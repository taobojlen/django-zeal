import functools
import importlib
import inspect
from typing import Any, Callable, Optional, TypedDict, Union

from django.db import models
from django.db.models.fields.related_descriptors import (
    ForwardManyToOneDescriptor,
    ReverseOneToOneDescriptor,
    create_forward_many_to_many_manager,
    create_reverse_many_to_one_manager,
)
from django.db.models.query import QuerySet
from django.db.models.query_utils import DeferredAttribute

from zeal.util import is_single_query

from .listeners import QuerySource, n_plus_one_listener


class QuerysetContext(TypedDict):
    args: Optional[Any]
    kwargs: Optional[Any]

    # This is only used for many-to-many relations. It contains the call args
    # when `create_forward_many_to_many_manager` is called.
    manager_call_args: Optional[dict[str, Any]]

    # used by ReverseManyToOne. a django model instance.
    instance: Optional[models.Model]


Parser = Callable[[QuerysetContext], QuerySource]


def get_instance_key(
    instance: Union[models.Model, dict[str, Any]],
) -> Optional[str]:
    if isinstance(instance, models.Model):
        return f"{instance.__class__.__name__}:{instance.pk}"
    else:
        # when calling a queryset with `.values(...).get()`, the instance
        # we get here may be a dict. we don't handle that case formally,
        # so we return None to ignore that instance in our listeners.
        return None


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
            parsed = parser(context)
            n_plus_one_listener.notify(
                parsed["model"],
                parsed["field"],
                parsed["instance_key"],
            )
        return fetch_all(*args, **kwargs)

    return wrapper


def patch_queryset_function(
    queryset_func: Callable[..., models.QuerySet],
    parser: Parser,
    context: Optional[QuerysetContext] = None,
):
    if context is None:
        context = {
            "args": None,
            "kwargs": None,
            "manager_call_args": None,
            "instance": None,
        }

    @functools.wraps(queryset_func)
    def wrapper(*args, **kwargs):
        queryset = queryset_func(*args, **kwargs)

        # don't patch the same queryset more than once
        if (
            hasattr(queryset, "__zeal_patched") and queryset.__zeal_patched  # type: ignore
        ):
            return queryset
        if args and args != context.get("args"):
            context["args"] = args
        if kwargs and kwargs != context.get("kwargs"):
            context["kwargs"] = kwargs
        queryset._clone = patch_queryset_function(  # type: ignore
            queryset._clone,  # type: ignore
            parser,
            context=context,
        )
        queryset._fetch_all = patch_queryset_fetch_all(
            queryset, parser, context
        )
        queryset.__zeal_patched = True  # type: ignore
        return queryset

    return wrapper


def patch_forward_many_to_one_descriptor():
    """
    This also handles ForwardOneToOneDescriptor, which is
    a subclass of ForwardManyToOneDescriptor.
    """

    def parser(context: QuerysetContext) -> QuerySource:
        assert "args" in context and context["args"] is not None
        descriptor = context["args"][0]

        if "kwargs" in context and context["kwargs"] is not None:
            instance = context["kwargs"]["instance"]
            instance_key = get_instance_key(instance)
        else:
            # `get_queryset` can in some cases be called without any
            # kwargs. In those cases, we ignore the instance.
            instance_key = None
        return {
            "model": descriptor.field.model,
            "field": descriptor.field.name,
            "instance_key": instance_key,
        }

    ForwardManyToOneDescriptor.get_queryset = patch_queryset_function(
        ForwardManyToOneDescriptor.get_queryset, parser=parser
    )


def parse_related_parts(
    model: type[models.Model],
    related_name: Optional[str],
    related_model: type[models.Model],
) -> tuple[type[models.Model], str]:
    field_name = related_name or f"{related_model._meta.model_name}_set"
    return (model, field_name)


def patch_reverse_many_to_one_descriptor():
    def parser(context: QuerysetContext) -> QuerySource:
        assert (
            "manager_call_args" in context
            and context["manager_call_args"] is not None
            and "rel" in context["manager_call_args"]
        )
        assert "instance" in context and context["instance"] is not None
        rel = context["manager_call_args"]["rel"]
        model, field = parse_related_parts(
            rel.model, rel.related_name, rel.related_model
        )
        return {
            "model": model,
            "field": field,
            "instance_key": get_instance_key(context["instance"]),
        }

    def patched_create_reverse_many_to_one_manager(*args, **kwargs):
        manager_call_args = inspect.getcallargs(
            create_reverse_many_to_one_manager, *args, **kwargs
        )
        manager = create_reverse_many_to_one_manager(*args, **kwargs)

        def patch_init_method(func):
            @functools.wraps(func)
            def wrapper(self, instance):
                self.get_queryset = patch_queryset_function(
                    self.get_queryset,
                    parser,
                    context={
                        "args": None,
                        "kwargs": None,
                        "manager_call_args": manager_call_args,
                        "instance": instance,
                    },
                )
                return func(self, instance)

            return wrapper

        manager.__init__ = patch_init_method(manager.__init__)  # type: ignore
        return manager

    patch_module_function(
        create_reverse_many_to_one_manager,
        patched_create_reverse_many_to_one_manager,
    )


def patch_reverse_one_to_one_descriptor():
    def parser(context: QuerysetContext) -> QuerySource:
        assert "args" in context and context["args"] is not None
        descriptor = context["args"][0]
        field = descriptor.related.field
        if "kwargs" in context and context["kwargs"] is not None:
            instance = context["kwargs"]["instance"]
            instance_key = get_instance_key(instance)
        else:
            instance_key = None
        return {
            "model": field.related_model,
            "field": field.remote_field.name,
            "instance_key": instance_key,
        }

    ReverseOneToOneDescriptor.get_queryset = patch_queryset_function(
        ReverseOneToOneDescriptor.get_queryset, parser
    )


def patch_many_to_many_descriptor():
    def parser(context: QuerysetContext) -> QuerySource:
        assert (
            "manager_call_args" in context
            and context["manager_call_args"] is not None
            and "rel" in context["manager_call_args"]
        )
        assert "args" in context and context["args"] is not None
        rel = context["manager_call_args"]["rel"]
        manager = context["args"][0]
        model = manager.instance.__class__
        related_model = manager.target_field.related_model
        is_reverse = context["manager_call_args"]["reverse"]
        field_name = (
            rel.related_name if is_reverse else manager.prefetch_cache_name
        )

        model, field_name = parse_related_parts(
            model, field_name, related_model
        )
        return {
            "model": model,
            "field": field_name,
            "instance_key": get_instance_key(manager.instance),
        }

    def patched_create_forward_many_to_many_manager(*args, **kwargs):
        manager_call_args = inspect.getcallargs(
            create_forward_many_to_many_manager, *args, **kwargs
        )
        manager = create_forward_many_to_many_manager(*args, **kwargs)
        manager.get_queryset = patch_queryset_function(
            manager.get_queryset,
            parser,
            context={
                "args": None,
                "kwargs": None,
                "manager_call_args": manager_call_args,
                "instance": None,
            },
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
                n_plus_one_listener.notify(
                    instance.__class__, self.field.name, str(instance.pk)
                )
            return result

        return wrapper

    DeferredAttribute._check_parent_chain = patched_check_parent_chain(  # type: ignore
        DeferredAttribute._check_parent_chain  # type: ignore
    )


def patch_global_queryset():
    """
    We patch `_fetch_all` and `.get()` on querysets to let us ignore singly-loaded
    instances. We don't want to trigger N+1 errors from such instances because of
    the high false positive rate.
    """

    def patch_fetch_all(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            should_ignore = (
                is_single_query(self.query) and self._result_cache is None
            )
            ret = func(self, *args, **kwargs)  # call the original _fetch_all
            if should_ignore and len(self) > 0:
                n_plus_one_listener.ignore(get_instance_key(self[0]))
            return ret

        return wrapper

    QuerySet._fetch_all = patch_fetch_all(QuerySet._fetch_all)

    def patch_get(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            ret = func(*args, **kwargs)
            n_plus_one_listener.ignore(get_instance_key(ret))
            return ret

        return wrapper

    QuerySet.get = patch_get(QuerySet.get)


def patch():
    patch_forward_many_to_one_descriptor()
    patch_reverse_many_to_one_descriptor()
    patch_reverse_one_to_one_descriptor()
    patch_many_to_many_descriptor()
    patch_deferred_attribute()
    patch_global_queryset()
