import factory
from djangoproject.social.models import Post, Profile, User


class UserFactory(factory.django.DjangoModelFactory):
    username = factory.Faker("user_name")

    class Meta:
        model = User


class ProfileFactory(factory.django.DjangoModelFactory):
    display_name = factory.Faker("name")

    class Meta:
        model = Profile


class PostFactory(factory.django.DjangoModelFactory):
    text = factory.Faker("sentence")

    class Meta:
        model = Post
