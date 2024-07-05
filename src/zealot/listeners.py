import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar, Token
from fnmatch import fnmatch
from typing import NotRequired, Type, TypedDict

from django.conf import settings
from django.db import models

from zealot.util import get_caller

from .errors import NPlusOneError, ZealotError


class QuerySource(TypedDict):
    model: type[models.Model]
    field: str
    instance_key: str  # e.g. `User:123`


_is_in_context = ContextVar("in_context", default=False)

logger = logging.getLogger("zealot")


class AllowListEntry(TypedDict):
    model: str
    field: NotRequired[str]


class Listener(ABC):
    @abstractmethod
    def notify(self, *args, **kwargs): ...

    @abstractmethod
    def reset(self): ...

    @property
    @abstractmethod
    def error_class(self) -> type[ZealotError]: ...

    @property
    def _allowlist(self) -> list[AllowListEntry]:
        if hasattr(settings, "ZEALOT_ALLOWLIST"):
            return settings.ZEALOT_ALLOWLIST
        else:
            return []

    def _alert(self, model: type[models.Model], field: str, message: str):
        should_error = (
            settings.ZEALOT_RAISE
            if hasattr(settings, "ZEALOT_RAISE")
            else True
        )
        is_allowlisted = False
        for entry in self._allowlist:
            model_match = fnmatch(
                f"{model._meta.app_label}.{model.__name__}", entry["model"]
            )
            field_match = fnmatch(field, entry.get("field", "*"))
            if model_match and field_match:
                is_allowlisted = True
                break

        if is_allowlisted:
            return

        caller = get_caller()
        message = f"{message} at {caller.filename}:{caller.lineno} in {caller.function}"
        if should_error:
            raise self.error_class(message)
        else:
            logger.warning(message)


class NPlusOneListener(Listener):
    ignored_instances: set[str]
    counts: dict[tuple[type[models.Model], str], int]

    def __init__(self):
        self.reset()

    @property
    def error_class(self):
        return NPlusOneError

    def notify(self, model: Type[models.Model], field: str, instance_key: str):
        if not _is_in_context.get():
            return

        key = (model, field)
        self.counts[key] += 1
        count = self.counts[key]
        if (
            count >= self._threshold
            and instance_key not in self.ignored_instances
        ):
            message = f"N+1 detected on {model.__name__}.{field}"
            self._alert(model, field, message)

    def ignore(self, instance_key: str):
        """
        Tells the listener to ignore N+1s arising from this instance.

        This is used when the given instance is singly-loaded, e.g. via `.first()`
        or `.get()`. This is to prevent false positives.
        """
        if not _is_in_context.get():
            return
        self.ignored_instances.add(instance_key)

    def reset(self):
        self.counts = defaultdict(int)
        self.ignored_instances = set()

    @property
    def _threshold(self) -> int:
        if hasattr(settings, "ZEALOT_NPLUSONE_THRESHOLD"):
            return settings.ZEALOT_NPLUSONE_THRESHOLD
        else:
            return 2


n_plus_one_listener = NPlusOneListener()


def setup() -> Token:
    return _is_in_context.set(True)


def teardown(token: Token | None = None):
    n_plus_one_listener.reset()
    if token:
        _is_in_context.reset(token)
    else:
        _is_in_context.set(False)


@contextmanager
def zealot_context():
    token = setup()
    try:
        yield
    finally:
        teardown(token)


@contextmanager
def zealot_ignore():
    token = _is_in_context.set(False)
    try:
        yield
    finally:
        _is_in_context.reset(token)
