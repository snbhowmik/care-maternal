"""URL routes.

Core mounts this module at /api/care_maternal/ via the PLUGIN_APPS loop in
config/urls.py. Do not repeat that prefix here.

Routes under `otp/` are for the patient portal (OTP-authenticated, phone-number scoped).
Keep them read-mostly. See the care-auth-contexts skill.
"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from care_maternal.viewsets.check_templates import CheckTemplateViewSet
from care_maternal.viewsets.config import ConfigView
from care_maternal.viewsets.demo_sms import DemoSmsView
from care_maternal.viewsets.duty import DutyView, ReminderViewSet
from care_maternal.viewsets.eka import EkaTokenView
from care_maternal.viewsets.otp_pregnancy import OTPPregnancyViewSet
from care_maternal.viewsets.portal import portal
from care_maternal.viewsets.pregnancy import PregnancyViewSet
from care_maternal.viewsets.referrals import (
    InboundReferralView,
    InboundStatusView,
    OTPReferralViewSet,
    ReferralViewSet,
)

router = DefaultRouter()
router.register("pregnancies", PregnancyViewSet, basename="maternal-pregnancy")
router.register("otp/pregnancies", OTPPregnancyViewSet, basename="otp-maternal-pregnancy")
router.register("referrals", ReferralViewSet, basename="maternal-referral")
router.register("reminders", ReminderViewSet, basename="maternal-reminder")
router.register("check-templates", CheckTemplateViewSet, basename="maternal-check-template")
router.register("otp/referrals", OTPReferralViewSet, basename="otp-maternal-referral")

urlpatterns = [
    path("referrals/inbound/", InboundReferralView.as_view(), name="care_maternal-referral-inbound"),
    path("referrals/status/", InboundStatusView.as_view(), name="care_maternal-referral-status"),
    *router.urls,
    path("config/", ConfigView.as_view(), name="care_maternal-config"),
    path("eka/token/", EkaTokenView.as_view(), name="care_maternal-eka-token"),
    path("duty/", DutyView.as_view(), name="care_maternal-duty"),
    path("otp/demo-sms/", DemoSmsView.as_view(), name="care_maternal-demo-sms"),
    path("portal/", portal, name="care_maternal-portal"),
]
