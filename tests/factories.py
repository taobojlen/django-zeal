from typing import Generic, TypeVar

import factory
from djangoproject.social.models import Post, Profile, User

T = TypeVar("T")


class BaseFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, **kwargs) -> T:
        return super().create(**kwargs)


class UserFactory(BaseFactory[User]):
    username = factory.Faker("user_name")

    class Meta:  # type: ignore
        model = User


class ProfileFactory(BaseFactory[Profile]):
    display_name = factory.Faker("name")

    class Meta:  # type: ignore
        model = Profile


class PostFactory(BaseFactory[Post]):
    text = factory.Faker("sentence")

    class Meta:  # type: ignore
        model = Post
