# Changelog

## [0.2.3](https://github.com/taobojlen/zealot/compare/v0.2.2...v0.2.3) (2024-07-18)


### Bug Fixes

* ensure context is reset after leaving ([#8](https://github.com/taobojlen/zealot/issues/8)) ([f45cabb](https://github.com/taobojlen/zealot/commit/f45cabb2abcabce34cd5aed163f7f95c71256e2c))

## [0.2.2](https://github.com/taobojlen/zealot/compare/v0.2.1...v0.2.2) (2024-07-15)


### Bug Fixes

* don't alert from calls on different lines ([7f7bda7](https://github.com/taobojlen/zealot/commit/7f7bda709e5fff2e953ddac0277d684255732e7c))

## [0.2.1](https://github.com/taobojlen/zealot/compare/v0.2.0...v0.2.1) (2024-07-08)


### Bug Fixes

* zealot_ignore always takes precedence ([e61d060](https://github.com/taobojlen/zealot/commit/e61d060c74ed32193c2c86f1b7f20929a37402a1))

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
