import functools
import importlib
import inspect
from typing import Any, Callable, NotRequired, Type, TypedDict, Unpack

from django.db import models
from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    create_forward_many_to_many_manager,
    create_reverse_many_to_one_manager,
)
from django.db.models.query_utils import DeferredAttribute

from .listeners import ModelAndField, n_plus_one_listener


class QuerysetContext(TypedDict):
    args: NotRequired[Any]
    kwargs: NotRequired[Any]

    # This is only used for many-to-many relations. It contains the call args
    # when `create_forward_many_to_many_manager` is called.
    manager_call_args: NotRequired[dict[str, Any]]


Parser = Callable[[QuerysetContext], ModelAndField]


def patch_module_function(original, patched):
    module = importlib.import_module(original.__module__)
    setattr(module, original.__name__, patched)


def patch_queryset_fetch_all(
    queryset: models.QuerySet, parser: Parser, context: QuerysetContext
):
    fetch_all = queryset._fetch_all

    @functools.wraps(fetch_all)
    def wrapper(*args, **kwargs):
        if queryset._result_cache is None:
            n_plus_one_listener.notify(*parser(context))
        return fetch_all(*args, **kwargs)

    return wrapper


def patch_queryset_function(
    queryset_func: Callable[..., models.QuerySet],
    parser: Parser,
    **context: Unpack[QuerysetContext],
):
    @functools.wraps(queryset_func)
    def wrapper(*args, **kwargs):
        queryset = queryset_func(*args, **kwargs)

        # don't patch the same queryset more than once
        if (
            hasattr(queryset, "__queryspy_patched")
            and queryset.__queryspy_patched  # type: ignore
        ):
            return queryset
        context["args"] = context.get("args", args)
        context["kwargs"] = context.get("kwargs", kwargs)
        queryset._clone = patch_queryset_function(  # type: ignore
            queryset._clone,  # type: ignore
            parser,
            **context,
        )
        queryset._fetch_all = patch_queryset_fetch_all(
            queryset, parser, context
        )
        queryset.__queryspy_patched = True  # type: ignore
        return queryset

    return wrapper


def patch_forward_many_to_one_descriptor():
    """
    This also handles ForwardOneToOneDescriptor, which is
    a subclass of ForwardManyToOneDescriptor.
    """

    # in ForwardManyToOneDescriptor, get_object is only called when the related
    # object is not prefetched
    def patch_get_object(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            descriptor = args[0]
            n_plus_one_listener.notify(
                descriptor.field.model, descriptor.field.name
            )
            return func(*args, **kwargs)

        return wrapper

    ForwardManyToOneDescriptor.get_object = patch_get_object(
        ForwardManyToOneDescriptor.get_object
    )


def parse_related_parts(
    model: Type[models.Model],
    related_name: str | None,
    related_model: Type[models.Model],
) -> ModelAndField:
    field_name = related_name or f"{related_model._meta.model_name}_set"
    return (model, field_name)


def patch_reverse_many_to_one_descriptor():
    def parser(context: QuerysetContext):
        assert (
            "manager_call_args" in context
            and "rel" in context["manager_call_args"]
        )
        rel = context["manager_call_args"]["rel"]
        return parse_related_parts(
            rel.model, rel.related_name, rel.related_model
        )

    def patched_create_reverse_many_to_one_manager(*args, **kwargs):
        manager_call_args = inspect.getcallargs(
            create_reverse_many_to_one_manager, *args, **kwargs
        )
        manager = create_reverse_many_to_one_manager(*args, **kwargs)
        manager.get_queryset = patch_queryset_function(
            manager.get_queryset, parser, manager_call_args=manager_call_args
        )
        return manager

    patch_module_function(
        create_reverse_many_to_one_manager,
        patched_create_reverse_many_to_one_manager,
    )


def patch_reverse_one_to_one_descriptor():
    def parser(context: QuerysetContext):
        assert "args" in context
        descriptor = context["args"][0]
        field = descriptor.related.field
        return (field.related_model, field.remote_field.name)

    ReverseOneToOneDescriptor.get_queryset = patch_queryset_function(
        ReverseOneToOneDescriptor.get_queryset, parser
    )


def patch_many_to_many_descriptor():
    def parser(context: QuerysetContext):
        assert (
            "manager_call_args" in context
            and "rel" in context["manager_call_args"]
        )
        assert "args" in context
        rel = context["manager_call_args"]["rel"]
        manager = context["args"][0]
        model = manager.instance.__class__
        related_model = manager.target_field.related_model
        field_name = manager.prefetch_cache_name if rel.related_name else None

        return parse_related_parts(model, field_name, related_model)

    def patched_create_forward_many_to_many_manager(*args, **kwargs):
        manager_call_args = inspect.getcallargs(
            create_forward_many_to_many_manager, *args, **kwargs
        )
        manager = create_forward_many_to_many_manager(*args, **kwargs)
        manager.get_queryset = patch_queryset_function(
            manager.get_queryset, parser, manager_call_args=manager_call_args
        )
        return manager

    patch_module_function(
        create_forward_many_to_many_manager,
        patched_create_forward_many_to_many_manager,
    )


def patch_deferred_attribute():
    def patched_check_parent_chain(func):
        @functools.wraps(func)
        def wrapper(self, instance, *args, **kwargs):
            result = func(self, instance, *args, **kwargs)
            if result is None:
                n_plus_one_listener.notify(instance.__class__, self.field.name)
            return result

        return wrapper

    DeferredAttribute._check_parent_chain = patched_check_parent_chain(  # type: ignore
        DeferredAttribute._check_parent_chain  # type: ignore
    )


def patch():
    patch_forward_many_to_one_descriptor()
    patch_reverse_many_to_one_descriptor()
    patch_reverse_one_to_one_descriptor()
    patch_many_to_many_descriptor()
    patch_deferred_attribute()
