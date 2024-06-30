from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Type

from django.db import models

from .errors import NPlusOneError

ModelAndField = tuple[Type[models.Model], str]
THRESHOLD = 2


class Listener(ABC):
    @abstractmethod
    def notify(self, *args, **kwargs): ...


class NPlusOneListener(Listener):
    counts: dict[ModelAndField, int]

    def __init__(self):
        self.counts = defaultdict(int)

    def notify(self, model: Type[models.Model], field: str):
        key = (model, field)
        self.counts[key] += 1
        count = self.counts[key]
        if count >= THRESHOLD:
            raise NPlusOneError("BAD!")


n_plus_one_listener = NPlusOneListener()
