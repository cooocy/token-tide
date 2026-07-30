import secrets
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from token_tide.config import get_settings
from token_tide.database import get_session_factory
from token_tide.response import ApplicationError
from token_tide.token_usage.service import TokenUsageService

bearer = HTTPBearer(auto_error=False)


def require_token_usage_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer),
    ],
) -> None:
    expected = get_settings().token_usage.auth_token.get_secret_value()
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.credentials, expected)
    ):
        raise ApplicationError(401, 40101, "Invalid token usage credentials")


@lru_cache
def get_token_usage_service() -> TokenUsageService:
    return TokenUsageService(get_session_factory())
