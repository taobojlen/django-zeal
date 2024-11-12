import warnings

import pytest
import pytest_django
import pytest_mock
from djangoproject.social import models
from zeal import errors
from zeal.listeners import n_plus_one_listener

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
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        _ = [post.author.username for post in models.Post.objects.all()]
    patched_signal.assert_called_once()
    sender = patched_signal.call_args[1]["sender"]
    assert sender == n_plus_one_listener
    exception = patched_signal.call_args[1]["exception"]
    assert isinstance(exception, errors.NPlusOneError)
    assert "N+1 detected on social.Post.author" in str(exception)
