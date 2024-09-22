import inspect

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


def get_caller() -> inspect.FrameInfo:
    """
    Returns the filename and line number of the current caller,
    excluding any code in site-packages or zeal.
    """
    return next(frame for frame in get_stack())


def is_single_query(query: Query):
    return (
        query.high_mark is not None and query.high_mark - query.low_mark == 1
    )
