import logging

import pytest
from djangoproject.social.models import User
from queryspy.listeners import queryspy_context

from .factories import PostFactory, UserFactory

pytestmark = pytest.mark.django_db


@queryspy_context()
def test_can_log_errors(settings, caplog):
    settings.QUERYSPY_RAISE = False

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with caplog.at_level(logging.WARNING):
        for user in User.objects.all():
            _ = list(user.posts.all())
        assert "N+1 detected on User.posts" in caplog.text
