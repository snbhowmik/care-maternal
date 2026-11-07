"""Demo only: write the login code to the server log as an SMS would be.

shortcut: CARE's login code goes to SMS only when USE_SMS is on, which is hardcoded off in
core. This endpoint logs the latest code through CARE's console SMS backend instead.
Disabled in production. Upgrade: remove it once a real SMS provider is configured.
"""

from django.conf import settings
from django.http import Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from care.facility.models.patient import MobileOTP
from care_maternal.settings import plugin_settings
from care.utils.sms.message import TextMessage


class DemoSmsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if settings.IS_PRODUCTION or not plugin_settings.MATERNAL_DEMO_SMS_ENABLED:
            raise Http404
        phone = request.data.get("phone_number", "")
        otp = (
            MobileOTP.objects.filter(phone_number=phone, is_used=False)
            .order_by("-created_date")
            .first()
        )
        if not otp:
            return Response({"logged": False}, status=404)
        TextMessage(
            content=f"[DEMO] Your CARE Maternal login code is {otp.otp}",
            recipients=[phone],
            fail_silently=True,
        ).dispatch(fail_silently=True)
        return Response({"logged": True})
