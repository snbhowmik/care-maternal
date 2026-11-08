from datetime import date

from rest_framework import serializers

from care_maternal.models import MaternalAlert, MaternalPregnancy, MaternalScheduleItem
from care_maternal.utils.schedule import item_state


class PregnancyCreateSerializer(serializers.Serializer):
    patient = serializers.UUIDField()
    lmp = serializers.DateField()
    gravida = serializers.IntegerField(min_value=1, max_value=30, default=1)
    para = serializers.IntegerField(min_value=0, max_value=30, default=0)
    abortions = serializers.IntegerField(min_value=0, max_value=30, default=0)
    living = serializers.IntegerField(min_value=0, max_value=30, default=0)


class PregnancySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="external_id", read_only=True)
    patient = serializers.UUIDField(source="patient.external_id", read_only=True)
    gestational_age = serializers.SerializerMethodField()

    class Meta:
        model = MaternalPregnancy
        fields = [
            "id", "patient", "lmp", "edd", "gravida", "para", "abortions", "living",
            "high_risk", "status", "gestational_age",
        ]
        read_only_fields = fields

    def get_gestational_age(self, obj) -> dict:
        weeks, days = divmod((date.today() - obj.lmp).days, 7)
        return {"weeks": weeks, "days": days}


class ScheduleItemSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="external_id", read_only=True)
    state = serializers.SerializerMethodField()

    class Meta:
        model = MaternalScheduleItem
        fields = [
            "id", "spec_id", "kind", "label", "due_from", "due_to", "waiting_on",
            "done_on", "state", "appointment_id", "appointment_at",
            "resolution", "resolution_note", "resolved_on", "priority",
        ]
        read_only_fields = fields

    appointment_id = serializers.SerializerMethodField()
    appointment_at = serializers.SerializerMethodField()

    def get_appointment_id(self, obj):
        return str(obj.booking.external_id) if obj.booking_id else None

    def get_appointment_at(self, obj):
        return obj.booking.token_slot.start_datetime.isoformat() if obj.booking_id else None

    def get_state(self, obj) -> str:
        return item_state(obj.due_from, obj.due_to, obj.done_on, date.today(), obj.resolution)


class BookVisitSerializer(serializers.Serializer):
    on_date = serializers.DateField()
    start_time = serializers.TimeField()


class CompleteItemSerializer(serializers.Serializer):
    on_date = serializers.DateField(default=date.today)


class EmergencySerializer(serializers.Serializer):
    symptoms = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                "vaginal_bleeding",
                "severe_abdominal_pain",
                "fainting_or_giddiness",
                "severe_vomiting_or_dehydration",
                "breathlessness_or_unstable_vitals",
            ]
        ),
        min_length=1,
    )


class AlertSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="external_id", read_only=True)

    class Meta:
        model = MaternalAlert
        fields = ["id", "audience", "kind", "message", "sms_sent", "acknowledged_on", "created_date"]
        read_only_fields = fields
