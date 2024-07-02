import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Type

from django.conf import settings
from django.db import models

from .errors import NPlusOneError

ModelAndField = tuple[Type[models.Model], str]

_is_in_context = ContextVar("in_context", default=False)

logger = logging.getLogger("queryspy")


class Listener(ABC):
    @abstractmethod
    def notify(self, *args, **kwargs): ...

    @abstractmethod
    def reset(self): ...

    @property
    def _should_error(self) -> bool:
        if hasattr(settings, "QUERYSPY_RAISE"):
            return settings.QUERYSPY_RAISE
        else:
            return True


class NPlusOneListener(Listener):
    counts: dict[ModelAndField, int]

    def __init__(self):
        self.reset()

    def notify(self, model: Type[models.Model], field: str):
        if not _is_in_context.get():
            return

        key = (model, field)
        self.counts[key] += 1
        count = self.counts[key]
        if count >= self._threshold:
            message = f"N+1 detected on {model.__name__}.{field}"
            if self._should_error:
                raise NPlusOneError(message)
            else:
                logger.warning(message)

    def reset(self):
        self.counts = defaultdict(int)

    @property
    def _threshold(self) -> int:
        if hasattr(settings, "QUERYSPY_NPLUSONE_THRESHOLD"):
            return settings.QUERYSPY_NPLUSONE_THRESHOLD
        else:
            return 2


n_plus_one_listener = NPlusOneListener()


def setup():
    _is_in_context.set(True)


def teardown():
    n_plus_one_listener.reset()
    _is_in_context.set(False)


@contextmanager
def queryspy_context():
    token = _is_in_context.set(True)
    try:
        yield
    finally:
        n_plus_one_listener.reset()
        _is_in_context.reset(token)


@contextmanager
def queryspy_ignore():
    token = _is_in_context.set(False)
    try:
        yield
    finally:
        _is_in_context.reset(token)
