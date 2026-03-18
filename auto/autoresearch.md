# Autoresearch: django-zeal Performance Optimization

## Objective
Reduce the runtime overhead of django-zeal's N+1 query detection.
The workload exercises all relationship types (forward/reverse many-to-one,
one-to-one, many-to-many, chained) with zeal enabled and N+1s suppressed
via `zeal_ignore()`. We measure the overhead ratio: zeal-enabled time vs
baseline (no zeal).

## How to Run
Run `./auto/autoresearch.sh` — it runs the full test suite (correctness gate),
then the performance benchmark, outputting METRIC lines.

For benchmark only: `.venv/bin/python auto/bench.py`

## Metrics
- **Primary (optimization target)**: `overhead_ratio` (lower is better, 1.00 = zero overhead)
- **Secondary (for context)**:
  - `zeal_ms` — median time with zeal enabled (ms)
  - `baseline_ms` — median time without zeal (ms)

## Iteration Protocol
Each autoresearch iteration must:
1. Make **exactly one change** (a single optimization idea)
2. Run `./auto/autoresearch.sh`
3. If tests fail → revert immediately (`git checkout -- .`)
4. If overhead_ratio improved → commit with a message describing the change and the new metric
5. If overhead_ratio regressed or unchanged → revert (`git checkout -- .`)
6. Update the Progress Log below with the result

## Files in Scope
- `src/zeal/listeners.py` — N+1 detection logic, context management, alert path
- `src/zeal/patch.py` — Django ORM monkey-patching, queryset wrapping
- `src/zeal/util.py` — Stack inspection utilities (`get_stack`, `get_caller`)
- `src/zeal/middleware.py` — Django middleware integration

## Off Limits
- `tests/` — tests must continue to pass unchanged
- `auto/` — benchmark infrastructure, do not modify
- Do not change the public API (`zeal_context`, `zeal_ignore`, signals, settings)
- Do not add new dependencies

## Constraints
- All 57 unit tests must pass
- Semantic correctness must be preserved — N+1 detection behavior must be identical
- `ZEAL_SHOW_ALL_CALLERS` feature must still work when enabled (full stack storage)
- When `ZEAL_SHOW_ALL_CALLERS` is not enabled, optimizations can skip stack storage

## Architecture Notes
The hot path on every relationship access is:
1. Patched descriptor calls `patch_queryset_fetch_all` wrapper
2. On query execution, `n_plus_one_listener.notify(model, field, instance_key)` is called
3. `notify()` calls `get_stack()` → `inspect.stack(context=0)` + frame filtering
4. Builds a key tuple `(model, field, "filename:lineno")`
5. Appends full stack to `context.calls[key]`
6. If count >= threshold: calls `_alert()` which calls `get_stack()` again

Known overhead sources (in estimated order of impact):
- `inspect.stack(context=0)` creates FrameInfo named tuples for every frame
- Full stack traces stored in memory for every call (even when SHOW_ALL_CALLERS is off)
- `_alert()` redundantly calls `get_stack()` (already captured in `notify()`)
- `hasattr(settings, ...)` checked on every `_threshold` / `_allowlist` access
- `fnmatch()` called per-allowlist-entry on every alert
- f-string key creation on every notify

## Baseline
- **Commit**: 2aabdaa (HEAD of main)
- **overhead_ratio**: 1.30
- **zeal_ms**: 101
- **baseline_ms**: 78

## Progress Log
1. **e572720** — Replace `inspect.stack(context=0)` with `sys._getframe()` in `notify()` fast path; skip storing full stacks when `ZEAL_SHOW_ALL_CALLERS` is off. **overhead_ratio=1.06** (was 1.30). baseline_ms=77.7, zeal_ms=82.7. All 57 tests pass. KEPT.
2. **58ce8a2** — Cache allowlisted (model, field) pairs in `NPlusOneContext._allowlisted_keys` so that once `_alert()` determines a pair is allowlisted, subsequent `notify()` calls skip `_alert()` entirely (avoiding message formatting, `_allowlist` property allocation, and `fnmatch()` checks on every call past threshold). **overhead_ratio=1.05** (was 1.06). baseline_ms=78.6, zeal_ms=82.6. All 57 tests pass. KEPT.
3. **f4bc2c4** — Reduce per-call allocations: remove `@functools.wraps` from hot-path queryset closures (profile showed `update_wrapper` as top zeal overhead at 0.013s/9250 calls), use tuple key instead of f-string in notify(), append `None` instead of `[]`, cache `calls[key]` in local var, remove redundant `_nplusone_context.set()` from `notify()` and `ignore()`. **overhead_ratio=1.04** (was 1.05). Official benchmark range: 1.02–1.05 (median 1.04). Interleaved A/B benchmark: median_pair_ratio=1.034 (was 1.038). All 57 tests pass. KEPT.
