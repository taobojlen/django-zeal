import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from fnmatch import fnmatch
from typing import NotRequired, Type, TypedDict

from django.conf import settings
from django.db import models

from zealot.util import get_caller

from .errors import NPlusOneError, ZealotError

ModelAndField = tuple[Type[models.Model], str]

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
    counts: dict[ModelAndField, int]

    def __init__(self):
        self.reset()

    @property
    def error_class(self):
        return NPlusOneError

    def notify(self, model: Type[models.Model], field: str):
        if not _is_in_context.get():
            return

        key = (model, field)
        self.counts[key] += 1
        count = self.counts[key]
        if count >= self._threshold:
            message = f"N+1 detected on {model.__name__}.{field}"
            self._alert(model, field, message)

    def reset(self):
        self.counts = defaultdict(int)

    @property
    def _threshold(self) -> int:
        if hasattr(settings, "ZEALOT_NPLUSONE_THRESHOLD"):
            return settings.ZEALOT_NPLUSONE_THRESHOLD
        else:
            return 2


n_plus_one_listener = NPlusOneListener()


def setup():
    _is_in_context.set(True)


def teardown():
    n_plus_one_listener.reset()
    _is_in_context.set(False)


@contextmanager
def zealot_context():
    token = _is_in_context.set(True)
    try:
        yield
    finally:
        n_plus_one_listener.reset()
        _is_in_context.reset(token)


@contextmanager
def zealot_ignore():
    token = _is_in_context.set(False)
    try:
        yield
    finally:
        _is_in_context.reset(token)
