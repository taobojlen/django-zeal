from django.apps import AppConfig

from .patch import patch


class QuerySpyConfig(AppConfig):
    name = "queryspy"

    def ready(self):
        patch()
