# Changelog

## [2.0.2](https://github.com/taobojlen/django-zeal/compare/v2.0.1...v2.0.2) (2024-11-22)


### Bug Fixes

* **#28:** prevent infinite recursion when custom __eq__ is used. ([#43](https://github.com/taobojlen/django-zeal/issues/43)) ([d157059](https://github.com/taobojlen/django-zeal/commit/d1570593bde02cd5f020fcbfb21350df03e43026))

## [2.0.1](https://github.com/taobojlen/django-zeal/compare/v2.0.0...v2.0.1) (2024-11-13)


### Bug Fixes

* use correct field name in forward many-to-many fields ([#39](https://github.com/taobojlen/django-zeal/issues/39)) ([3ada66f](https://github.com/taobojlen/django-zeal/commit/3ada66fa8f9b9c79acd9f2c45b35cb4967770e04))

## [2.0.0](https://github.com/taobojlen/django-zeal/compare/v1.4.1...v2.0.0) (2024-11-12)


### Features

* add app name to error messages ([#34](https://github.com/taobojlen/django-zeal/issues/34)) ([ad6fe5f](https://github.com/taobojlen/django-zeal/commit/ad6fe5f6599de26ee9adf30cd372cd3fcb7cded0))
* Add Django signal for zeal errors ([#31](https://github.com/taobojlen/django-zeal/issues/31)) ([1190ca7](https://github.com/taobojlen/django-zeal/commit/1190ca73b5e714c3ded3b979e0fb09935928abca))
* validate the allowlist ([#33](https://github.com/taobojlen/django-zeal/issues/33)) ([2aa1b42](https://github.com/taobojlen/django-zeal/commit/2aa1b42c3a441d6b66f52dd2ba70abc6ffe5efee))


### Bug Fixes

* handle related field names in allowlist validation ([#36](https://github.com/taobojlen/django-zeal/issues/36)) ([654eed6](https://github.com/taobojlen/django-zeal/commit/654eed692b9b6e0a17d5c5edc4ec74a2ae0783c9))
* use custom error class for validation errors ([#37](https://github.com/taobojlen/django-zeal/issues/37)) ([035ae35](https://github.com/taobojlen/django-zeal/commit/035ae3574e3bf29e1c24d896d5c3cd4100d1002b))


### Miscellaneous Chores

* make breaking change ([5eed8ec](https://github.com/taobojlen/django-zeal/commit/5eed8ec26e89f657e659d37acbf51c4ef8c4bed4))

## [1.4.1](https://github.com/taobojlen/django-zeal/compare/v1.4.0...v1.4.1) (2024-09-22)


### Performance Improvements

* don't load context in callstack ([#26](https://github.com/taobojlen/django-zeal/issues/26)) ([5ade002](https://github.com/taobojlen/django-zeal/commit/5ade0023be95173506167e5cd50388a8dbb5b5e9))

## [1.4.0](https://github.com/taobojlen/django-zeal/compare/v1.3.0...v1.4.0) (2024-09-03)

**NOTE**: In versions 1.1.0 - 1.3.0, there was a bug that caused `zeal` to be active
in all code, even outside of a `zeal_context` block. That is fixed in 1.4.0. When updating,
make sure that you have installed zeal correctly as per the README.

### Features

* add async support to middleware ([#23](https://github.com/taobojlen/django-zeal/issues/23)) ([815bc16](https://github.com/taobojlen/django-zeal/commit/815bc1651e98a4519a42dfa088dcac4320350a1c))


### Bug Fixes

* only run zeal inside context ([#21](https://github.com/taobojlen/django-zeal/issues/21)) ([6c88fd2](https://github.com/taobojlen/django-zeal/commit/6c88fd247388cf58a3c2291917623b7e8094442b))

## [1.3.0](https://github.com/taobojlen/django-zeal/compare/v1.2.0...v1.3.0) (2024-07-25)


### Features

* add ZEAL_SHOW_ALL_CALLERS to aid in debugging ([#17](https://github.com/taobojlen/django-zeal/issues/17)) ([7fdaf36](https://github.com/taobojlen/django-zeal/commit/7fdaf36db50fed6dee0b0544205e71035c977541))

## [1.2.0](https://github.com/taobojlen/django-zeal/compare/v1.1.0...v1.2.0) (2024-07-22)


### Features

* use warnings instead of logging ([#15](https://github.com/taobojlen/django-zeal/issues/15)) ([df2c841](https://github.com/taobojlen/django-zeal/commit/df2c841b21fae664c14356d00a7a2f6ecbb7fd61))

## [1.1.0](https://github.com/taobojlen/django-zeal/compare/v1.0.0...v1.1.0) (2024-07-20)


### Features

* allow ignoring specific models/fields in zeal_ignore ([#13](https://github.com/taobojlen/django-zeal/issues/13)) ([e51413b](https://github.com/taobojlen/django-zeal/commit/e51413ba5fe4d9a3c34409863e9888d873ff84fa))

## [1.0.0](https://github.com/taobojlen/zealot/compare/v0.2.3...v1.0.0) (2024-07-20)


### ⚠ BREAKING CHANGES

This project has been renamed to `zeal`. To migrate, replace `zealot` with `zeal` in your
project's requirements. In your Django settings, replace `ZEALOT_ALLOWLIST`, `ZEALOT_RAISE`, etc.
with `ZEAL_ALLOWLIST`, `ZEAL_RAISE`, and so on.
In your code, replace `from zealot import ...` with `from zeal import ...`.


### Miscellaneous Chores

* rename to zeal ([cc429a2](https://github.com/taobojlen/zealot/commit/cc429a26bfede770db69429e8a11fc9e98fbb2a9))

## [0.2.3](https://github.com/taobojlen/zeal/compare/v0.2.2...v0.2.3) (2024-07-18)


### Bug Fixes

* ensure context is reset after leaving ([#8](https://github.com/taobojlen/zeal/issues/8)) ([f45cabb](https://github.com/taobojlen/zeal/commit/f45cabb2abcabce34cd5aed163f7f95c71256e2c))

## [0.2.2](https://github.com/taobojlen/zeal/compare/v0.2.1...v0.2.2) (2024-07-15)


### Bug Fixes

* don't alert from calls on different lines ([7f7bda7](https://github.com/taobojlen/zeal/commit/7f7bda709e5fff2e953ddac0277d684255732e7c))

## [0.2.1](https://github.com/taobojlen/zeal/compare/v0.2.0...v0.2.1) (2024-07-08)


### Bug Fixes

* zeal_ignore always takes precedence ([e61d060](https://github.com/taobojlen/zeal/commit/e61d060c74ed32193c2c86f1b7f20929a37402a1))

## [0.2.0](https://github.com/taobojlen/zeal/compare/v0.1.2...v0.2.0) (2024-07-06)


### Features

* add support for python 3.9 ([#2](https://github.com/taobojlen/zeal/issues/2)) ([44e5f41](https://github.com/taobojlen/zeal/commit/44e5f41fc247e98683a1dd283ae70322a32445d6))

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
