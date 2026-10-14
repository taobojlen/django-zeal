"""Model-based properties for detection contexts and Django queryset state."""

import asyncio
import pickle
import warnings
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy

import pytest
from django.db import connection, transaction
from django.db.models import prefetch_related_objects
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from djangoproject.social.models import Post, User
from hypothesis import event, given
from hypothesis import strategies as st
from zeal import zeal_context, zeal_ignore
from zeal.listeners import n_plus_one_listener


def notify(field, instance, caller):
    if caller == 0:
        n_plus_one_listener.notify(User, field, instance)
    else:
        n_plus_one_listener.notify(User, field, instance)


operation = st.tuples(
    st.sampled_from(["notify", "ignore", "push_ignore", "push", "pop"]),
    st.sampled_from(["posts", "following", "username"]),
    st.sampled_from([None, "User:0", "User:1"]),
    st.integers(0, 1),
)

context_histories = st.one_of(
    st.lists(operation, max_size=60),
    st.tuples(st.lists(operation, max_size=10), st.integers(0, 1)).map(
        lambda parts: parts[0]
        + [
            ("notify", "posts", None, parts[1]),
            ("push_ignore", "posts", None, parts[1]),
            ("notify", "posts", None, parts[1]),
            ("pop", "posts", None, parts[1]),
            ("notify", "posts", None, parts[1]),
        ]
    ),
)


@given(st.integers(2, 4), st.booleans(), context_histories)
def test_context_histories(threshold, show_all, operations):
    # The model stores complete snapshots, without caching or shared lists.
    model = {"counts": Counter(), "ignored": set(), "allowlist": set()}
    parents = []
    scopes = []

    def close_scopes():
        while scopes:
            scopes.pop().__exit__(None, None, None)

    with (
        override_settings(
            ZEAL_RAISE=False,
            ZEAL_NPLUSONE_THRESHOLD=threshold,
            ZEAL_SHOW_ALL_CALLERS=show_all,
        ),
        zeal_context(),
        ExitStack() as cleanup,
    ):
        cleanup.callback(close_scopes)
        for kind, field, instance, caller in operations:
            event(kind)
            if kind == "push_ignore" or kind == "push":
                parents.append(deepcopy(model))
                if kind == "push_ignore":
                    scope = zeal_ignore(
                        [{"model": "social.User", "field": field}]
                    )
                    model["allowlist"].add(field)
                else:
                    scope = zeal_context()
                    model["counts"] = Counter()
                    model["ignored"] = set()
                scope.__enter__()
                scopes.append(scope)
            elif kind == "pop":
                if scopes:
                    scopes.pop().__exit__(None, None, None)
                    model = parents.pop()
                    event("restored parent")
            elif kind == "ignore":
                n_plus_one_listener.ignore(instance)
                if instance is not None:
                    model["ignored"].add(instance)
            else:
                key = (field, caller)
                model["counts"][key] += 1
                expected = (
                    model["counts"][key] >= threshold
                    and instance not in model["ignored"]
                    and field not in model["allowlist"]
                )
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    notify(field, instance, caller)
                assert len(caught) == int(expected)


@pytest.mark.django_db
@given(
    st.sampled_from(["all", "first", "get", "slice"]),
    st.sampled_from(["only", "defer"]),
    st.integers(2, 5),
    st.booleans(),
)
def test_deferred_single_load_contract(load, defer, count, show_all):
    # Each generated example rolls back its database writes independently.
    with transaction.atomic():
        users = [User.objects.create(username=str(i)) for i in range(count)]
        with (
            override_settings(
                ZEAL_RAISE=False, ZEAL_SHOW_ALL_CALLERS=show_all
            ),
            zeal_context(),
        ):
            qs = (
                User.objects.only("pk")
                if defer == "only"
                else User.objects.defer("username")
            )
            if load == "all":
                loaded = list(qs.filter(pk__in=[u.pk for u in users]))
            else:
                loaded = []
                for user in users:
                    with override_settings(
                        ZEAL_ALLOWLIST=[
                            {"model": "social.User", "field": "get()"}
                        ]
                    ):
                        selected = qs.filter(pk=user.pk)
                        if load == "first":
                            loaded.append(selected.first())
                        elif load == "get":
                            loaded.append(selected.get())
                        else:
                            loaded.append(selected[0])
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                names = [user.username for user in loaded]
            assert names == [str(i) for i in range(count)]
            fields = [
                str(w.message).split("social.User.")[1].split()[0]
                for w in caught
            ]
            assert fields == (
                ["username"] * (count - 1) if load == "all" else []
            )
        transaction.set_rollback(True)


@pytest.mark.django_db
@given(st.integers(2, 5), st.booleans(), st.booleans())
def test_deferred_refresh_preserves_loading_origin(count, single, show_all):
    with transaction.atomic():
        users = [User.objects.create(username=str(i)) for i in range(count)]
        posts = [
            Post.objects.create(author=u, text=str(i))
            for i, u in enumerate(users)
        ]
        with (
            override_settings(
                ZEAL_RAISE=False,
                ZEAL_SHOW_ALL_CALLERS=show_all,
                ZEAL_ALLOWLIST=[{"model": "social.Post", "field": "text"}],
            ),
            zeal_context(),
        ):
            qs = Post.objects.filter(pk__in=[p.pk for p in posts]).defer(
                "text"
            )
            if single:
                loaded = []
                for post in posts:
                    selected = qs.filter(pk=post.pk).first()
                    assert selected is not None
                    loaded.append(selected)
            else:
                loaded = list(qs)
            assert [post.text for post in loaded] == [
                str(i) for i in range(count)
            ]
            with CaptureQueriesContext(connection) as captured:
                assert [post.text for post in loaded] == [
                    str(i) for i in range(count)
                ]
            assert len(captured) == 0
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                authors = [post.author.pk for post in loaded]
            assert authors == [u.pk for u in users]
            assert len(caught) == (0 if single else count - 1)
            assert all("social.Post.author" in str(w.message) for w in caught)
        transaction.set_rollback(True)


edge_sets = st.sets(st.tuples(st.integers(0, 2), st.integers(0, 2)))
relation_ops = st.lists(
    st.tuples(
        st.sampled_from(["add", "remove", "clear", "set", "warm", "pickle"]),
        st.integers(0, 2),
        st.sets(st.integers(0, 2)),
    ),
    max_size=35,
)
relation_histories = st.one_of(
    relation_ops,
    st.tuples(relation_ops, st.integers(0, 2), st.integers(0, 2)).map(
        lambda parts: parts[0]
        + [
            ("set", parts[1], {parts[2]}),
            ("warm", parts[1], set()),
            ("set", parts[1], {(parts[2] + 1) % 3}),
            ("pickle", parts[1], set()),
            ("remove", parts[1], {(parts[2] + 1) % 3}),
            ("add", parts[1], {parts[2]}),
            ("pickle", parts[1], set()),
        ]
    ),
)


@pytest.mark.django_db
@given(edge_sets, relation_histories, st.integers(0, pickle.HIGHEST_PROTOCOL))
def test_relation_cache_histories(edges, operations, protocol):
    with transaction.atomic(), zeal_ignore():
        users = [User.objects.create(username=str(i)) for i in range(3)]
        expected = {i: {b for a, b in edges if a == i} for i in range(3)}
        for i, user in enumerate(users):
            user.following.set([users[j] for j in expected[i]])
        for kind, i, targets in operations:
            event(kind)
            user = users[i]
            selected = [users[j] for j in sorted(targets)]
            if kind == "add":
                user.following.add(*selected)
                expected[i] |= targets
            elif kind == "remove":
                user.following.remove(*selected)
                expected[i] -= targets
            elif kind == "clear":
                user.following.clear()
                expected[i].clear()
            elif kind == "set":
                if targets != expected[i]:
                    event("unequal replacement")
                if hasattr(user, "_prefetched_objects_cache"):
                    event("mutation after prefetch")
                user.following.set(selected)
                expected[i] = set(targets)
            elif kind == "warm":
                users[i] = User.objects.prefetch_related("following").get(
                    pk=user.pk
                )
            else:
                prefetch_related_objects([user], "following")
                users[i] = pickle.loads(pickle.dumps(user, protocol=protocol))
                with CaptureQueriesContext(connection) as captured:
                    restored = list(users[i].following.all())
                assert len(captured) == 0
                assert {u.pk for u in restored} == {
                    users[j].pk for j in expected[i]
                }
            assert {u.pk for u in users[i].following.all()} == {
                users[j].pk for j in expected[i]
            }
        transaction.set_rollback(True)


query_operations = st.lists(
    st.tuples(
        st.sampled_from(["new", "clone", "filter", "read", "pickle"]),
        st.integers(0, 5),
    ),
    min_size=1,
    max_size=40,
)


def evaluate(queryset, method):
    if method == "read":
        return list(queryset)
    return list(pickle.loads(pickle.dumps(queryset)))


@pytest.mark.django_db
@given(query_operations, st.integers(2, 4))
def test_lazy_queryset_clone_histories(operations, threshold):
    with transaction.atomic():
        users = [User.objects.create(username=str(i)) for i in range(3)]
        rows = [
            [
                Post.objects.create(author=user, text=str(j)).pk
                for j in range(i)
            ]
            for i, user in enumerate(users)
        ]
        querysets = [users[2].posts.all()]
        model = [(rows[2], False)]
        counts = Counter()
        with (
            override_settings(
                ZEAL_RAISE=False, ZEAL_NPLUSONE_THRESHOLD=threshold
            ),
            zeal_context(),
        ):
            for kind, operand in operations:
                event(kind)
                index = operand % len(model)
                expected, cached = model[index]
                if kind == "new":
                    owner = operand % 3
                    querysets.append(users[owner].posts.all())
                    model.append((rows[owner], False))
                elif kind == "clone":
                    querysets.append(querysets[index].all())
                    model.append((expected, False))
                elif kind == "filter":
                    querysets.append(querysets[index].filter(text="1"))
                    model.append(
                        ([pk for pk in expected if pk == rows[2][1]], False)
                    )
                else:
                    if not cached:
                        counts[kind] += 1
                    else:
                        event("repeated cached evaluation")
                    with warnings.catch_warnings(record=True) as caught:
                        warnings.simplefilter("always")
                        result = evaluate(querysets[index], kind)
                    assert [post.pk for post in result] == expected
                    assert len(caught) == int(
                        not cached and counts[kind] >= threshold
                    )
                    model[index] = (expected, True)
        transaction.set_rollback(True)


@given(st.integers(2, 4), st.booleans(), st.booleans())
def test_async_context_isolation_and_exception_unwind(threshold, ignore, fail):
    async def worker():
        with zeal_context():
            caught = []
            for _ in range(threshold):
                await asyncio.sleep(0)
                with warnings.catch_warnings(record=True) as current:
                    warnings.simplefilter("always")
                    notify("posts", None, 0)
                caught.extend(current)
            assert len(caught) == (0 if ignore else 1)

    async def run():
        with zeal_context():
            notify("posts", None, 0)
            try:
                with zeal_ignore() if ignore else zeal_context():
                    await asyncio.gather(worker(), worker())
                    if fail:
                        raise ValueError("injected failure")
            except ValueError:
                pass
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                for _ in range(threshold - 1):
                    notify("posts", None, 0)
            assert len(caught) == 1

    with override_settings(
        ZEAL_RAISE=False, ZEAL_NPLUSONE_THRESHOLD=threshold
    ):
        asyncio.run(run())


@pytest.mark.django_db
@given(st.integers(2, 5), st.integers(1, 3), st.booleans())
def test_prefetch_iterator_partitioning(count, chunk, clone):
    with transaction.atomic():
        users = [User.objects.create(username=str(i)) for i in range(count)]
        for user in users:
            Post.objects.create(author=user, text=str(user.pk))
        with zeal_context():
            qs = User.objects.filter(
                pk__in=[u.pk for u in users]
            ).prefetch_related("posts")
            if clone:
                qs = qs.all().filter(username__isnull=False)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = {
                    user.pk: [post.text for post in user.posts.all()]
                    for user in qs.iterator(chunk_size=chunk)
                }
            assert result == {u.pk: [str(u.pk)] for u in users}
            assert not caught
        transaction.set_rollback(True)
