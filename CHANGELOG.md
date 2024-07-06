# Changelog

## Unreleased

### Fixed

- Handle empty querysets
- Handle incorrectly-used `.prefetch_related()` when `.select_related()` should have been used
- Don't raise an exception when using `.values(...).get()`

## 0.1.1 - 2024-07-05

### Fixed

- Ignore N+1s from singly-loaded records

## 0.1.0 - 2024-05-03

Initial release.
