import sys
import time

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from djangoproject.social.models import Post, Profile, User
from zeal import zeal_context, zeal_ignore

from .factories import PostFactory, ProfileFactory, UserFactory

pytestmark = [pytest.mark.benchmark, pytest.mark.nozeal, pytest.mark.django_db]


def _run_benchmark():
    # Test forward & reverse many-to-one relationships (Post -> User, User -> Posts)
    posts = Post.objects.all()
    for post in posts:
        _ = post.author.username  # forward many-to-one
        _ = list(post.author.posts.all())  # reverse many-to-one

    # Test forward & reverse one-to-one relationships (Profile -> User, User -> Profile)
    profiles = Profile.objects.all()
    for profile in profiles:
        _ = profile.user.username  # forward one-to-one
        _ = profile.user.profile.display_name  # reverse one-to-one

    # Test forward & reverse many-to-many relationships
    users = User.objects.all()
    for user in users:
        _ = list(user.following.all())  # forward many-to-many
        _ = list(user.followers.all())  # reverse many-to-many
        _ = list(user.blocked.all())  # many-to-many without related_name

        # Test chained relationships
        for follower in user.followers.all():
            _ = follower.profile.display_name
            _ = list(follower.posts.all())


def test_performance():
    users = UserFactory.create_batch(50)

    # everyone follows everyone
    user_following_relations = []
    for user in users:
        for followee in users:
            if user == followee:
                continue
            user_following_relations.append(
                User.following.through(
                    from_user_id=user.id, to_user_id=followee.id
                )
            )
    User.following.through.objects.bulk_create(user_following_relations)

    # give everyone a profile
    for user in users:
        ProfileFactory(user=user)

    # everyone has 10 posts
    for user in users:
        PostFactory.create_batch(10, author=user)

    sys.stderr.write("# Benchmark\n")
    sys.stderr.flush()

    with CaptureQueriesContext(connection) as ctx:
        start_time = time.monotonic()
        _run_benchmark()
        duration_no_zeal = time.monotonic() - start_time
        num_queries_no_zeal = len(ctx.captured_queries)
        # write to stderr so we can suppress pytest's output
        sys.stderr.write(
            f"Without zeal: executed {num_queries_no_zeal} queries in {duration_no_zeal:.2f} seconds\n"
        )
        sys.stderr.flush()

    connection.queries_log.clear()
    with (
        zeal_context(),
        zeal_ignore(),
        CaptureQueriesContext(connection) as ctx,
    ):
        start_time = time.monotonic()
        _run_benchmark()
        duration_with_zeal = time.monotonic() - start_time
        num_queries_with_zeal = len(ctx.captured_queries)
        sys.stderr.write(
            f"With zeal:    executed {num_queries_with_zeal} queries in {duration_with_zeal:.2f} seconds\n"
        )
        sys.stderr.flush()

    # if the number of queries is different, the benchmark is invalid
    assert num_queries_no_zeal == num_queries_with_zeal

    sys.stderr.write(
        f"**Zeal made the code {duration_with_zeal / duration_no_zeal:.2f} times slower**\n"
    )
    sys.stderr.flush()
