import pytest
from zeal import zeal_context


@pytest.fixture(scope="function", autouse=True)
def use_zeal(request):
    if "nozeal" in request.keywords:
        yield
    else:
        with zeal_context():
            yield
