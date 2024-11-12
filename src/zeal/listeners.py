import inspect
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

from zeal.util import get_caller, get_stack

from .constants import ALL_APPS
from .errors import NPlusOneError, ZealConfigError, ZealError
from .signals import nplusone_detected


class QuerySource(TypedDict):
    model: type[models.Model]
    field: str
    instance_key: Optional[str]  # e.g. `User:123`


# tuple of (model, field, caller)
CountsKey = tuple[type[models.Model], str, str]


class AllowListEntry(TypedDict):
    model: str
    field: Optional[str]


def _validate_allowlist(allowlist: list[AllowListEntry]):
    for entry in allowlist:
        fnmatch_chars = "*?[]"
        # if this is an fnmatch, don't do anything
        if any(char in entry["model"] for char in fnmatch_chars):
            continue
        if entry["model"] not in ALL_APPS:
            raise ZealConfigError(
                f"Model '{entry['model']}' not found in installed Django models"
            )

        if not entry["field"]:
            continue

        if any(char in entry["field"] for char in fnmatch_chars):
            continue

        if entry["field"] not in ALL_APPS[entry["model"]]:
            raise ZealConfigError(
                f"Field '{entry['field']}' not found on '{entry['model']}'"
            )


@dataclass
class NPlusOneContext:
    enabled: bool = False
    calls: dict[CountsKey, list[list[inspect.FrameInfo]]] = field(
        default_factory=lambda: defaultdict(list)
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

    def _alert(
        self,
        model: type[models.Model],
        field: str,
        message: str,
        calls: list[list[inspect.FrameInfo]],
    ):
        should_error = (
            settings.ZEAL_RAISE if hasattr(settings, "ZEAL_RAISE") else True
        )
        should_include_all_callers = (
            settings.ZEAL_SHOW_ALL_CALLERS
            if hasattr(settings, "ZEAL_SHOW_ALL_CALLERS")
            else False
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

        final_caller = get_caller()
        if should_include_all_callers:
            message = f"{message} with calls:\n"
            for i, caller in enumerate(calls):
                message += f"CALL {i+1}:\n"
                for frame in caller:
                    message += f"  {frame.filename}:{frame.lineno} in {frame.function}\n"
        else:
            message = f"{message} at {final_caller.filename}:{final_caller.lineno} in {final_caller.function}"
        if should_error:
            raise self.error_class(message)
        else:
            warnings.warn_explicit(
                message,
                UserWarning,
                filename=final_caller.filename,
                lineno=final_caller.lineno,
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
        if not context.enabled:
            return
        caller = get_caller()
        key = (model, field, f"{caller.filename}:{caller.lineno}")
        context.calls[key].append(get_stack())
        count = len(context.calls[key])
        if count >= self._threshold and instance_key not in context.ignored:
            message = f"N+1 detected on {model._meta.app_label}.{model.__name__}.{field}"
            self._alert(model, field, message, context.calls[key])
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

    def _alert(
        self,
        model: type[models.Model],
        field: str,
        message: str,
        calls: list[list[inspect.FrameInfo]],
    ):
        super()._alert(model, field, message, calls)
        nplusone_detected.send(
            sender=self,
            exception=self.error_class(message),
        )


n_plus_one_listener = NPlusOneListener()


def setup() -> Optional[Token]:
    # if we're already in an ignore-context, we don't want to override
    # it.
    context = _nplusone_context.get()
    if hasattr(settings, "ZEAL_ALLOWLIST"):
        _validate_allowlist(settings.ZEAL_ALLOWLIST)
    return _nplusone_context.set(
        NPlusOneContext(enabled=True, allowlist=context.allowlist)
    )


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
    else:
        _validate_allowlist(allowlist)

    old_context = _nplusone_context.get()
    new_context = NPlusOneContext(
        enabled=old_context.enabled,
        calls=old_context.calls.copy(),
        ignored=old_context.ignored.copy(),
        allowlist=[*old_context.allowlist, *allowlist],
    )
    token = _nplusone_context.set(new_context)
    try:
        yield
    finally:
        _nplusone_context.reset(token)
