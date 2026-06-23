# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Overview

django-zeal is a zero-dependency library that detects N+1 queries in Django apps by monkey-patching the Django ORM at app-ready time. It is intended for use in development, tests, and CI — not production (it adds ~3-5% overhead).

## Commands

Tasks are defined in `mise.toml` and run via `mise run <task>`. Tooling (uv, Python, ruff) is provisioned by mise.

- `mise run install` — create the venv, install dev deps, and configure git hooks (`hooks/`)
- `mise run test` — run the test suite (excludes benchmarks, uses `--random-order`)
- `mise run test -- -x -k test_foo` — pass extra pytest args after `--`; run a single test this way
- `mise run typecheck` — run pyright over `src` and `tests`
- `mise run format` — apply ruff formatting and lint fixes; `mise run format-check` to only check
- `mise run benchmark` — run codspeed benchmarks (the `benchmark` pytest marker)

Tests use a real in-memory SQLite Django project under `tests/djangoproject/` (`DJANGO_SETTINGS_MODULE=djangoproject.settings`, set in `pyproject.toml`). The `nozeal` pytest marker disables zeal auto-setup for a test.

CI (`.github/workflows/test.yaml`) runs the matrix Python 3.9–3.12 × Django 4.2/5.0/6.0 plus a Django prerelease job, so changes must work across all supported versions. Guard version-specific ORM internals (e.g. `get_prefetch_querysets` vs the older `get_prefetch_queryset`).

## Architecture

The library has no public-facing query interception of its own — it wraps Django's ORM internals and reports through a per-context listener.

**Entry point.** `ZealConfig.ready()` (`apps.py`) calls `initialize_app_registry()` then `patch()`. So patching only happens when `zeal` is in `INSTALLED_APPS`; nothing is touched otherwise (unlike nplusone).

**`patch.py` — ORM monkey-patching.** Each `patch_*` function wraps one Django relation mechanism: forward/reverse many-to-one, reverse one-to-one, many-to-many, generic FK, generic related manager, deferred attributes (`.only()`/`.defer()`), and global `QuerySet._fetch_all`/`.get()`. The core trick is `patch_queryset_function`, which recursively re-patches `queryset._clone` and `queryset._fetch_all` so that lazy querysets notify the listener exactly once when first evaluated (`__zeal_patched`/`__zeal_skip_notify` flags prevent double-counting). A set of `ContextVar` flags (`_in_queryset_prefetch`, `_in_prefetch_queryset`, `_in_gfk_get`) suppress notifications during Django's internal prefetch/GFK paths so that *correct* `.prefetch_related()` usage is not flagged — only genuine per-instance N+1s are. Each patch supplies a `parser` that turns the captured queryset context into a `QuerySource` (model, field, instance_key).

**`listeners.py` — detection state and reporting.** All state lives in an `NPlusOneContext` held in a `ContextVar` (`_nplusone_context`), so detection is isolated per request/task/test and async-safe. `NPlusOneListener.notify(model, field, instance_key)` counts repeated `(model, field, caller)` accesses; when the count hits `ZEAL_NPLUSONE_THRESHOLD` (default 2) it calls `_alert()`, which checks the allowlist, then either raises `NPlusOneError` (`ZEAL_RAISE`, default True) or emits a warning, and fires the `nplusone_detected` signal. Single-instance loads (via `.get()`, `.first()`, single-row queries — see `is_single_query` in `util.py`) are added to `context.ignored` to avoid false positives. Several values on the context are lazily cached (`_threshold`, `_show_all_callers`, `_allowlisted_keys`) specifically to keep the hot `notify()` path cheap.

**Public API & lifecycle.** `setup()`/`teardown()` enable/disable a context and return/reset a `Token`; `zeal_context()` is the context-manager form (used by `middleware.py` for both sync and async requests). `zeal_ignore([...])` temporarily extends the allowlist within a block. The allowlist supports `fnmatch` patterns on model/field and is validated against `ALL_APPS` (built in `constants.py` from the model registry). Exported names are in `__init__.py`; the signal lives in `signals.py`.

**`util.py` — caller attribution.** `get_caller()`/`get_stack()` walk raw frames skipping `site-packages` and zeal's own dir to find the user code line for error messages. `ZEAL_SHOW_ALL_CALLERS` switches to capturing full stacks per call.

## Conventions

- ruff with `line-length = 79`; lint rules include the `FIX` set, so `TODO`/`FIXME` comments and commented-out code (`ERA`) will fail linting.
- Supports Python 3.9+, so avoid 3.10+-only syntax in runtime code; `typing_extensions` is used for `NotRequired` under `TYPE_CHECKING`.
- Releases are automated via release-please; do not hand-edit `CHANGELOG.md` or the version in `pyproject.toml`.
