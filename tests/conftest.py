import pytest
from zealot import zealot_context


@pytest.fixture(scope="function", autouse=True)
def use_zealot():
    with zealot_context():
        yield
