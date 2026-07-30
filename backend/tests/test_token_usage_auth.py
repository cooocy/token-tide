from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import SecretStr

from token_tide.response import ApplicationError
from token_tide.token_usage.dependencies import require_token_usage_token


def test_token_usage_auth_accepts_matching_bearer_token() -> None:
    settings = SimpleNamespace(
        token_usage=SimpleNamespace(auth_token=SecretStr("secret")),
    )
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="secret",
    )

    with patch("token_tide.token_usage.dependencies.get_settings", return_value=settings):
        require_token_usage_token(credentials)


@pytest.mark.parametrize(
    "credentials",
    [
        None,
        HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong"),
    ],
)
def test_token_usage_auth_rejects_missing_or_wrong_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> None:
    settings = SimpleNamespace(
        token_usage=SimpleNamespace(auth_token=SecretStr("secret")),
    )

    with (
        patch("token_tide.token_usage.dependencies.get_settings", return_value=settings),
        pytest.raises(ApplicationError) as error,
    ):
        require_token_usage_token(credentials)

    assert error.value.status_code == 401
