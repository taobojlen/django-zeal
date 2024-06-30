# queryspy

This library catches N+1s in your Django project.

## Features

- Detects N+1s from missing prefetches and from `.defer()`/`.only()`
- Configurable thresholds
- TODO: allowlist
- TODO: catches unused eager loads
- Well-tested
- No dependencies

## Acknowledgements

This library draws heavily from jmcarp's [nplusone](https://github.com/jmcarp/nplusone/).
It's not exactly a fork, but not far from it.

## Installation

To install `queryspy`, add it to your `INSTALLED_APPS` and `MIDDLEWARE`. You probably
don't want to run it in production: I haven't profiled it but it will have a performance
impact.

```python
if DEBUG:
    INSTALLED_APPS.append("queryspy")
    MIDDLEWARE.append("queryspy.middleware.queryspy_middleware")
```

This will detect N+1s that happen in web requests. If you also want to find N+1s in other
places like background tasks or management commands, you can use the `setup` and
`teardown` functions, or the `queryspy_context` context manager:

```python
from queryspy import setup, teardown, queryspy_context


def foo():
    setup()
    try:
        # ...
    finally:
        teardown()


@queryspy_context()
def bar():
    # ...


def baz():
    with queryspy_context():
        # ...
```

For example, if you use Celery, you can configure this using [signals](https://docs.celeryq.dev/en/stable/userguide/signals.html):

```python
from celery.signals import task_prerun, task_postrun
from queryspy import setup, teardown
from django.conf import settings

if settings.DEBUG:
    @task_prerun.connect()
    def setup_queryspy(*args, **kwargs):
        setup()

    @task_postrun.connect()
    def teardown_queryspy(*args, **kwargs):
        teardown()
```

## Configuration

By default, N+1s will be reported when the same query is executed twice. To configure this
threshold, set the following in your Django settings.

```python
QUERYSPY_NPLUSONE_THRESHOLD = 3
```

## Contributing

1. First, install [uv](https://github.com/astral-sh/uv).
2. Create a virtual env using `uv venv` and activate it with `source .venv/bin/activate`.
3. Run `make install` to install dev dependencies.
4. To run tests, run `make test`.

