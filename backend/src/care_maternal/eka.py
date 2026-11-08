"""Eka Care tokens for the scribe, minted on the server.

The CARE backend holds the Eka client ID and secret. It logs in to Eka, keeps the refresh token in
the server cache, and gives logged-in staff only the short-lived access token (30 minutes). The
scribe in the browser asks for a new one when Eka answers 401.
"""

import time

import requests
from django.core.cache import cache
from rest_framework.exceptions import APIException

from care_maternal.settings import plugin_settings

TIMEOUT_SECONDS = 15
EARLY_RENEW_SECONDS = 120  # renew a little before expiry so a token never dies mid-request
CACHE_KEY = "care_maternal:eka:tokens"


class EkaUnavailable(APIException):
    status_code = 503
    default_detail = "Eka Care is not available. Try again in a minute."


def configured() -> bool:
    return bool(plugin_settings.MATERNAL_EKA_CLIENT_ID and plugin_settings.MATERNAL_EKA_CLIENT_SECRET)


def _url(path: str) -> str:
    return plugin_settings.MATERNAL_EKA_API_BASE.rstrip("/") + path


def _store(data: dict) -> dict:
    now = time.time()
    tokens = {
        "access_token": data["access_token"],
        "expires_at": now + int(data.get("expires_in") or 0),
        "refresh_token": data.get("refresh_token", ""),
        "refresh_expires_at": now + int(data.get("refresh_expires_in") or 0),
    }
    cache.set(CACHE_KEY, tokens, timeout=max(int(data.get("refresh_expires_in") or 0), 60))
    return tokens


def _login() -> dict:
    response = requests.post(
        _url("/connect-auth/v1/account/login"),
        json={
            "client_id": plugin_settings.MATERNAL_EKA_CLIENT_ID,
            "client_secret": plugin_settings.MATERNAL_EKA_CLIENT_SECRET,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise EkaUnavailable()
    return _store(response.json())


def _refresh(tokens: dict) -> dict | None:
    response = requests.post(
        _url("/connect-auth/v1/account/refresh-token"),
        json={"refresh_token": tokens["refresh_token"], "access_token": tokens["access_token"]},
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Client-Id": plugin_settings.MATERNAL_EKA_CLIENT_ID,
        },
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        return None
    return _store(response.json())


def access_token(force: bool = False) -> dict:
    """A valid access token and its expiry (epoch seconds). Never returns the refresh token."""
    if not configured():
        raise EkaUnavailable("Eka Care is not configured on this hospital.")
    tokens = cache.get(CACHE_KEY)
    now = time.time()
    fresh = tokens and not force and tokens["expires_at"] - EARLY_RENEW_SECONDS > now
    if not fresh:
        can_refresh = tokens and tokens.get("refresh_token") and tokens["refresh_expires_at"] > now
        try:
            tokens = (can_refresh and _refresh(tokens)) or _login()
        except requests.RequestException as exc:
            raise EkaUnavailable() from exc
    return {"access_token": tokens["access_token"], "expires_at": int(tokens["expires_at"])}
