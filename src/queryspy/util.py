import inspect

PATTERNS = ["site-packages", "queryspy/listeners.py", "queryspy/patch.py"]


def get_caller() -> inspect.FrameInfo:
    """
    Returns the filename and line number of the current caller,
    excluding any code in site-packages or queryspy.
    """
    return next(
        frame
        for frame in inspect.stack()[1:]
        if not any(pattern in frame.filename for pattern in PATTERNS)
    )
