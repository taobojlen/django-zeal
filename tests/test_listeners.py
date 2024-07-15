import logging
import re

import pytest
from djangoproject.social.models import Post, User
from zealot import zealot_context, zealot_ignore
from zealot.errors import NPlusOneError

from .factories import PostFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_can_log_errors(settings, caplog):
    settings.ZEALOT_RAISE = False

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with caplog.at_level(logging.WARNING):
        for user in User.objects.all():
            _ = list(user.posts.all())
        assert (
            re.search(
                r"N\+1 detected on User\.posts at .*\/test_listeners\.py:22 in test_can_log_errors",
                caplog.text,
            )
            is not None
        ), f"{caplog.text} does not match regex"


def test_errors_include_caller():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(
        NPlusOneError,
        match=r"N\+1 detected on User\.posts at .*\/test_listeners\.py:41 in test_errors_include_caller",
    ):
        for user in User.objects.all():
            _ = list(user.posts.all())


def test_can_exclude_with_allowlist(settings):
    settings.ZEALOT_ALLOWLIST = [{"model": "social.User", "field": "posts"}]

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this will not raise, allow-listed
    for user in User.objects.all():
        _ = list(user.posts.all())

    with pytest.raises(NPlusOneError):
        for post in Post.objects.all():
            _ = post.author


def test_can_use_fnmatch_pattern_in_allowlist_model(settings):
    settings.ZEALOT_ALLOWLIST = [{"model": "social.U*"}]

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this will not raise, allow-listed
    for user in User.objects.all():
        _ = list(user.posts.all())

    with pytest.raises(NPlusOneError):
        for post in Post.objects.all():
            _ = post.author


def test_can_use_fnmatch_pattern_in_allowlist_field(settings):
    settings.ZEALOT_ALLOWLIST = [{"model": "social.User", "field": "p*st*"}]

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this will not raise, allow-listed
    for user in User.objects.all():
        _ = list(user.posts.all())

    with pytest.raises(NPlusOneError):
        for post in Post.objects.all():
            _ = post.author


def test_ignore_context_takes_precedence():
    """
    If you're within a `zealot_ignore` context, then even if some later code adds
    a zealot context, then the ignore context should take precedence.
    """
    with zealot_ignore():
        with zealot_context():
            [user_1, user_2] = UserFactory.create_batch(2)
            PostFactory.create(author=user_1)
            PostFactory.create(author=user_2)

            # this will not raise because we're in the zealot_ignore context
            for user in User.objects.all():
                _ = list(user.posts.all())


def test_ignores_calls_on_different_lines():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this should *not* raise an exception
    _a = list(user_1.posts.all())
    _b = list(user_2.posts.all())
