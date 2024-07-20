from django.apps import AppConfig

from .patch import patch


class ZealConfig(AppConfig):
    name = "zeal"

    def ready(self):
        patch()
