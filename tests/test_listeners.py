import re
import warnings

import pytest
from djangoproject.social.models import Post, User
from zeal import NPlusOneError, zeal_context, zeal_ignore
from zeal.errors import ZealConfigError
from zeal.listeners import _nplusone_context, n_plus_one_listener

from .factories import PostFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_can_log_errors(settings, caplog):
    settings.ZEAL_RAISE = False

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        for user in User.objects.all():
            _ = list(user.posts.all())
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        assert re.search(
            r"N\+1 detected on social\.User\.posts at .*\/test_listeners\.py:24 in test_can_log_errors",
            str(w[0].message),
        )


def test_can_log_all_traces(settings):
    settings.ZEAL_SHOW_ALL_CALLERS = True
    settings.ZEAL_RAISE = False
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        for user in User.objects.all():
            _ = list(user.posts.all())
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)
        expected_lines = [
            "N+1 detected on social.User.posts with calls:",
            "CALL 1:",
            "tests/test_listeners.py:42 in test_can_log_all_traces",
            "CALL 2:",
            "tests/test_listeners.py:42 in test_can_log_all_traces",
        ]
        for line in expected_lines:
            assert line in str(w[0].message)


def test_errors_include_caller():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(
        NPlusOneError,
        match=r"N\+1 detected on social\.User\.posts at .*\/test_listeners\.py:65 in test_errors_include_caller",
    ):
        for user in User.objects.all():
            _ = list(user.posts.all())


def test_can_exclude_with_allowlist(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "social.User", "field": "posts"}]

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this will not raise, allow-listed
    for user in User.objects.all():
        _ = list(user.posts.all())

    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Post.author")
    ):
        for post in Post.objects.all():
            _ = post.author


def test_can_use_fnmatch_pattern_in_allowlist_model(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "social.U*"}]

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this will not raise, allow-listed
    for user in User.objects.all():
        _ = list(user.posts.all())

    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Post.author")
    ):
        for post in Post.objects.all():
            _ = post.author


def test_can_use_fnmatch_pattern_in_allowlist_field(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "social.User", "field": "p*st*"}]

    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this will not raise, allow-listed
    for user in User.objects.all():
        _ = list(user.posts.all())

    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Post.author")
    ):
        for post in Post.objects.all():
            _ = post.author


def test_ignore_context_takes_precedence():
    """
    If you're within a `zeal_ignore` context, then even if some later code adds
    a zeal context, then the ignore context should take precedence.
    """
    with zeal_ignore():
        with zeal_context():
            [user_1, user_2] = UserFactory.create_batch(2)
            PostFactory.create(author=user_1)
            PostFactory.create(author=user_2)

            # this will not raise because we're in the zeal_ignore context
            for user in User.objects.all():
                _ = list(user.posts.all())


def test_reverts_to_previous_state_when_leaving_zeal_ignore():
    # we are currently in a zeal context
    initial_context = _nplusone_context.get()
    with zeal_ignore():
        assert _nplusone_context.get().allowlist == [
            {"model": "*", "field": "*"}
        ]
    assert _nplusone_context.get() == initial_context


def test_resets_state_in_nested_context():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # we're already in a zeal_context within each test, so let's set
    # some state.
    n_plus_one_listener.ignore("Test:1")
    n_plus_one_listener.notify(Post, "test_field", "Post:1")

    context = _nplusone_context.get()
    assert context.ignored == {"Test:1"}
    assert len(context.calls.values()) == 1
    caller = list(context.calls.values())[0]

    with zeal_context():
        # new context, fresh state
        context = _nplusone_context.get()
        assert context.ignored == set()
        assert list(context.calls.values()) == []

        n_plus_one_listener.ignore("NestedTest:1")
        n_plus_one_listener.notify(Post, "nested_test_field", "Post:1")

        context = _nplusone_context.get()
        assert context.ignored == {"NestedTest:1"}
        assert len(list(context.calls.values())) == 1

    # back outside the nested context, we're back to the old state
    context = _nplusone_context.get()
    assert context.ignored == {"Test:1"}
    assert list(context.calls.values()) == [caller]


def test_can_ignore_specific_models():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    with zeal_ignore([{"model": "social.User", "field": "post*"}]):
        # this will not raise, allow-listed
        for user in User.objects.all():
            _ = list(user.posts.all())

        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.Post.author"),
        ):
            # this is *not* allowlisted
            for post in Post.objects.all():
                _ = post.author

    # if we ignore another field, we still raise
    with zeal_ignore([{"model": "social.User", "field": "following"}]):
        with pytest.raises(
            NPlusOneError, match=re.escape("N+1 detected on social.User.posts")
        ):
            for user in User.objects.all():
                _ = list(user.posts.all())

    # outside of the context, we're back to normal
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.posts")
    ):
        for user in User.objects.all():
            _ = list(user.posts.all())


def test_context_specific_allowlist_merges():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    with zeal_ignore([{"model": "social.User", "field": "post*"}]):
        # this will not raise, allow-listed
        for user in User.objects.all():
            _ = list(user.posts.all())

        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.Post.author"),
        ):
            # this is *not* allowlisted
            for post in Post.objects.all():
                _ = post.author

        with zeal_ignore([{"model": "social.Post", "field": "author"}]):
            for post in Post.objects.all():
                _ = post.author

            # this is still allowlisted
            for user in User.objects.all():
                _ = list(user.posts.all())


# other tests automatically run in a zeal context, so we need to disable
# that here.
@pytest.mark.nozeal
def test_does_not_run_outside_of_context():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this should not raise since we are outside of a zeal context
    for user in User.objects.all():
        _ = list(user.posts.all())

    with zeal_context(), pytest.raises(NPlusOneError):
        # this should raise since we are inside a zeal context
        for user in User.objects.all():
            _ = list(user.posts.all())


@pytest.mark.nozeal
def test_validates_global_allowlist_model_name(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "foo", "field": "*"}]
    with pytest.raises(
        ZealConfigError,
        match=re.escape("Model 'foo' not found in installed Django models"),
    ):
        with zeal_context():
            pass


@pytest.mark.nozeal
def test_validates_global_allowlist_field_name(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "social.User", "field": "foo"}]
    with pytest.raises(
        ZealConfigError,
        match=re.escape("Field 'foo' not found on 'social.User'"),
    ):
        with zeal_context():
            pass


@pytest.mark.nozeal
def test_allows_fnmatch_in_global_allowlist(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "social.U[sb]er", "field": "p?st"}]
    with zeal_context():
        pass


def test_validates_local_allowlist_model_name():
    with pytest.raises(
        ZealConfigError,
        match=re.escape("Model 'foo' not found in installed Django models"),
    ):
        with zeal_ignore([{"model": "foo", "field": "*"}]):
            pass


def test_validates_local_allowlist_field_name():
    with pytest.raises(
        ZealConfigError,
        match=re.escape("Field 'foo' not found on 'social.User'"),
    ):
        with zeal_ignore([{"model": "social.User", "field": "foo"}]):
            pass


def test_allows_fnmatch_in_local_allowlist():
    with zeal_ignore([{"model": "social.U[sb]er", "field": "p?st"}]):
        pass


def test_validates_related_name_field_names():
    # User.following is a M2M field with related_name followers
    with zeal_ignore([{"model": "social.User", "field": "followers"}]):
        pass

    # User.blocked is a M2M field with an auto-generated related name (user_set)
    with zeal_ignore([{"model": "social.User", "field": "user_set"}]):
        pass
