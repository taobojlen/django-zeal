import re

import pytest
from django.db import connection
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


def test_ignores_calls_on_different_lines():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)

    # this should *not* raise an exception
    _a = list(user_1.posts.all())
    _b = list(user_2.posts.all())
