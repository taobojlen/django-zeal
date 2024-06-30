from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Type

from django.conf import settings
from django.db import models

from .errors import NPlusOneError

ModelAndField = tuple[Type[models.Model], str]


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
        threshold = (
            settings.QUERYSPY_NPLUSONE_THRESHOLD
            if hasattr(settings, "QUERYSPY_NPLUSONE_THRESHOLD")
            else 2
        )

        key = (model, field)
        self.counts[key] += 1
        count = self.counts[key]
        if count >= threshold:
            raise NPlusOneError("BAD!")

    def reset(self):
        self.counts = defaultdict(int)


n_plus_one_listener = NPlusOneListener()


def reset():
    n_plus_one_listener.reset()
