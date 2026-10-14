import re
import warnings

import django
import pytest
from django.contrib.auth.models import User as AuthUser
from django.db import connection
from django.db.models import Model, QuerySet, prefetch_related_objects
from django.test.utils import CaptureQueriesContext
from djangoproject.social.models import Post, Profile, User
from zeal import NPlusOneError, zeal_context
from zeal.listeners import zeal_ignore

from .factories import PostFactory, ProfileFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_detects_nplusone_in_forward_many_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Post.author")
    ):
        for post in Post.objects.all():
            _ = post.author.username

    for post in Post.objects.select_related("author").all():
        _ = post.author.username


def test_detects_nplusone_in_forward_many_to_one_iterator():
    for _ in range(4):
        user = UserFactory.create()
        PostFactory.create(author=user)

    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Post.author")
    ):
        for post in Post.objects.all().iterator(chunk_size=2):
            _ = post.author.username

    for post in Post.objects.select_related("author").iterator(chunk_size=2):
        _ = post.author.username


def test_handles_prefetch_instead_of_select_related_in_forward_many_to_one():
    user_1, user_2 = UserFactory.create_batch(2)
    PostFactory(author=user_1)
    PostFactory(author=user_2)
    with CaptureQueriesContext(connection) as ctx:
        # this should be a select_related! but we need to handle it even if someone
        # has accidentally used the wrong method.
        for post in Post.objects.prefetch_related("author").all():
            _ = post.author.username
        assert len(ctx.captured_queries) == 2


def test_no_false_positive_when_loading_single_object_forward_many_to_one():
    user = UserFactory.create()
    post_1, post_2 = PostFactory.create_batch(2, author=user)

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        post_1 = Post.objects.filter(pk=post_1.pk).first()
        post_2 = Post.objects.filter(pk=post_2.pk).first()
        assert post_1 is not None and post_2 is not None
        # queries on `post` should not raise an exception, because `post` was
        # singly-loaded
        _ = post_1.author
        _ = post_2.author
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        # same when using a slice to get a single record
        post_1 = Post.objects.filter(pk=post_1.pk).all()[0]
        post_2 = Post.objects.filter(pk=post_2.pk).all()[0]
        _ = post_1.author
        _ = post_2.author
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        # similarly, when using `.get()`, no N+1 error
        post_1 = Post.objects.get(pk=post_1.pk)
        post_2 = Post.objects.get(pk=post_2.pk)
        _ = post_1.author
        _ = post_2.author
        assert len(ctx.captured_queries) == 4


def test_detects_nplusone_in_reverse_many_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.posts")
    ):
        for user in User.objects.all():
            _ = list(user.posts.all())

    for user in User.objects.prefetch_related("posts").all():
        _ = list(user.posts.all())


def test_detects_nplusone_in_reverse_many_to_one_iterator():
    for _ in range(4):
        user = UserFactory.create()
        PostFactory.create(author=user)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.posts")
    ):
        for user in User.objects.all().iterator(chunk_size=2):
            _ = list(user.posts.all())

    for user in User.objects.prefetch_related("posts").iterator(chunk_size=2):
        _ = list(user.posts.all())


def test_no_false_positive_when_calling_reverse_many_to_one_twice():
    user = UserFactory.create()
    PostFactory.create(author=user)

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        queryset = user.posts.all()
        list(queryset)  # evaluate queryset once
        list(queryset)  # evalute again (cached)
        assert len(ctx.captured_queries) == 1


def test_detects_nplusone_in_forward_one_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Profile.user")
    ):
        for profile in Profile.objects.all():
            _ = profile.user.username

    for profile in Profile.objects.select_related("user").all():
        _ = profile.user.username


def test_detects_nplusone_in_forward_one_to_one_iterator():
    for _ in range(4):
        user = UserFactory.create()
        ProfileFactory.create(user=user)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Profile.user")
    ):
        for profile in Profile.objects.all().iterator(chunk_size=2):
            _ = profile.user.username

    for profile in Profile.objects.select_related("user").iterator(
        chunk_size=2
    ):
        _ = profile.user.username


def test_handles_prefetch_instead_of_select_related_in_forward_one_to_one():
    user_1, user_2 = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)
    with CaptureQueriesContext(connection) as ctx:
        # this should be a select_related! but we need to handle it even if someone
        # has accidentally used the wrong method.
        for profile in Profile.objects.prefetch_related("user").all():
            _ = profile.user.username
        assert len(ctx.captured_queries) == 2


def test_no_false_positive_when_loading_single_object_forward_one_to_one():
    user_1, user_2 = UserFactory.create_batch(2)
    profile_1 = ProfileFactory.create(user=user_1)
    profile_2 = ProfileFactory.create(user=user_2)

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        profile_1 = Profile.objects.filter(pk=profile_1.pk).first()
        profile_2 = Profile.objects.filter(pk=profile_2.pk).first()
        assert profile_1 is not None and profile_2 is not None
        _ = profile_1.user.username
        _ = profile_2.user.username
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        profile_1 = Profile.objects.filter(pk=profile_1.pk)[0]
        profile_2 = Profile.objects.filter(pk=profile_2.pk)[0]
        _ = profile_1.user.username
        _ = profile_2.user.username
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        profile_1 = Profile.objects.get(pk=profile_1.pk)
        profile_2 = Profile.objects.get(pk=profile_2.pk)
        _ = profile_1.user.username
        _ = profile_2.user.username
        assert len(ctx.captured_queries) == 4


def test_detects_nplusone_in_reverse_one_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.profile")
    ):
        for user in User.objects.all():
            _ = user.profile.display_name

    for user in User.objects.select_related("profile").all():
        _ = user.profile.display_name


def test_detects_nplusone_in_reverse_one_to_one_iterator():
    for _ in range(4):
        user = UserFactory.create()
        ProfileFactory.create(user=user)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.profile")
    ):
        for user in User.objects.all().iterator(chunk_size=2):
            _ = user.profile.display_name

    for user in User.objects.select_related("profile").iterator(chunk_size=2):
        _ = user.profile.display_name


def test_handles_prefetch_instead_of_select_related_in_reverse_one_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)

    with CaptureQueriesContext(connection) as ctx:
        # this should be a select_related! but we need to handle it even if someone
        # has accidentally used the wrong method.
        for user in User.objects.prefetch_related("profile").all():
            _ = user.profile.display_name
        assert len(ctx.captured_queries) == 2


def test_no_false_positive_when_loading_single_object_reverse_one_to_one():
    user_1, user_2 = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        user_1 = User.objects.filter(pk=user_1.pk).first()
        user_2 = User.objects.filter(pk=user_2.pk).first()
        assert user_1 is not None and user_2 is not None
        _ = user_1.profile.display_name
        _ = user_2.profile.display_name
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        user_1 = User.objects.filter(pk=user_1.pk)[0]
        user_2 = User.objects.filter(pk=user_2.pk)[0]
        _ = user_1.profile.display_name
        _ = user_2.profile.display_name
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        user_1 = User.objects.get(pk=user_1.pk)
        user_2 = User.objects.get(pk=user_2.pk)
        _ = user_1.profile.display_name
        _ = user_2.profile.display_name
        assert len(ctx.captured_queries) == 4


def test_detects_nplusone_in_forward_many_to_many():
    [user_1, user_2] = UserFactory.create_batch(2)
    user_1.following.add(user_2)
    user_2.following.add(user_1)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.following")
    ):
        for user in User.objects.all():
            _ = list(user.following.all())

    for user in User.objects.prefetch_related("following").all():
        _ = list(user.following.all())


def test_detects_nplusone_in_forward_many_to_many_iterator():
    influencer = UserFactory.create()
    users = UserFactory.create_batch(4)
    influencer.followers.set(users)  # type: ignore

    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.following")
    ):
        for user in User.objects.iterator(chunk_size=2):
            _ = list(user.following.all())

    for user in User.objects.prefetch_related("following").iterator(
        chunk_size=2
    ):
        _ = list(user.following.all())


def test_no_false_positive_when_loading_single_object_forward_many_to_many():
    user_1, user_2 = UserFactory.create_batch(2)
    user_1.following.add(user_2)
    user_2.following.add(user_1)

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        _ = user_1.following.first().username
        _ = user_2.following.first().username
        assert len(ctx.captured_queries) == 2

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        _ = user_1.following.all()[0].username
        _ = user_2.following.all()[0].username
        assert len(ctx.captured_queries) == 2

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        _ = user_1.following.get(pk=user_2.pk).username
        _ = user_2.following.get(pk=user_1.pk).username
        assert len(ctx.captured_queries) == 2


def test_detects_nplusone_in_reverse_many_to_many():
    [user_1, user_2] = UserFactory.create_batch(2)
    user_1.following.add(user_2)
    user_2.following.add(user_1)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.followers")
    ):
        for user in User.objects.all():
            _ = list(user.followers.all())

    for user in User.objects.prefetch_related("followers").all():
        _ = list(user.followers.all())


def test_detects_nplusone_in_reverse_many_to_many_iterator():
    follower = UserFactory.create()
    users = UserFactory.create_batch(4)
    follower.following.set(users)  # type: ignore
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.followers")
    ):
        for user in User.objects.all().iterator(chunk_size=2):
            _ = list(user.followers.all())

    for user in (
        User.objects.prefetch_related("followers").all().iterator(chunk_size=2)
    ):
        _ = list(user.followers.all())


def test_no_false_positive_when_loading_single_object_reverse_many_to_many():
    user_1, user_2 = UserFactory.create_batch(2)
    user_1.following.add(user_2)
    user_2.following.add(user_1)

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        _ = user_1.followers.first().username
        _ = user_2.followers.first().username
        assert len(ctx.captured_queries) == 2

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        _ = user_1.followers.all()[0].username
        _ = user_2.followers.all()[0].username
        assert len(ctx.captured_queries) == 2

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        _ = user_1.followers.get(pk=user_2.pk).username
        _ = user_2.followers.get(pk=user_1.pk).username
        assert len(ctx.captured_queries) == 2


def test_detects_nplusone_in_forward_many_to_many_with_no_related_name():
    [user_1, user_2] = UserFactory.create_batch(2)
    user_1.blocked.add(user_2)
    user_2.blocked.add(user_1)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.blocked")
    ):
        for user in User.objects.all():
            _ = list(user.blocked.all())

    for user in User.objects.prefetch_related("blocked").all():
        _ = list(user.blocked.all())


def test_detects_nplusone_in_reverse_many_to_many_with_no_related_name():
    [user_1, user_2] = UserFactory.create_batch(2)
    user_1.blocked.add(user_2)
    user_2.blocked.add(user_1)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.user_set")
    ):
        for user in User.objects.all():
            _ = list(user.user_set.all())

    for user in User.objects.prefetch_related("user_set").all():
        _ = list(user.user_set.all())


def test_detects_nplusone_due_to_deferred_fields():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.username")
    ):
        for post in (
            Post.objects.all().select_related("author").only("author__id")
        ):
            _ = post.author.username

    for post in (
        Post.objects.all().select_related("author").only("author__username")
    ):
        _ = post.author.username


@pytest.mark.parametrize("clone", [False, True])
@pytest.mark.parametrize("load", ["bulk", "get", "first", "slice"])
def test_deferred_refresh_preserves_detection(
    settings, monkeypatch, clone, load
):
    settings.ZEAL_RAISE = False
    settings.ZEAL_ALLOWLIST = [{"model": "social.Post", "field": "text"}]
    authors = [UserFactory.create(username=f"author-{i}") for i in range(2)]
    created = [
        PostFactory.create(author=author, text=f"text-{i}")
        for i, author in enumerate(authors)
    ]

    class RefreshQuerySet(QuerySet):
        def get(self, *args, **kwargs):
            if clone:
                self = self.order_by("pk").all()
            return super().get(*args, **kwargs)

    manager = RefreshQuerySet.as_manager()
    manager.model = Post
    monkeypatch.setattr(Post._meta, "base_manager", manager)

    with zeal_context(), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        qs = Post.objects.defer("text").order_by("pk")
        if load == "bulk":
            posts = list(qs)
        elif load == "get":
            first = qs.get(pk=created[0].pk)
            second = qs.get(pk=created[1].pk)
            posts = [first, second]
        elif load == "first":
            posts = [qs.filter(pk=post.pk).first() for post in created]
        else:
            posts = [qs.filter(pk=post.pk)[0] for post in created]
        assert all(post is not None for post in posts)
        with CaptureQueriesContext(connection) as queries:
            assert [post.text for post in posts if post is not None] == [
                "text-0",
                "text-1",
            ]
        assert len(queries) == 2
        assert not caught
        with CaptureQueriesContext(connection) as queries:
            assert [
                post.author.username for post in posts if post is not None
            ] == ["author-0", "author-1"]
        assert len(queries) == 2
        assert len(caught) == (1 if load == "bulk" else 0)
        if caught:
            assert "social.Post.author" in str(caught[0].message)


@pytest.mark.parametrize("when", ["before", "after"])
@pytest.mark.parametrize("same_model", [False, True])
def test_deferred_refresh_override_get_is_detected(
    settings, monkeypatch, when, same_model
):
    settings.ZEAL_RAISE = False
    settings.ZEAL_ALLOWLIST = [{"model": "social.Post", "field": "text"}]
    for i in range(2):
        author = UserFactory.create(username=f"author-{i}")
        PostFactory.create(author=author, text=f"text-{i}")

    def unrelated_get(post):
        if same_model:
            return Post.objects.get(pk=post.pk)
        return User.objects.get(pk=post.author_id)

    def refresh(self, *args, **kwargs):
        if when == "before":
            unrelated_get(self)
        Model.refresh_from_db(self, *args, **kwargs)
        if when == "after":
            unrelated_get(self)

    monkeypatch.setattr(Post, "refresh_from_db", refresh)
    with zeal_context(), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        posts = list(Post.objects.defer("text").order_by("pk"))
        assert [post.text for post in posts] == ["text-0", "text-1"]
    assert len(caught) == 1
    model = "Post" if same_model else "User"
    assert f"social.{model}.get()" in str(caught[0].message)


@pytest.mark.parametrize("copy_hints", [False, True])
@pytest.mark.parametrize("access", ["deferred", "explicit", "from_queryset"])
def test_refresh_clones_preserve_unrelated_get_detection(
    settings, monkeypatch, copy_hints, access
):
    if access == "from_queryset" and django.VERSION < (5, 1):
        pytest.skip("refresh_from_db(from_queryset=...) requires Django 5.1")
    settings.ZEAL_RAISE = False
    settings.ZEAL_ALLOWLIST = [{"model": "social.Post", "field": "text"}]
    created = [
        PostFactory.create(
            author=UserFactory.create(username=f"author-{i}"),
            text=f"text-{i}",
        )
        for i in range(3)
    ]

    class RefreshQuerySet(QuerySet):
        def get(self, *args, **kwargs):
            hints = self._hints if copy_hints else {}  # type: ignore
            unrelated = Post.objects.db_manager(hints=hints).get(
                pk=created[2].pk
            )
            assert unrelated.text == "text-2"
            self = self.order_by("pk").all()
            return super().get(*args, **kwargs)

    manager = RefreshQuerySet.as_manager()
    manager.model = Post
    monkeypatch.setattr(Post._meta, "base_manager", manager)

    with zeal_context(), warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        qs = Post.objects.filter(pk__in=[post.pk for post in created[:2]])
        if access == "deferred":
            qs = qs.defer("text")
        posts = list(qs.order_by("pk"))
        with CaptureQueriesContext(connection) as queries:
            if access == "explicit":
                for post in posts:
                    post.refresh_from_db(fields=["text"])
            elif access == "from_queryset":
                for post in posts:
                    post.refresh_from_db(
                        fields=["text"],
                        from_queryset=RefreshQuerySet(model=Post),
                    )
            assert [post.text for post in posts] == ["text-0", "text-1"]
        assert len(queries) == 4
        assert len(caught) == 1
        assert "social.Post.get()" in str(caught[0].message)
        with CaptureQueriesContext(connection) as queries:
            assert [post.author.username for post in posts] == [
                "author-0",
                "author-1",
            ]
        assert len(queries) == 2
        assert len(caught) == 2
        assert "social.Post.author" in str(caught[1].message)


def test_detects_nplusone_due_to_deferred_fields_in_iterator():
    for _ in range(4):
        user = UserFactory.create()
        PostFactory.create(author=user)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.username")
    ):
        for post in (
            Post.objects.all()
            .select_related("author")
            .only("author__id")
            .iterator(chunk_size=2)
        ):
            _ = post.author.username

    for post in (
        Post.objects.all()
        .select_related("author")
        .only("author__username")
        .iterator(chunk_size=2)
    ):
        _ = post.author.username


def test_handles_prefetch_instead_of_select_related_with_deferred_fields():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    with CaptureQueriesContext(connection) as ctx:
        # this should be a select_related! but we need to handle it even if someone
        # has accidentally used the wrong method.
        for post in (
            Post.objects.all()
            .prefetch_related("author")
            .only("author__username")
        ):
            _ = post.author.username
        assert len(ctx.captured_queries) == 2


def test_has_configurable_threshold(settings):
    settings.ZEAL_NPLUSONE_THRESHOLD = 3
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    for post in Post.objects.all():
        _ = post.author.username


@zeal_ignore()
def test_does_nothing_if_not_in_middleware(settings, client):
    settings.MIDDLEWARE = []
    [user_1, user_2] = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)

    # this does not raise an N+1 error even though the same
    # related field gets hit twice
    response = client.get(f"/user/{user_1.pk}/")
    assert response.status_code == 200
    response = client.get(f"/user/{user_2.pk}/")
    assert response.status_code == 200


def test_works_in_web_requests(client):
    [user_1, user_2] = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)
    with pytest.raises(
        NPlusOneError, match=re.escape(r"N+1 detected on social.User.profile")
    ):
        response = client.get("/users/")

    # but multiple requests work fine
    response = client.get(f"/user/{user_1.pk}/")
    assert response.status_code == 200
    response = client.get(f"/user/{user_2.pk}/")
    assert response.status_code == 200


def test_detects_nplusone_on_get():
    users = UserFactory.create_batch(2)
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.get()")
    ):
        for user in users:
            _ = User.objects.get(pk=user.pk)


def test_no_false_positive_on_get_on_different_lines():
    users = UserFactory.create_batch(2)
    # .get() on different lines should not trigger N+1
    _ = User.objects.get(pk=users[0].pk)
    _ = User.objects.get(pk=users[1].pk)


def test_ignores_calls_on_different_lines():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this should *not* raise an exception
    _a = list(user_1.posts.all())
    _b = list(user_2.posts.all())


class TestPrefetchRelatedObjects:
    """prefetch_related_objects called per-instance is N+1; bulk is not."""

    def test_reverse_many_to_one_per_instance_is_n_plus_one(self):
        users = UserFactory.create_batch(2)
        for u in users:
            PostFactory.create(author=u)
        users = list(User.objects.all())
        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.User.posts"),
        ):
            for user in users:
                prefetch_related_objects([user], "posts")

    def test_forward_many_to_one_per_instance_is_n_plus_one(self):
        users = UserFactory.create_batch(2)
        for u in users:
            PostFactory.create(author=u)
        posts = list(Post.objects.all())
        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.Post.author"),
        ):
            for post in posts:
                prefetch_related_objects([post], "author")

    def test_reverse_one_to_one_per_instance_is_n_plus_one(self):
        users = UserFactory.create_batch(2)
        for u in users:
            ProfileFactory.create(user=u)
        users = list(User.objects.all())
        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.User.profile"),
        ):
            for user in users:
                prefetch_related_objects([user], "profile")

    def test_forward_many_to_many_per_instance_is_n_plus_one(self):
        user_1, user_2 = UserFactory.create_batch(2)
        user_1.following.add(user_2)
        user_2.following.add(user_1)
        users = list(User.objects.all())
        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.User.following"),
        ):
            for user in users:
                prefetch_related_objects([user], "following")

    def test_reverse_many_to_many_per_instance_is_n_plus_one(self):
        user_1, user_2 = UserFactory.create_batch(2)
        user_1.following.add(user_2)
        user_2.following.add(user_1)
        users = list(User.objects.all())
        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.User.followers"),
        ):
            for user in users:
                prefetch_related_objects([user], "followers")

    def test_generic_relation_per_instance_is_n_plus_one(self):
        from djangoproject.social.models import Tag

        users = UserFactory.create_batch(2)
        for u in users:
            Tag.objects.create(obj=u, label="x")
        users = list(User.objects.all())
        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.User.tags"),
        ):
            for user in users:
                prefetch_related_objects([user], "tags")

    def test_per_instance_in_iterator_loop_is_n_plus_one(self):
        users = UserFactory.create_batch(2)
        for u in users:
            PostFactory.create(author=u)
        with pytest.raises(
            NPlusOneError,
            match=re.escape("N+1 detected on social.User.posts"),
        ):
            for user in User.objects.iterator(chunk_size=1):
                prefetch_related_objects([user], "posts")

    def test_bulk_is_not_n_plus_one(self):
        users = UserFactory.create_batch(2)
        for u in users:
            PostFactory.create(author=u)
        users = list(User.objects.all())
        prefetch_related_objects(users, "posts")

    def test_singly_loaded_prefetch_is_not_n_plus_one(self):
        user_1, user_2 = UserFactory.create_batch(2)
        PostFactory.create(author=user_1)
        PostFactory.create(author=user_2)

        def prefetch_one(user):
            prefetch_related_objects([user], "posts")

        prefetch_one(User.objects.get(pk=user_1.pk))
        prefetch_one(User.objects.get(pk=user_2.pk))


def test_detects_nplusone_in_generic_relation():
    from djangoproject.social.models import Tag

    [user_1, user_2] = UserFactory.create_batch(2)
    Tag.objects.create(obj=user_1, label="a")
    Tag.objects.create(obj=user_2, label="b")
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.tags")
    ):
        for user in User.objects.all():
            _ = list(user.tags.all())

    for user in User.objects.prefetch_related("tags").all():
        _ = list(user.tags.all())


def test_detects_nplusone_in_generic_relation_iterator():
    from djangoproject.social.models import Tag

    for _ in range(4):
        user = UserFactory.create()
        Tag.objects.create(obj=user, label="x")
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.User.tags")
    ):
        for user in User.objects.all().iterator(chunk_size=2):
            _ = list(user.tags.all())

    for user in User.objects.prefetch_related("tags").iterator(chunk_size=2):
        _ = list(user.tags.all())


def test_no_false_positive_when_loading_single_object_generic_relation():
    from djangoproject.social.models import Tag

    user_1, user_2 = UserFactory.create_batch(2)
    Tag.objects.create(obj=user_1, label="a")
    Tag.objects.create(obj=user_2, label="b")

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        user_1 = User.objects.filter(pk=user_1.pk).first()
        user_2 = User.objects.filter(pk=user_2.pk).first()
        assert user_1 is not None and user_2 is not None
        _ = list(user_1.tags.all())
        _ = list(user_2.tags.all())
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        user_1 = User.objects.filter(pk=user_1.pk)[0]
        user_2 = User.objects.filter(pk=user_2.pk)[0]
        _ = list(user_1.tags.all())
        _ = list(user_2.tags.all())
        assert len(ctx.captured_queries) == 4

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        user_1 = User.objects.get(pk=user_1.pk)
        user_2 = User.objects.get(pk=user_2.pk)
        _ = list(user_1.tags.all())
        _ = list(user_2.tags.all())
        assert len(ctx.captured_queries) == 4


def test_zeal_ignore_works_for_generic_relation():
    from djangoproject.social.models import Tag

    [user_1, user_2] = UserFactory.create_batch(2)
    Tag.objects.create(obj=user_1, label="a")
    Tag.objects.create(obj=user_2, label="b")

    with zeal_ignore([{"model": "social.User", "field": "tags"}]):
        for user in User.objects.all():
            _ = list(user.tags.all())


def test_no_false_positive_when_calling_generic_relation_twice():
    from djangoproject.social.models import Tag

    user = UserFactory.create()
    Tag.objects.create(obj=user, label="a")

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        queryset = user.tags.all()
        list(queryset)  # evaluate queryset once
        list(queryset)  # evaluate again (cached)
        assert len(ctx.captured_queries) == 1


def test_detects_nplusone_in_generic_foreign_key():
    from djangoproject.social.models import Tag

    [user_1, user_2] = UserFactory.create_batch(2)
    Tag.objects.create(obj=user_1, label="a")
    Tag.objects.create(obj=user_2, label="b")
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Tag.obj")
    ):
        for tag in Tag.objects.all():
            _ = tag.obj

    for tag in Tag.objects.prefetch_related("obj").all():
        _ = tag.obj


def test_detects_nplusone_in_generic_foreign_key_iterator():
    from djangoproject.social.models import Tag

    for _ in range(4):
        user = UserFactory.create()
        Tag.objects.create(obj=user, label="x")
    with pytest.raises(
        NPlusOneError, match=re.escape("N+1 detected on social.Tag.obj")
    ):
        for tag in Tag.objects.all().iterator(chunk_size=2):
            _ = tag.obj

    for tag in Tag.objects.prefetch_related("obj").iterator(chunk_size=2):
        _ = tag.obj


def test_no_false_positive_when_loading_single_object_generic_foreign_key():
    from djangoproject.social.models import Tag

    user_1, user_2 = UserFactory.create_batch(2)
    tag_1 = Tag.objects.create(obj=user_1, label="a")
    tag_2 = Tag.objects.create(obj=user_2, label="b")

    with zeal_context():
        tag_1 = Tag.objects.filter(pk=tag_1.pk).first()
        tag_2 = Tag.objects.filter(pk=tag_2.pk).first()
        assert tag_1 is not None and tag_2 is not None
        _ = tag_1.obj
        _ = tag_2.obj

    with zeal_context():
        tag_1 = Tag.objects.filter(pk=tag_1.pk)[0]
        tag_2 = Tag.objects.filter(pk=tag_2.pk)[0]
        _ = tag_1.obj
        _ = tag_2.obj

    with zeal_context():
        tag_1 = Tag.objects.get(pk=tag_1.pk)
        tag_2 = Tag.objects.get(pk=tag_2.pk)
        _ = tag_1.obj
        _ = tag_2.obj


def test_zeal_ignore_works_for_generic_foreign_key():
    from djangoproject.social.models import Tag

    [user_1, user_2] = UserFactory.create_batch(2)
    Tag.objects.create(obj=user_1, label="a")
    Tag.objects.create(obj=user_2, label="b")

    with zeal_ignore([{"model": "social.Tag", "field": "obj"}]):
        for tag in Tag.objects.all():
            _ = tag.obj


def test_no_false_positive_when_generic_foreign_key_is_null():
    from djangoproject.social.models import Tag

    Tag.objects.create(label="a")
    Tag.objects.create(label="b")

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        for tag in Tag.objects.all():
            assert tag.obj is None
        # Only the SELECT for Tag.objects.all(); no per-row GFK queries.
        assert len(ctx.captured_queries) == 1


def test_no_false_positive_when_accessing_generic_foreign_key_twice():
    from djangoproject.social.models import Tag

    user = UserFactory.create()
    Tag.objects.create(obj=user, label="a")

    with zeal_context(), CaptureQueriesContext(connection) as ctx:
        [tag] = list(Tag.objects.all())
        _ = tag.obj  # first access hits DB
        _ = tag.obj  # second access uses descriptor cache
        # 1 query for the tag itself, 1 for the User via GFK,
        # plus ContentType lookups (cached after first).
        gfk_queries = [
            q for q in ctx.captured_queries if '"social_user"' in q["sql"]
        ]
        assert len(gfk_queries) == 1


@pytest.mark.parametrize("load", ["first", "get", "slice"])
def test_singly_loaded_deferred_fields_do_not_raise(settings, load):
    settings.ZEAL_ALLOWLIST = [{"model": "social.User", "field": "get()"}]
    users = UserFactory.create_batch(2)
    qs = User.objects.only("pk")
    if load == "first":
        loaded = [
            qs.filter(pk=users[0].pk).first(),
            qs.filter(pk=users[1].pk).first(),
        ]
    elif load == "get":
        loaded = [
            qs.get(pk=users[0].pk),
            qs.get(pk=users[1].pk),
        ]
    else:
        loaded = [qs.filter(pk=users[0].pk)[0], qs.filter(pk=users[1].pk)[0]]
    with CaptureQueriesContext(connection) as captured:
        names = []
        for user in loaded:
            assert user is not None
            names.append(user.username)
    assert names == [user.username for user in users]
    assert len(captured) == 2


@pytest.mark.parametrize("field", ["username", "posts"])
def test_single_load_exemptions_do_not_cross_app_boundaries(field):
    users = UserFactory.create_batch(2)
    AuthUser.objects.create(pk=users[1].pk, username="auth-user")
    assert AuthUser.objects.filter(pk=users[1].pk).first() is not None

    with pytest.raises(NPlusOneError, match=f"social.User.{field}"):
        for user in User.objects.only("pk").order_by("pk"):
            if field == "username":
                _ = user.username
            else:
                _ = list(user.posts.all())
