from typing import TYPE_CHECKING

from django.apps import apps

ALL_APPS = {}


def initialize_app_registry():
    if TYPE_CHECKING:
        # pyright is unhappy with model._meta.related_objects below,
        # so we need to skip this code path in type checking
        return

    for model in apps.get_models():
        # Get direct fields
        fields = set(
            field.name for field in model._meta.get_fields(include_hidden=True)
        )

        # Get reverse relations using related_objects
        reverse_fields = set(
            rel.get_accessor_name() for rel in model._meta.related_objects
        )

        ALL_APPS[f"{model._meta.app_label}.{model.__name__}"] = (
            fields | reverse_fields
        )
