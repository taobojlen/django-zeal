from django.apps import AppConfig

from .patch import patch


class ZealConfig(AppConfig):
    name = "zeal"

    def ready(self):
        from .constants import initialize_app_registry

        initialize_app_registry()
        patch()
