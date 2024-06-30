from django.db import models


class User(models.Model):
    username = models.TextField()
    # user.followers and user.following are both ManyToManyDescriptor
    following = models.ManyToManyField("User", related_name="followers")

    # note that there's no related_name set here, because we want to
    # test that case too.
    blocked = models.ManyToManyField("user")

    followers: models.Manager["User"]
    user_set: models.Manager["User"]
    posts: models.Manager["Post"]
    profile: "Profile"


class Profile(models.Model):
    # profile.user is ForwardOneToOne
    # user.profile is ReverseOneToOne
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    display_name = models.TextField()


class Post(models.Model):
    # post.author is ForwardManyToOne
    # user.posts is ReverseManyToOne
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="posts"
    )
    text = models.TextField()
