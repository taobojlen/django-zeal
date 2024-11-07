import pytest
import pytest_django
import pytest_mock
from djangoproject.social import models
from zeal import errors

from . import factories

pytestmark = pytest.mark.django_db


def test_signal_send_message(
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
    settings: pytest_django.fixtures.SettingsWrapper,
):
    """Test signal send message after detecting N+1 query."""
    settings.ZEAL_RAISE = False
    patched_signal = mocker.patch(
        "zeal.listeners.nplusone_detected.send",
    )
    user_1, user_2 = factories.UserFactory.create_batch(2)
    factories.PostFactory.create(author=user_1)
    factories.PostFactory.create(author=user_2)
    _ = [
        post.author.username
        for post in models.Post.objects.all()
    ]
    patched_signal.assert_called_once()

