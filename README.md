# django-zeal

Catch N+1 queries in your Django project.

[![Static Badge](https://img.shields.io/badge/license-MIT-brightgreen)](https://github.com/taobojlen/django-zeal/blob/main/LICENSE)
[![PyPI - Version](https://img.shields.io/pypi/v/django-zeal?color=lightgrey)](https://pypi.org/project/django-zeal/)

🔥 Battle-tested at [Cinder](https://www.cinder.co/)

## Features

- Detects N+1s from missing prefetches and from use of `.defer()`/`.only()`
- Friendly error messages like `N+1 detected on social.User.followers at myapp/views.py:25 in get_user`
- Configurable thresholds
- Allow-list
- Well-tested
- No dependencies

## Acknowledgements

This library draws heavily from jmcarp's [nplusone](https://github.com/jmcarp/nplusone/).
It's not a fork, but a lot of the central concepts and initial code came from nplusone.

## Installation

First:

```
pip install django-zeal
```

Then, add zeal to your `INSTALLED_APPS` and `MIDDLEWARE`.

```python
if DEBUG:
    INSTALLED_APPS.append("zeal")
    MIDDLEWARE.append("zeal.middleware.zeal_middleware")
```

This will detect N+1s that happen in web requests. To catch N+1s in more places,
read on!

> [!WARNING]  
> You probably don't want to run zeal in production:
> there is significant overhead to detecting N+1s, and my benchmarks show that it
> can make your code between 2.5x - 7x slower.

### Celery

If you use Celery, you can configure this using [signals](https://docs.celeryq.dev/en/stable/userguide/signals.html):

```python
from celery.signals import task_prerun, task_postrun
from zeal import setup, teardown
from django.conf import settings

@task_prerun.connect()
def setup_zeal(*args, **kwargs):
    setup()

@task_postrun.connect()
def teardown_zeal(*args, **kwargs):
    teardown()
```

### Tests

Django [runs tests with `DEBUG=False`](https://docs.djangoproject.com/en/5.0/topics/testing/overview/#other-test-conditions),
so to run zeal in your tests, you'll first need to ensure it's added to your
`INSTALLED_APPS` and `MIDDLEWARE`. You could do something like:

```python
import sys

TEST = "test" in sys.argv
if DEBUG or TEST:
    INSTALLED_APPS.append("zeal")
    MIDDLEWARE.append("zeal.middleware.zeal_middleware")
```

This will enable zeal in any tests that go through your middleware. If you want to enable
it in _all_ tests, you need to do a bit more work.

If you use pytest, use a fixture in your `conftest.py`:

```python
import pytest
from zeal import zeal_context

@pytest.fixture(scope="function", autouse=True)
def use_zeal():
    with zeal_context():
        yield
```

If you use unittest, add custom test cases and inherit from these rather than directly from Django's test cases:

```python
# In e.g. `myapp/testing/test_cases.py`
from zeal import setup as zeal_setup, teardown as zeal_teardown
import unittest
from django.test import SimpleTestCase, TestCase, TransactionTestCase

class ZealTestMixin(unittest.TestCase):
    def setUp(self, test):
        zeal_setup()
        super().setUp()

    def teardown(self) -> None:
        zeal_teardown()
        return super().teardown(test, err)

class CustomSimpleTestCase(ZealTestMixin, SimpleTestCase):
    pass

class CustomTestCase(ZealTestMixin, TestCase):
    pass

class CustomTransactionTestCase(ZealTestMixin, TransactionTestCase):
    pass
```

### Generic setup

If you also want to detect N+1s in other places not covered here, you can use the `setup` and
`teardown` functions, or the `zeal_context` context manager:

```python
from zeal import setup, teardown, zeal_context


def foo():
    setup()
    try:
        # your code goes here
    finally:
        teardown()


@zeal_context()
def bar():
    # your code goes here


def baz():
    with zeal_context():
        # your code goes here
```

## Configuration

By default, any issues detected by zeal will raise a `ZealError`. If you'd
rather log any detected N+1s as warnings, you can set:

```python
ZEAL_RAISE = False
```

N+1s will be reported when the same query is executed twice. To configure this
threshold, set the following in your Django settings.

```python
ZEAL_NPLUSONE_THRESHOLD = 3
```

To handle false positives, you can temporarily disable zeal in parts of your code
using a context manager:

```python
from zeal import zeal_ignore

with zeal_ignore():
    # code in this block will not log/raise zeal errors
```

If you only want to ignore a specific N+1, you can pass in a list of models/fields to ignore:

```python
with zeal_ignore([{"model": "polls.Question", "field": "options"}]):
    # code in this block will ignore N+1s on Question.options
```

If you want to listen to N+1 exceptions globally and do something with them, you can listen to the Django signal that zeal emits:

```python
from zeal.signals import nplusone_detected
from django.dispatch import receiver

@receiver(nplusone_detected)
def handle_nplusone(sender, exception):
    # do something
```

Finally, if you want to ignore N+1 alerts from a specific model/field globally, you can
add it to your settings:

```python
ZEAL_ALLOWLIST = [
    {"model": "polls.Question", "field": "options"},

    # you can use fnmatch syntax in the model/field, too
    {"model": "polls.*", "field": "options"},

    # if you don't pass in a field, all N+1s arising from the model will be ignored
    {"model": "polls.Question"},
]
```


## Debugging N+1s

By default, zeal's alerts will tell you the line of your code that executed the same query
multiple times. If you'd like to see the full call stack from each time the query was executed,
you can set:

```python
ZEAL_SHOW_ALL_CALLERS = True
```

in your settings. This will give you the full call stack from each time the query was executed.

## Comparison to nplusone

zeal borrows heavily from [nplusone](https://github.com/jmcarp/nplusone), but has some differences:

- zeal also detects N+1 caused by using `.only()` and `.defer()`
- it lets you configure your own threshold for what constitutes an N+1
- it has slightly more helpful error messages that tell you where the N+1 occurred
- nplusone patches the Django ORM even in production when it's not enabled. zeal does not!
- nplusone appears to be abandoned at this point.
- however, zeal only works with Django, whereas nplusone can also be used with SQLAlchemy.
- zeal does not (yet) detect unused prefetches, but nplusone does.

## Contributing

1. First, install [uv](https://github.com/astral-sh/uv).
2. Create a virtual env using `uv venv` and activate it with `source .venv/bin/activate`.
3. Run `make install` to install dev dependencies.
4. To run tests, run `make test`.
