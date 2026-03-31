import functools
import importlib
import inspect
from contextvars import ContextVar
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

# Set to True while inside Django's internal prefetch path
# (QuerySet._prefetch_related_objects or QuerySet._iterator).
# Used to suppress get_prefetch_queryset notifications for
# proper .prefetch_related() usage on querysets.
_in_queryset_prefetch: ContextVar[bool] = ContextVar(
    "_in_queryset_prefetch", default=False
)

# Set to True while inside a patched get_prefetch_queryset call.
# Suppresses _fetch_all notifications on querysets that
# get_prefetch_queryset creates and evaluates internally.
_in_prefetch_queryset: ContextVar[bool] = ContextVar(
    "_in_prefetch_queryset", default=False
)


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

    def wrapper(*args, **kwargs):
        if (
            queryset._result_cache is None
            and not _in_prefetch_queryset.get()
            and not getattr(queryset, "__zeal_skip_notify", False)
        ):
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

    def wrapper(*args, **kwargs):
        queryset = queryset_func(*args, **kwargs)

        # don't patch the same queryset more than once
        if (
            hasattr(queryset, "__zeal_patched") and queryset.__zeal_patched  # type: ignore
        ):
            return queryset

        if args and args != context.get("args"):
            context["args"] = args

        # When comparing kwargs, we must use id() rather than == because
        # __eq__ methods on model instances can trigger infinite recursion.
        if kwargs:
            existing_kwargs = context.get("kwargs")
            if existing_kwargs is None or any(
                id(v) != id(existing_kwargs.get(k)) for k, v in kwargs.items()
            ):
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


def _wrap_prefetch_queryset(original, notify_fn):
    """Wrap a get_prefetch_queryset method to detect N+1s from
    standalone prefetch_related_objects() calls.

    Calls notify_fn() unless we're inside a queryset's own
    prefetch path. Suppresses the _fetch_all notify on the
    returned queryset to avoid double-counting.
    """

    def patched(self, instances, queryset=None):
        if not _in_queryset_prefetch.get():
            notify_fn(self, instances)
        token = _in_prefetch_queryset.set(True)
        try:
            result = original(self, instances, queryset)
        finally:
            _in_prefetch_queryset.reset(token)
        result[0].__zeal_skip_notify = True  # type: ignore
        return result

    return patched


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

    ForwardManyToOneDescriptor.get_prefetch_queryset = _wrap_prefetch_queryset(
        ForwardManyToOneDescriptor.get_prefetch_queryset,
        lambda self, instances: n_plus_one_listener.notify(
            self.field.model, self.field.name, instance_key=None
        ),
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

        def notify_fn(self, instances):
            rel = manager_call_args["rel"]
            model, field_name = parse_related_parts(
                rel.model, rel.related_name, rel.related_model
            )
            n_plus_one_listener.notify(model, field_name, instance_key=None)

        manager.get_prefetch_queryset = _wrap_prefetch_queryset(  # type: ignore
            manager.get_prefetch_queryset,  # type: ignore
            notify_fn,
        )

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

    ReverseOneToOneDescriptor.get_prefetch_queryset = _wrap_prefetch_queryset(
        ReverseOneToOneDescriptor.get_prefetch_queryset,
        lambda self, instances: n_plus_one_listener.notify(
            self.related.field.related_model,
            self.related.field.remote_field.name,
            instance_key=None,
        ),
    )


def patch_many_to_many_descriptor():
    def parser(context: QuerysetContext) -> QuerySource:
        assert (
            "manager_call_args" in context
            and context["manager_call_args"] is not None
            and "rel" in context["manager_call_args"]
        )
        assert "instance" in context and context["instance"] is not None
        rel = context["manager_call_args"]["rel"]
        instance = context["instance"]
        model = instance.__class__
        is_reverse = context["manager_call_args"]["reverse"]
        if is_reverse:
            field_name = rel.related_name
            related_model = rel.related_model
        else:
            field_name = rel.field.name
            related_model = rel.model

        model, field_name = parse_related_parts(
            model, field_name, related_model
        )
        return {
            "model": model,
            "field": field_name,
            "instance_key": get_instance_key(instance),
        }

    def patched_create_forward_many_to_many_manager(*args, **kwargs):
        manager_call_args = inspect.getcallargs(
            create_forward_many_to_many_manager, *args, **kwargs
        )
        manager = create_forward_many_to_many_manager(*args, **kwargs)

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

        def notify_fn(self, instances):
            rel = manager_call_args["rel"]
            is_reverse = manager_call_args["reverse"]
            if is_reverse:
                field_name = rel.related_name
                related_model = rel.related_model
            else:
                field_name = rel.field.name
                related_model = rel.model
            model = instances[0].__class__
            model, field_name = parse_related_parts(
                model, field_name, related_model
            )
            n_plus_one_listener.notify(model, field_name, instance_key=None)

        manager.get_prefetch_queryset = _wrap_prefetch_queryset(  # type: ignore
            manager.get_prefetch_queryset,  # type: ignore
            notify_fn,
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
            qs = args[0]
            # Detect N+1 on standalone .get() calls (e.g. in a loop).
            # Skip if the queryset is already tracked via a relation descriptor.
            if not getattr(qs, "__zeal_patched", False):
                n_plus_one_listener.notify(qs.model, "get", instance_key=None)
            ret = func(*args, **kwargs)
            n_plus_one_listener.ignore(get_instance_key(ret))
            return ret

        return wrapper

    QuerySet.get = patch_get(QuerySet.get)

    original_prefetch_related_objects = QuerySet._prefetch_related_objects  # type: ignore

    def patched_prefetch_related_objects(self):
        token = _in_queryset_prefetch.set(True)
        try:
            return original_prefetch_related_objects(self)
        finally:
            _in_queryset_prefetch.reset(token)

    QuerySet._prefetch_related_objects = (  # type: ignore
        patched_prefetch_related_objects
    )

    original_iterator = QuerySet._iterator  # type: ignore

    def patched_iterator(self, *args, **kwargs):
        token = _in_queryset_prefetch.set(True)
        try:
            yield from original_iterator(self, *args, **kwargs)
        finally:
            _in_queryset_prefetch.reset(token)

    QuerySet._iterator = patched_iterator  # type: ignore


def patch():
    patch_forward_many_to_one_descriptor()
    patch_reverse_many_to_one_descriptor()
    patch_reverse_one_to_one_descriptor()
    patch_many_to_many_descriptor()
    patch_deferred_attribute()
    patch_global_queryset()
