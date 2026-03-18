import os
import sys

from django.db.models.sql import Query

_ZEAL_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_internal_frame(fn: str) -> bool:
    """Check if a filename belongs to site-packages or zeal internals."""
    return "site-packages" in fn or fn.startswith(_ZEAL_DIR)


def get_caller() -> tuple[str, int, str]:
    """
    Returns (filename, lineno, funcname) of the first caller outside
    site-packages/zeal, walking raw frame objects.
    """
    frame = sys._getframe(1)
    while frame is not None:
        fn = frame.f_code.co_filename
        if not _is_internal_frame(fn):
            result = (fn, frame.f_lineno, frame.f_code.co_name)
            del frame
            return result
        frame = frame.f_back
    return ("<unknown>", 0, "<unknown>")


def get_stack() -> list[tuple[str, int, str]]:
    """
    Returns the current call stack as (filename, lineno, funcname) tuples,
    excluding site-packages and zeal internals.
    """
    result = []
    frame = sys._getframe(1)
    while frame is not None:
        fn = frame.f_code.co_filename
        if not _is_internal_frame(fn):
            result.append((fn, frame.f_lineno, frame.f_code.co_name))
        frame = frame.f_back
    return result


def is_single_query(query: Query):
    return (
        query.high_mark is not None and query.high_mark - query.low_mark == 1
    )
