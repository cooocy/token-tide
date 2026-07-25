from functools import lru_cache

from token_tide.config import get_settings
from token_tide.database import get_session_factory
from token_tide.providers import create_providers
from token_tide.service import BalanceService


@lru_cache
def get_balance_service() -> BalanceService:
    return BalanceService(
        providers=create_providers(get_settings()),
        session_factory=get_session_factory(),
    )
