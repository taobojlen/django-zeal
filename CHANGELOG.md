# Changelog

## Unreleased

### Added

- Add support for Python 3.9+

## [0.2.0](https://github.com/taobojlen/zealot/compare/v0.1.2...v0.2.0) (2024-07-06)


### Features

* add support for python 3.9 ([#2](https://github.com/taobojlen/zealot/issues/2)) ([44e5f41](https://github.com/taobojlen/zealot/commit/44e5f41fc247e98683a1dd283ae70322a32445d6))

## 0.1.2 - 2024-07-06

### Fixed

- Handle empty querysets
- Handle incorrectly-used `.prefetch_related()` when `.select_related()` should have been used
- Don't raise an exception when using `.values(...).get()`

## 0.1.1 - 2024-07-05

### Fixed

- Ignore N+1s from singly-loaded records

## 0.1.0 - 2024-05-03

Initial release.
