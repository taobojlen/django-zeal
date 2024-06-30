from django.apps import AppConfig

from .patch import patch

# from . import ugh


class QuerySpyConfig(AppConfig):
    name = "queryspy"

    def ready(self):
        patch()
        pass
