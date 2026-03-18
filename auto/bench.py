#!/usr/bin/env python
"""
Benchmark: measures zeal overhead ratio (zeal-enabled vs disabled).

Outputs machine-readable METRIC lines for autoresearch consumption.
Uses median of N iterations (default 15) after warmup for stability.
"""

import gc
import os
import statistics
import sys
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tests"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoproject.settings")

import django

django.setup()

from django.core.management import call_command

call_command("migrate", "--run-syncdb", verbosity=0)

from django.conf import settings

from djangoproject.social.models import Post, Profile, User
from factories import PostFactory, ProfileFactory, UserFactory
from zeal import zeal_context, zeal_ignore


def setup_data():
    users = UserFactory.create_batch(10)
    rels = []
    for u in users:
        for f in users:
            if u != f:
                rels.append(
                    User.following.through(from_user_id=u.id, to_user_id=f.id)
                )
    User.following.through.objects.bulk_create(rels)
    for u in users:
        ProfileFactory(user=u)
    for u in users:
        PostFactory.create_batch(10, author=u)


def workload():
    posts = Post.objects.all()
    for post in posts:
        _ = post.author.username
        _ = list(post.author.posts.all())

    profiles = Profile.objects.all()
    for profile in profiles:
        _ = profile.user.username
        _ = profile.user.profile.display_name

    users = User.objects.all()
    for user in users:
        _ = list(user.following.all())
        _ = list(user.followers.all())
        _ = list(user.blocked.all())
        for follower in user.followers.all():
            _ = follower.profile.display_name
            _ = list(follower.posts.all())


def bench(label, wrapper, n, warmup):
    for _ in range(warmup):
        gc.collect()
        with wrapper():
            workload()

    times = []
    for _ in range(n):
        gc.collect()
        start = time.perf_counter()
        with wrapper():
            workload()
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1000)

    median = statistics.median(times)
    mean = statistics.mean(times)
    stdev = statistics.stdev(times) if len(times) > 1 else 0
    mn = min(times)
    mx = max(times)
    print(
        f"  {label}: median={median:.1f}ms mean={mean:.1f}ms "
        f"stdev={stdev:.1f}ms min={mn:.1f}ms max={mx:.1f}ms (n={n})"
    )
    return median


@contextmanager
def noop_ctx():
    yield


@contextmanager
def zeal_ctx():
    with zeal_context(), zeal_ignore():
        yield


@contextmanager
def zeal_all_callers_ctx():
    settings.ZEAL_SHOW_ALL_CALLERS = True
    try:
        with zeal_context(), zeal_ignore():
            yield
    finally:
        settings.ZEAL_SHOW_ALL_CALLERS = False


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    warmup = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    setup_data()
    print(f"Benchmark: {n} iterations, {warmup} warmup\n")

    baseline_ms = bench("baseline (no zeal)", noop_ctx, n, warmup)
    zeal_ms = bench("with zeal", zeal_ctx, n, warmup)
    zeal_allcallers_ms = bench("with zeal (SHOW_ALL_CALLERS)", zeal_all_callers_ctx, n, warmup)
    overhead_ratio = zeal_ms / baseline_ms
    overhead_ratio_allcallers = zeal_allcallers_ms / baseline_ms

    print()
    print(f"METRIC baseline_ms={baseline_ms:.1f}")
    print(f"METRIC zeal_ms={zeal_ms:.1f}")
    print(f"METRIC overhead_ratio={overhead_ratio:.2f}")
    print(f"METRIC zeal_allcallers_ms={zeal_allcallers_ms:.1f}")
    print(f"METRIC overhead_ratio_allcallers={overhead_ratio_allcallers:.2f}")
