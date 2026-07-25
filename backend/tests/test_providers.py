from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from token_tide.config import ProviderSettings, XaiProviderSettings
from token_tide.providers.deepseek import DeepSeekProvider
from token_tide.providers.openrouter import OpenRouterProvider
from token_tide.providers.siliconflow import SiliconFlowProvider
from token_tide.providers.xai import XaiProvider


def provider_settings(base_url: str) -> ProviderSettings:
    return ProviderSettings.model_validate(
        {"enabled": True, "api-key": "secret", "base-url": base_url}
    )


@pytest.mark.asyncio
async def test_openrouter_balance_is_credits_minus_usage() -> None:
    provider = OpenRouterProvider(provider_settings("https://openrouter.ai"), 10)
    provider.get_json = AsyncMock(  # type: ignore[method-assign]
        return_value={"data": {"total_credits": 100.5, "total_usage": 25.25}}
    )

    readings = await provider.fetch_balance()

    assert readings[0].available_amount == Decimal("75.25")
    assert readings[0].currency == "USD"


@pytest.mark.asyncio
async def test_deepseek_returns_each_currency() -> None:
    provider = DeepSeekProvider(provider_settings("https://api.deepseek.com"), 10)
    provider.get_json = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "is_available": True,
            "balance_infos": [
                {
                    "currency": "CNY",
                    "total_balance": "110.00",
                    "granted_balance": "10.00",
                    "topped_up_balance": "100.00",
                },
                {
                    "currency": "USD",
                    "total_balance": "5.00",
                    "granted_balance": "0.00",
                    "topped_up_balance": "5.00",
                },
            ],
        }
    )

    readings = await provider.fetch_balance()

    assert [reading.currency for reading in readings] == ["CNY", "USD"]
    assert readings[0].prepaid_amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_siliconflow_balance_components() -> None:
    provider = SiliconFlowProvider(provider_settings("https://api.siliconflow.com"), 10)
    provider.get_json = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "status": True,
            "data": {
                "balance": "0.88",
                "chargeBalance": "88.00",
                "totalBalance": "88.88",
            },
        }
    )

    readings = await provider.fetch_balance()

    assert readings[0].available_amount == Decimal("88.88")
    assert readings[0].granted_amount == Decimal("0.88")


@pytest.mark.asyncio
async def test_xai_converts_negative_cents_to_available_usd() -> None:
    settings = XaiProviderSettings.model_validate(
        {
            "enabled": True,
            "api-key": "management-secret",
            "base-url": "https://management-api.x.ai",
            "team-id": "team-id",
        }
    )
    provider = XaiProvider(settings, 10)
    provider.get_json = AsyncMock(  # type: ignore[method-assign]
        return_value={"changes": [], "total": {"val": "-1000"}}
    )

    readings = await provider.fetch_balance()

    assert readings[0].available_amount == Decimal("10")
