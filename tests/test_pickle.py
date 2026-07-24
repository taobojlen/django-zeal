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
from django.db import connection
from django.test.utils import CaptureQueriesContext
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
    This must not crash, and the prefetched data must actually survive the
    round-trip (not be silently reloaded from the database on access).
    """
    user = UserFactory.create()
    PostFactory.create(author=user)
    PostFactory.create(author=user)

    [loaded] = list(User.objects.prefetch_related("posts"))
    # Force the prefetch cache population by accessing the relation.
    posts = list(loaded.posts.all())
    assert len(posts) == 2
    expected_pks = {p.pk for p in posts}

    restored = pickle.loads(pickle.dumps(loaded))

    # The prefetch cache must survive serialization. Asserting on the cache
    # directly (and that accessing the restored relation issues zero queries)
    # guards against a regression where the data happens to match only because
    # ``.all()`` reloaded the same rows from the database.
    assert "posts" in restored._prefetched_objects_cache
    with CaptureQueriesContext(connection) as captured:
        result = list(restored.posts.all())
    assert len(captured.captured_queries) == 0
    assert {p.pk for p in result} == expected_pks


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
