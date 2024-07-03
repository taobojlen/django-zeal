import inspect

PATTERNS = ["site-packages", "zealot/listeners.py", "zealot/patch.py"]


def get_caller() -> inspect.FrameInfo:
    """
    Returns the filename and line number of the current caller,
    excluding any code in site-packages or zealot.
    """
    return next(
        frame
        for frame in inspect.stack()[1:]
        if not any(pattern in frame.filename for pattern in PATTERNS)
    )
