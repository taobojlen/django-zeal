from django.apps import AppConfig, apps

from .patch import patch


class ZealConfig(AppConfig):
    name = "zeal"

    def ready(self):
        from .constants import ALL_APPS

        for model in apps.get_models():
            ALL_APPS[f"{model._meta.app_label}.{model.__name__}"] = [
                field.name for field in model._meta.get_fields()
            ]
        patch()
