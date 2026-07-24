"""
Regression tests for https://github.com/taobojlen/django-zeal/issues/76

zeal attaches locally-defined closures to queryset instances
(``_clone``/``_fetch_all``/``__zeal_patched``). Local closures are not
picklable, so any related or prefetched queryset created while zeal is
installed can no longer be pickled -- even outside an active zeal context.

These tests must pass both with and without an active zeal context, because
the issue is caused by merely having zeal in INSTALLED_APPS.
"""

import pickle

import pytest
from djangoproject.social.models import User

from .factories import PostFactory, UserFactory

pytestmark = pytest.mark.django_db


def _roundtrip(qs):
    return pickle.loads(pickle.dumps(qs))


def test_plain_queryset_pickles():
    """A plain queryset (no zeal-affected path) must pickle."""
    UserFactory.create()
    qs = User.objects.all()
    assert _roundtrip(qs).count() == 1


def test_prefetch_related_queryset_pickles():
    """
    `prefetch_related` produces querysets that go through zeal's patched
    prefetch path. The resulting (un-evaluated) queryset must pickle.
    """
    user = UserFactory.create()
    PostFactory.create(author=user)

    qs = User.objects.prefetch_related("posts")
    assert _roundtrip(qs).count() == 1


def test_reverse_fk_queryset_pickles():
    """A reverse FK manager's queryset (user.posts.all()) must pickle."""
    user = UserFactory.create()
    PostFactory.create(author=user)

    qs = user.posts.all()
    assert _roundtrip(qs).count() == 1


def test_m2m_queryset_pickles():
    """A M2M manager's queryset (user.following.all()) must pickle."""
    u1 = UserFactory.create()
    u2 = UserFactory.create()
    u1.following.add(u2)

    qs = u1.following.all()
    assert _roundtrip(qs).count() == 1


def test_prefetched_instance_pickles_with_cache():
    """
    The cacheops scenario: a model instance carrying a prefetched queryset in
    ``_prefetched_objects_cache`` is pickled as part of a larger object graph.
    This must not crash.
    """
    user = UserFactory.create()
    PostFactory.create(author=user)
    PostFactory.create(author=user)

    [loaded] = list(User.objects.prefetch_related("posts"))
    # Force the prefetch cache population by accessing the relation.
    posts = list(loaded.posts.all())
    assert len(posts) == 2

    restored = pickle.loads(pickle.dumps(loaded))
    # prefetched data survives the round-trip
    assert {p.pk for p in restored.posts.all()} == {p.pk for p in posts}


@pytest.mark.nozeal
def test_pickles_work_without_zeal_context():
    """
    The issue reproduces regardless of whether a zeal context is active,
    because the instance attributes are attached at queryset creation time.
    Ensure pickling works with no active context.
    """
    user = UserFactory.create()
    PostFactory.create(author=user)

    qs = User.objects.prefetch_related("posts")
    assert _roundtrip(qs).count() == 1
