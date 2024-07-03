import sys

import pytest
from djangoproject.social.models import User
from zealot.listeners import zealot_context

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@zealot_context()
def test_handles_calling_queryset_many_times():
    UserFactory.create()
    user = User.objects.prefetch_related("posts").all()[0]
    for _ in range(sys.getrecursionlimit() + 1):
        # this should *not* raise a recursion error
        list(user.posts.all())
