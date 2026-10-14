import re
import warnings

import pytest
from djangoproject.social.models import Post, User
from zeal import NPlusOneError, UnusedIgnoreError, zeal_context, zeal_ignore
from zeal.errors import ZealConfigError
from zeal.listeners import (
    AllowListEntry,
    _nplusone_context,
    n_plus_one_listener,
)

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
            r"N\+1 detected on social\.User\.posts at .*\/test_listeners\.py:28 in test_can_log_errors",
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
            "tests/test_listeners.py:46 in test_can_log_all_traces",
            "CALL 2:",
            "tests/test_listeners.py:46 in test_can_log_all_traces",
        ]
        for line in expected_lines:
            assert line in str(w[0].message)


def test_errors_include_caller():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(
        NPlusOneError,
        match=r"N\+1 detected on social\.User\.posts at .*\/test_listeners\.py:69 in test_errors_include_caller",
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


@pytest.mark.nozeal
def test_allows_get_in_global_allowlist(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "social.User", "field": "get()"}]
    with zeal_context():
        pass


@pytest.mark.nozeal
def test_allows_global_allowlist_without_field_name(settings):
    settings.ZEAL_ALLOWLIST = [{"model": "social.User"}]
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


def test_allows_get_in_local_allowlist():
    with zeal_ignore([{"model": "social.User", "field": "get()"}]):
        pass


def test_get_allowlist_suppresses_nplusone_on_get():
    users = UserFactory.create_batch(2)
    with zeal_ignore([{"model": "social.User", "field": "get()"}]):
        for user in users:
            _ = User.objects.get(pk=user.pk)


def test_allows_local_allowlist_without_field_name():
    with zeal_ignore([{"model": "social.User"}]):
        pass


def test_validates_related_name_field_names():
    # User.following is a M2M field with related_name followers
    with zeal_ignore([{"model": "social.User", "field": "followers"}]):
        pass

    # User.blocked is a M2M field with an auto-generated related name (user_set)
    with zeal_ignore([{"model": "social.User", "field": "user_set"}]):
        pass


@pytest.mark.nozeal
def test_handles_zeal_ignore_when_disabled():
    with zeal_ignore([{"model": "social.User", "field": "post"}]):
        pass


@pytest.mark.parametrize("show_all", [False, True])
def test_ignore_scope_does_not_change_parent_counts(settings, show_all):
    settings.ZEAL_NPLUSONE_THRESHOLD = 3
    settings.ZEAL_SHOW_ALL_CALLERS = show_all

    def access():
        n_plus_one_listener.notify(User, "posts", None)

    access()
    with zeal_ignore():
        access()
    access()
    with pytest.raises(NPlusOneError, match="social.User.posts"):
        access()


def test_warns_about_unused_ignore_when_enabled(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    settings.ZEAL_RAISE = False
    with pytest.warns(UserWarning, match="zeal_ignore.*did not suppress") as w:
        with zeal_ignore():
            pass
    assert len(w) == 1
    assert w[0].filename == __file__


@pytest.mark.parametrize("check_unused", [False, True])
def test_unused_ignore_is_opt_in(settings, check_unused):
    settings.ZEAL_CHECK_UNUSED_IGNORES = check_unused
    if check_unused:
        with pytest.raises(UnusedIgnoreError, match="did not suppress"):
            with zeal_ignore():
                pass
    else:
        with zeal_ignore():
            pass


@pytest.mark.parametrize("accesses", [0, 1, 2, 3])
@pytest.mark.parametrize("show_all", [False, True])
def test_unused_ignore_respects_threshold(settings, accesses, show_all):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    settings.ZEAL_NPLUSONE_THRESHOLD = 3
    settings.ZEAL_SHOW_ALL_CALLERS = show_all
    UserFactory.create_batch(3)
    users = list(User.objects.all())

    def run():
        with zeal_ignore([{"model": "social.U*", "field": "post*"}]):
            for user in users[:accesses]:
                list(user.posts.all())

    if accesses < 3:
        with pytest.raises(UnusedIgnoreError):
            run()
    else:
        run()


def test_unused_ignore_with_prefetched_relations(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    UserFactory.create_batch(2)
    with pytest.raises(UnusedIgnoreError):
        with zeal_ignore():
            for user in User.objects.prefetch_related("posts"):
                list(user.posts.all())


def test_unused_ignore_with_singly_loaded_instances(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    UserFactory.create_batch(2)
    with pytest.raises(UnusedIgnoreError):
        with zeal_ignore():
            users = [User.objects.first(), User.objects.last()]
            for user in users:
                assert user is not None
                list(user.posts.all())


@pytest.mark.parametrize("global_field", ["posts", "following"])
def test_unused_ignore_accounts_for_global_allowlist(settings, global_field):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    entry: AllowListEntry = {"model": "social.User", "field": global_field}
    settings.ZEAL_ALLOWLIST = [entry]
    UserFactory.create_batch(2)

    def run():
        # Reusing a global entry must not attribute its suppression locally.
        with zeal_ignore([entry, {"model": "social.User", "field": "posts"}]):
            for user in User.objects.all():
                list(user.posts.all())

    if global_field == "posts":
        with pytest.raises(UnusedIgnoreError):
            run()
    else:
        run()


def test_redundant_inner_ignore_is_unused(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    UserFactory.create_batch(2)
    allowlist: list[AllowListEntry] = [{"model": "social.User"}]
    with zeal_ignore(allowlist):
        with pytest.raises(UnusedIgnoreError):
            with zeal_ignore(allowlist):
                for user in User.objects.all():
                    list(user.posts.all())


def test_inner_ignore_does_not_mark_unrelated_outer_ignore_used(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    UserFactory.create_batch(2)
    with pytest.raises(UnusedIgnoreError):
        with zeal_ignore([{"model": "social.Post"}]):
            with zeal_ignore([{"model": "social.User"}]):
                for user in User.objects.all():
                    list(user.posts.all())


def test_ignore_usage_survives_nested_detection_context(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    UserFactory.create_batch(2)
    with zeal_ignore(), zeal_context():
        for user in User.objects.all():
            list(user.posts.all())

    with pytest.raises(UnusedIgnoreError):
        with zeal_ignore():
            pass

    # An unused-ignore error must still restore detection outside the block.
    with pytest.raises(NPlusOneError):
        for user in User.objects.all():
            list(user.posts.all())


def test_unused_ignore_does_not_mask_exceptions(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    with pytest.raises(ValueError, match="original error"):
        with zeal_ignore():
            raise ValueError("original error")

    with pytest.raises(NPlusOneError):
        with zeal_ignore([{"model": "social.Post"}]):
            UserFactory.create_batch(2)
            for user in User.objects.all():
                list(user.posts.all())


@pytest.mark.nozeal
def test_unused_ignore_is_not_checked_when_detection_is_disabled(settings):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with zeal_ignore():
            pass
    assert not caught


@pytest.mark.nozeal
@pytest.mark.parametrize("raise_errors", [False, True])
@pytest.mark.parametrize("used", [False, True])
def test_ignore_checked_when_detection_starts_inside(
    settings, raise_errors, used
):
    settings.ZEAL_CHECK_UNUSED_IGNORES = True
    settings.ZEAL_RAISE = raise_errors
    UserFactory.create_batch(2)

    def run():
        with zeal_ignore():
            with zeal_context():
                if used:
                    for user in User.objects.all():
                        list(user.posts.all())

    if used:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            run()
        assert not caught
    elif raise_errors:
        with pytest.raises(UnusedIgnoreError):
            run()
    else:
        with pytest.warns(UserWarning, match="did not suppress"):
            run()
