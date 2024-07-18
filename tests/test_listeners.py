import logging
import re

import pytest
from djangoproject.social.models import Post, User
from zealot import NPlusOneError, zealot_context, zealot_ignore
from zealot.listeners import _nplusone_context, n_plus_one_listener

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


def test_reverts_to_previous_state_when_leaving_zealot_ignore():
    # we are currently in a zealot context
    assert _nplusone_context.get().is_in_context is True
    with zealot_ignore():
        assert _nplusone_context.get().is_in_context is False
    assert _nplusone_context.get().is_in_context is True

    # if we start off *without* being in a context, that also gets reset
    context = _nplusone_context.get()
    context.is_in_context = None
    _nplusone_context.set(context)

    assert _nplusone_context.get().is_in_context is None
    with zealot_ignore():
        assert _nplusone_context.get().is_in_context is False
    assert _nplusone_context.get().is_in_context is None


def test_resets_state_in_nested_context():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # we're already in a zealot_context within each test, so let's set
    # some state.
    n_plus_one_listener.ignore("Test:1")
    n_plus_one_listener.notify(Post, "test_field", "Post:1")

    context = _nplusone_context.get()
    assert context.ignored == {"Test:1"}
    assert list(context.counts.values()) == [1]

    with zealot_context():
        # new context, fresh state
        context = _nplusone_context.get()
        assert context.ignored == set()
        assert list(context.counts.values()) == []

        n_plus_one_listener.ignore("NestedTest:1")
        n_plus_one_listener.notify(Post, "nested_test_field", "Post:1")

        context = _nplusone_context.get()
        assert context.ignored == {"NestedTest:1"}
        assert list(context.counts.values()) == [1]

    # back outside the nested context, we're back to the old state
    context = _nplusone_context.get()
    assert context.ignored == {"Test:1"}
    assert list(context.counts.values()) == [1]
