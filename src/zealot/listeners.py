import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Optional, TypedDict

from django.conf import settings
from django.db import models

from zealot.util import get_caller

from .errors import NPlusOneError, ZealotError


class QuerySource(TypedDict):
    model: type[models.Model]
    field: str
    instance_key: Optional[str]  # e.g. `User:123`


# tuple of (model, field, caller)
CountsKey = tuple[type[models.Model], str, str]


@dataclass
class NPlusOneContext:
    # None means not initialized
    # bool means initialized, in/not in zealot context
    is_in_context: Optional[bool] = None
    counts: dict[CountsKey, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    ignored: set[str] = field(default_factory=set)


_nplusone_context: ContextVar[NPlusOneContext] = ContextVar(
    "nplusone",
    default=NPlusOneContext(),
)

logger = logging.getLogger("zealot")


class AllowListEntry(TypedDict):
    model: str
    field: Optional[str]


class Listener(ABC):
    @abstractmethod
    def notify(self, *args, **kwargs): ...

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
            field_match = fnmatch(field, entry.get("field") or "*")
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
    @property
    def error_class(self):
        return NPlusOneError

    def notify(
        self,
        model: type[models.Model],
        field: str,
        instance_key: Optional[str],
    ):
        context = _nplusone_context.get()
        if not context.is_in_context:
            return

        caller = get_caller()
        key = (model, field, f"{caller.filename}:{caller.lineno}")
        context.counts[key] += 1
        count = context.counts[key]
        if count >= self._threshold and instance_key not in context.ignored:
            message = f"N+1 detected on {model.__name__}.{field}"
            self._alert(model, field, message)
        _nplusone_context.set(context)

    def ignore(self, instance_key: Optional[str]):
        """
        Tells the listener to ignore N+1s arising from this instance.

        This is used when the given instance is singly-loaded, e.g. via `.first()`
        or `.get()`. This is to prevent false positives.
        """
        context = _nplusone_context.get()
        if not context.is_in_context:
            return
        if not instance_key:
            return
        context.ignored.add(instance_key)
        _nplusone_context.set(context)

    @property
    def _threshold(self) -> int:
        if hasattr(settings, "ZEALOT_NPLUSONE_THRESHOLD"):
            return settings.ZEALOT_NPLUSONE_THRESHOLD
        else:
            return 2


n_plus_one_listener = NPlusOneListener()


def setup() -> Optional[Token]:
    # if we're already in an ignore-context, we don't want to override
    # it.
    context = _nplusone_context.get()
    if context.is_in_context is False:
        new_is_in_context = False
    else:
        new_is_in_context = True

    return _nplusone_context.set(
        NPlusOneContext(is_in_context=new_is_in_context)
    )


def teardown(token: Optional[Token] = None):
    if token:
        _nplusone_context.reset(token)
    else:
        _nplusone_context.set(NPlusOneContext())


@contextmanager
def zealot_context():
    token = setup()
    try:
        yield
    finally:
        teardown(token)


@contextmanager
def zealot_ignore():
    old_context = _nplusone_context.get()
    new_context = NPlusOneContext(
        counts=old_context.counts.copy(),
        ignored=old_context.ignored.copy(),
        is_in_context=False,
    )
    token = _nplusone_context.set(new_context)
    try:
        yield
    finally:
        _nplusone_context.reset(token)
