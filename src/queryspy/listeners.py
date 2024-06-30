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


class Listener(ABC):
    @abstractmethod
    def notify(self, *args, **kwargs): ...

    @abstractmethod
    def reset(self): ...


class NPlusOneListener(Listener):
    counts: dict[ModelAndField, int]
    threshold: int

    def __init__(self):
        self.reset()

    def notify(self, model: Type[models.Model], field: str):
        if not _is_in_context.get():
            return

        threshold = (
            settings.QUERYSPY_NPLUSONE_THRESHOLD
            if hasattr(settings, "QUERYSPY_NPLUSONE_THRESHOLD")
            else 2
        )

        key = (model, field)
        self.counts[key] += 1
        count = self.counts[key]
        if count >= threshold:
            raise NPlusOneError(f"N+1 detected on {model.__name__}.{field}")

    def reset(self):
        self.counts = defaultdict(int)


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
