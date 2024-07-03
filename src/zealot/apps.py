from django.apps import AppConfig

from .patch import patch


class ZealotConfig(AppConfig):
    name = "zealot"

    def ready(self):
        patch()
