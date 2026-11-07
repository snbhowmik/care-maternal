from pathlib import Path

from django.http import HttpResponse

PORTAL_HTML = Path(__file__).resolve().parent.parent / "portal" / "index.html"


def portal(request):
    """Demo patient portal page. Plain HTML, no login required to load it."""
    return HttpResponse(PORTAL_HTML.read_text(), content_type="text/html; charset=utf-8")
