from django.apps import AppConfig

from .listeners import reset as setup_listeners
from .patch import patch


class QuerySpyConfig(AppConfig):
    name = "queryspy"

    def ready(self):
        setup_listeners()
        patch()
        pass
