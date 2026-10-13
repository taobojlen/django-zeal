import pytest
from hypothesis import settings
from zeal import zeal_context

settings.register_profile("ci", max_examples=300, deadline=None)
settings.register_profile(
    "stress", settings.get_profile("ci"), max_examples=1500
)
settings.load_profile("ci")


@pytest.fixture(scope="function", autouse=True)
def use_zeal(request):
    if "nozeal" in request.keywords:
        yield
    else:
        with zeal_context():
            yield
