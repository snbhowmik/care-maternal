"""Eka Care tokens: minted on the server, cached, renewed, and only for logged-in staff."""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from care.users.models import User
from care_maternal import eka
from care_maternal.settings import plugin_settings

CONFIG = {"care_maternal": {"MATERNAL_EKA_CLIENT_ID": "EC_TEST", "MATERNAL_EKA_CLIENT_SECRET": "secret"}}


def _response(status, body):
    r = mock.Mock(status_code=status)
    r.json.return_value = body
    return r


TOKENS = {"access_token": "access-1", "expires_in": 1800, "refresh_token": "refresh-1", "refresh_expires_in": 7776000}


@override_settings(PLUGIN_CONFIGS=CONFIG)
class EkaTokenTests(TestCase):
    def setUp(self):
        plugin_settings.reload()
        cache.delete(eka.CACHE_KEY)

    def tearDown(self):
        cache.delete(eka.CACHE_KEY)

    @mock.patch("care_maternal.eka.requests.post")
    def test_logs_in_once_and_reuses_the_token(self, post):
        post.return_value = _response(200, TOKENS)
        first = eka.access_token()
        second = eka.access_token()
        self.assertEqual(first["access_token"], "access-1")
        self.assertEqual(second["access_token"], "access-1")
        self.assertEqual(post.call_count, 1)
        self.assertNotIn("refresh_token", first)
        sent = post.call_args.kwargs["json"]
        self.assertEqual(sent, {"client_id": "EC_TEST", "client_secret": "secret"})

    @mock.patch("care_maternal.eka.requests.post")
    def test_renew_uses_the_refresh_token(self, post):
        post.side_effect = [_response(200, TOKENS), _response(200, dict(TOKENS, access_token="access-2"))]
        eka.access_token()
        renewed = eka.access_token(force=True)
        self.assertEqual(renewed["access_token"], "access-2")
        self.assertTrue(post.call_args.args[0].endswith("/connect-auth/v1/account/refresh-token"))
        self.assertEqual(post.call_args.kwargs["headers"]["Client-Id"], "EC_TEST")

    @mock.patch("care_maternal.eka.requests.post")
    def test_failed_refresh_falls_back_to_login(self, post):
        post.side_effect = [_response(200, TOKENS), _response(401, {}), _response(200, dict(TOKENS, access_token="access-3"))]
        eka.access_token()
        self.assertEqual(eka.access_token(force=True)["access_token"], "access-3")

    @mock.patch("care_maternal.eka.requests.post")
    def test_endpoint_is_for_logged_in_staff_only(self, post):
        post.return_value = _response(200, TOKENS)
        client = APIClient()
        self.assertIn(client.get("/api/care_maternal/eka/token/").status_code, (401, 403))
        client.force_authenticate(User.objects.create(username="maternal-eka-staff"))
        response = client.get("/api/care_maternal/eka/token/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["access_token"], "access-1")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_not_configured_is_a_clear_error(self):
        with override_settings(PLUGIN_CONFIGS={"care_maternal": {}}):
            plugin_settings.reload()
            with self.assertRaises(eka.EkaUnavailable):
                eka.access_token()
