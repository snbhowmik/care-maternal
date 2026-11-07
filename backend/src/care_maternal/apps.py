from pathlib import Path

from django.apps import AppConfig

PLUGIN_NAME = "care_maternal"


class CareMaternalConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = "Care Maternal"

    def __init__(self, app_name, app_module):
        super().__init__(app_name, app_module)
        # shortcut: the editable install loads care_maternal as a namespace package whose first
        # path is the outer repo folder, so Django would look for management commands there.
        # Pin the path to the real package. Scaffold issue #7 describes the same root cause.
        self.path = str(Path(__file__).resolve().parent)

    def ready(self):
        from care_maternal import signals  # noqa: F401
        from care_maternal import tasks  # noqa: F401
