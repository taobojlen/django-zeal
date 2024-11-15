import pytest
from djangoproject.social.models import Post, Profile, User
from zeal import zeal_context, zeal_ignore

from .factories import PostFactory, ProfileFactory, UserFactory

pytestmark = [pytest.mark.nozeal, pytest.mark.django_db]


def test_performance(benchmark):
    users = UserFactory.create_batch(10)

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

    @benchmark
    def _run_benchmark():
        with (
            zeal_context(),
            zeal_ignore(),
        ):
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
                _ = list(
                    user.blocked.all()
                )  # many-to-many without related_name

                # Test chained relationships
                for follower in user.followers.all():
                    _ = follower.profile.display_name
                    _ = list(follower.posts.all())
