import sys

import pytest
from djangoproject.social.models import User

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_handles_calling_queryset_many_times():
    UserFactory.create()
    user = User.objects.prefetch_related("posts").all()[0]
    for _ in range(sys.getrecursionlimit() + 1):
        # this should *not* raise a recursion error
        list(user.posts.all())


def test_handles_empty_querysets():
    User.objects.none().first()


def test_handles_get_with_values():
    user = UserFactory.create()
    User.objects.filter(pk=user.pk).values("username").get()
