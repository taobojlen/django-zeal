# Property investigations

This opt-in suite uses Hypothesis without adding a library dependency or
changing the default pytest test paths. Deterministic regressions belong in
`tests/`; generators and reference models belong here. The discovery code is
excluded from the default pyright check, like the benchmark machinery in
`auto/`. Ruff checks both suites.

Run from the repository root:

```sh
uv run --frozen --with hypothesis pytest discovery -q --hypothesis-show-statistics
ZEAL_PROPERTY_EXAMPLES=1500 uv run --frozen --with hypothesis pytest discovery tests -q -m 'not benchmark' --random-order --hypothesis-show-statistics
```

Use `--hypothesis-seed=<integer>` to reproduce a particular generation run.
Hypothesis also stores and shrinks failing examples in `.hypothesis/`.
Database examples use a transaction rollback; detection contexts and Django
settings are reset for each example. No generated data leaves SQLite memory.

| Correctness target | Independent check and interacting inputs |
| --- | --- |
| Context counts and scope restoration | Counter/set snapshots versus notifications; nested ignore/setup scopes, repeated identities, two call sites, thresholds 2–4, both caller modes. Targeted prefixes warm a call history before entering and leaving an ignore scope. |
| Deferred single-load exemptions | `.only()` and `.defer()` crossed with bulk, `.first()`, `.get()`, and indexing; exact values and field-attributed warning counts. |
| Deferred refresh loading origin | Read an allowlisted scalar, then a non-allowlisted relation; bulk and single loads must retain their respective reporting behavior. Repeated scalar reads must use their cache. |
| M2M mutation and pickle | A three-node directed adjacency map versus Django rows; set/add/remove/clear, prefetch, and protocols 0 through the interpreter maximum. Embedded warm → unequal replacement → pickle → remove → reinsert histories make stale caches visible. Restored prefetched relations must execute zero queries. |
| Lazy queryset ownership | Lists of expected post IDs and evaluation bits versus retained querysets; creation, clone, filtering, repeated evaluation, and pickle. Two evaluation call sites have independent counts. |
| Prefetch iterator partitioning | Expected row membership versus chunked iteration, including singleton chunks, leftovers, and cloned querysets. Correct bulk prefetch must not raise or warn. |
| Async isolation and exception unwinding | Interleaved tasks establish their own contexts, inherit allowlists, and reach thresholds independently. Parent counts survive normal and exceptional scope exits. |

`event()` statistics report operation mix, restored contexts, repeated cached
reads, unequal replacements, and mutations after prefetch. The three randomized
history properties use the requested example budget. The smaller finite
properties stop when their argument domains are exhausted.

The model does not use Zeal's counting, matching, or identity helpers. The
queryset model derives filtered membership from creation-time IDs, not from
another queryset. Pickle properties check both values and absence of reloads.

Scope limits: this is not exhaustive ORM or security verification. M2M cache
mutation histories cover the forward manager on the mutated instance, not
automatic invalidation of separate instances. Async tests cover context state,
not asynchronous database queries. Aggregate/exists evaluation, cross-app model
name collisions, unusual custom managers, and deeper GFK cache mutations remain
useful targets. Detection on clones of unpickled related querysets is explicitly
outside the serialization contract described in `patch.py`.
