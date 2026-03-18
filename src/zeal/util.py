import inspect
import sys

from django.db.models.sql import Query

PATTERNS = [
    "site-packages",
    "zeal/listeners.py",
    "zeal/patch.py",
    "zeal/util.py",
]


def get_stack() -> list[inspect.FrameInfo]:
    """
    Returns the current call stack, excluding any code in site-packages or zeal.
    """
    return [
        frame
        for frame in inspect.stack(context=0)[1:]
        if not any(pattern in frame.filename for pattern in PATTERNS)
    ]


def get_caller(stack: list[inspect.FrameInfo]) -> inspect.FrameInfo:
    """
    Returns the filename and line number of the current caller,
    excluding any code in site-packages or zeal.
    """
    return next(frame for frame in stack)


def get_caller_fast() -> tuple[str, int, str]:
    """
    Fast path: walk raw frame objects to find the first caller outside
    site-packages/zeal. Returns (filename, lineno, funcname) without
    allocating FrameInfo named tuples.
    """
    frame = sys._getframe(1)
    while frame is not None:
        fn = frame.f_code.co_filename
        if not any(pattern in fn for pattern in PATTERNS):
            result = (fn, frame.f_lineno, frame.f_code.co_name)
            del frame
            return result
        frame = frame.f_back
    # Fallback: should never happen in practice
    return ("<unknown>", 0, "<unknown>")


def is_single_query(query: Query):
    return (
        query.high_mark is not None and query.high_mark - query.low_mark == 1
    )
