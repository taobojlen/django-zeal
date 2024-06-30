import pytest
from djangoproject.social.models import Post, Profile, User
from queryspy.errors import NPlusOneError

from .factories import PostFactory, ProfileFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_detects_nplusone_in_forward_many_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(NPlusOneError):
        for post in Post.objects.all():
            _ = post.author.username

    for post in Post.objects.select_related("author").all():
        _ = post.author.username


def test_detects_nplusone_in_reverse_many_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(NPlusOneError):
        for user in User.objects.all():
            _ = list(user.posts.all())

    for user in User.objects.prefetch_related("posts").all():
        _ = list(user.posts.all())


def test_detects_nplusone_in_forward_one_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)
    with pytest.raises(NPlusOneError):
        for profile in Profile.objects.all():
            _ = profile.user.username

    for profile in Profile.objects.select_related("user").all():
        _ = profile.user.username


def test_detects_nplusone_in_reverse_one_to_one():
    [user_1, user_2] = UserFactory.create_batch(2)
    ProfileFactory.create(user=user_1)
    ProfileFactory.create(user=user_2)
    with pytest.raises(NPlusOneError):
        for user in User.objects.all():
            _ = user.profile.display_name

    for user in User.objects.select_related("profile").all():
        _ = user.profile.display_name


def test_detects_nplusone_in_forward_many_to_many():
    [user_1, user_2] = UserFactory.create_batch(2)
    user_1.following.add(user_2)
    user_2.following.add(user_1)
    with pytest.raises(NPlusOneError):
        for user in User.objects.all():
            _ = list(user.following.all())

    for user in User.objects.prefetch_related("following").all():
        _ = list(user.following.all())


def test_detects_nplusone_in_reverse_many_to_many():
    [user_1, user_2] = UserFactory.create_batch(2)
    user_1.following.add(user_2)
    user_2.following.add(user_1)
    with pytest.raises(NPlusOneError):
        for user in User.objects.all():
            _ = list(user.followers.all())

    for user in User.objects.prefetch_related("followers").all():
        _ = list(user.followers.all())


def test_detects_nplusone_in_reverse_many_to_many_with_no_related_name():
    [user_1, user_2] = UserFactory.create_batch(2)
    user_1.blocked.add(user_2)
    user_2.blocked.add(user_1)
    with pytest.raises(NPlusOneError):
        for user in User.objects.all():
            _ = list(user.user_set.all())

    for user in User.objects.prefetch_related("user_set").all():
        _ = list(user.user_set.all())


def test_detects_nplusone_due_to_deferred_fields():
    [user_1, user_2] = UserFactory.create_batch(2)
    PostFactory.create(author=user_1)
    PostFactory.create(author=user_2)
    with pytest.raises(NPlusOneError):
        for post in (
            Post.objects.all().select_related("author").only("author__id")
        ):
            _ = post.author.username

    for post in (
        Post.objects.all().select_related("author").only("author__username")
    ):
        _ = post.author.username
