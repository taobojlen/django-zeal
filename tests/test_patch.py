import sys

import pytest
from django.db import models
from djangoproject.social.models import User

from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_handles_calling_queryset_many_times():
    UserFactory.create()
    user = User.objects.prefetch_related("posts").all()[0]
    for _ in range(sys.getrecursionlimit() + 1):
        # this should *not* raise a recursion error
        list(user.posts.all())


def test_handles_empty_querysets():
    User.objects.none().first()


def test_handles_get_with_values():
    user = UserFactory.create()
    User.objects.filter(pk=user.pk).values("username").get()


class CustomEqualityModel(models.Model):
    """Model that implements custom equality checking using related fields"""

    name: models.CharField = models.CharField(max_length=100)
    relation: models.ForeignKey[
        "CustomEqualityModel", "CustomEqualityModel"
    ] = models.ForeignKey(
        "self", null=True, on_delete=models.CASCADE, related_name="related"
    )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CustomEqualityModel):
            return NotImplemented
        # Explicitly access relation to trigger potential recursion
        my_rel = self.relation
        other_rel = other.relation
        return my_rel == other_rel and self.name == other.name

    class Meta:
        app_label = "social"


def test_handles_custom_equality_with_relations():
    """
    Ensure model equality comparisons don't cause infinite recursion
    when __eq__ methods access related fields. This is important because
    Django's lazy loading could trigger repeated relation lookups during
    equality checks.
    """
    # Create test instances
    base = CustomEqualityModel.objects.create(name="base")
    obj1 = CustomEqualityModel.objects.create(name="test1", relation=base)
    obj2 = CustomEqualityModel.objects.create(name="test1", relation=base)
    obj3 = CustomEqualityModel.objects.create(name="test2", relation=base)

    assert obj1 == obj1  # Same object
    assert obj1 == obj2  # Different objects, same values
    assert obj1 != obj3  # Different values

    result = CustomEqualityModel.objects.filter(name="test1").first()
    assert result is not None
    _ = result.relation


def test_handles_nested_relation_equality():
    """
    Ensure deep relation traversal works correctly without infinite recursion.
    This is particularly important for models that compare relations in their
    equality checks, as each comparison could potentially trigger a chain of
    database lookups through the relationship tree.
    """
    root = CustomEqualityModel.objects.create(name="root")
    middle = CustomEqualityModel.objects.create(name="middle", relation=root)
    leaf1 = CustomEqualityModel.objects.create(name="leaf", relation=middle)
    leaf2 = CustomEqualityModel.objects.create(name="leaf", relation=middle)

    assert leaf1 == leaf2
    assert leaf1.relation == leaf2.relation

    result = CustomEqualityModel.objects.filter(name="leaf").first()
    assert result is not None
    _ = result.relation.relation
