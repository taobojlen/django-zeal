import inspect

from django.db.models.sql import Query

PATTERNS = ["site-packages", "zeal/listeners.py", "zeal/patch.py"]


def get_caller() -> inspect.FrameInfo:
    """
    Returns the filename and line number of the current caller,
    excluding any code in site-packages or zeal.
    """
    return next(
        frame
        for frame in inspect.stack()[1:]
        if not any(pattern in frame.filename for pattern in PATTERNS)
    )


def is_single_query(query: Query):
    return (
        query.high_mark is not None and query.high_mark - query.low_mark == 1
    )
