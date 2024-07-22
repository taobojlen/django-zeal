import logging
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Optional, TypedDict

from django.conf import settings
from django.db import models

from zeal.util import get_caller

from .errors import NPlusOneError, ZealError


class QuerySource(TypedDict):
    model: type[models.Model]
    field: str
    instance_key: Optional[str]  # e.g. `User:123`


# tuple of (model, field, caller)
CountsKey = tuple[type[models.Model], str, str]


class AllowListEntry(TypedDict):
    model: str
    field: Optional[str]


@dataclass
class NPlusOneContext:
    counts: dict[CountsKey, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    ignored: set[str] = field(default_factory=set)
    allowlist: list[AllowListEntry] = field(default_factory=list)


_nplusone_context: ContextVar[NPlusOneContext] = ContextVar(
    "nplusone",
    default=NPlusOneContext(),
)

logger = logging.getLogger("zeal")


class Listener(ABC):
    @abstractmethod
    def notify(self, *args, **kwargs): ...

    @property
    @abstractmethod
    def error_class(self) -> type[ZealError]: ...

    @property
    def _allowlist(self) -> list[AllowListEntry]:
        if hasattr(settings, "ZEAL_ALLOWLIST"):
            settings_allowlist = settings.ZEAL_ALLOWLIST
        else:
            settings_allowlist = []

        return [*settings_allowlist, *_nplusone_context.get().allowlist]

    def _alert(self, model: type[models.Model], field: str, message: str):
        should_error = (
            settings.ZEAL_RAISE if hasattr(settings, "ZEAL_RAISE") else True
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
            warnings.warn_explicit(
                message,
                UserWarning,
                filename=caller.filename,
                lineno=caller.lineno,
            )


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
        if not instance_key:
            return
        context.ignored.add(instance_key)
        _nplusone_context.set(context)

    @property
    def _threshold(self) -> int:
        if hasattr(settings, "ZEAL_NPLUSONE_THRESHOLD"):
            return settings.ZEAL_NPLUSONE_THRESHOLD
        else:
            return 2


n_plus_one_listener = NPlusOneListener()


def setup() -> Optional[Token]:
    # if we're already in an ignore-context, we don't want to override
    # it.
    context = _nplusone_context.get()
    return _nplusone_context.set(NPlusOneContext(allowlist=context.allowlist))


def teardown(token: Optional[Token] = None):
    if token:
        _nplusone_context.reset(token)
    else:
        _nplusone_context.set(NPlusOneContext())


@contextmanager
def zeal_context():
    token = setup()
    try:
        yield
    finally:
        teardown(token)


@contextmanager
def zeal_ignore(allowlist: Optional[list[AllowListEntry]] = None):
    if allowlist is None:
        allowlist = [{"model": "*", "field": "*"}]

    old_context = _nplusone_context.get()
    new_context = NPlusOneContext(
        counts=old_context.counts.copy(),
        ignored=old_context.ignored.copy(),
        allowlist=[*old_context.allowlist, *allowlist],
    )
    token = _nplusone_context.set(new_context)
    try:
        yield
    finally:
        _nplusone_context.reset(token)
