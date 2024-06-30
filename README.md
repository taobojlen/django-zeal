# queryspy

This library catches N+1s in your Django project.

## Features

- Detects N+1s from missing prefetches and from `.defer()`/`.only()`
- Simple installation -- just add to your `INSTALLED_APPS` and it works everywhere
- Configurable thresholds
- TODO: allowlist
- TODO: catches unused eager loads
- Well-tested
- No dependencies

## Acknowledgements

This library draws very heavily on jmcarp's [nplusone](https://github.com/jmcarp/nplusone/).
It's not *exactly* a fork, but not far from it.

## Installation

TODO.

By default, N+1s will be reported when the same query is executed twice. To configure this
threshold, set the following in your Django settings.

```
QUERYSPY_NPLUSONE_THRESHOLD = 3
```

## Contributing

1. First, install [uv](https://github.com/astral-sh/uv).
2. Create a virtual env using `uv venv` and activate it with `source .venv/bin/activate`.
3. Run `make install` to install dev dependencies.
4. To run tests, run `make test`.

