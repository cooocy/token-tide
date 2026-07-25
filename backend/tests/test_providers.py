from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from token_tide.config import ProviderSettings, XaiProviderSettings
from token_tide.providers.base import ProviderError
from token_tide.providers.deepseek import DeepSeekProvider
from token_tide.providers.openrouter import OpenRouterProvider
from token_tide.providers.siliconflow import SiliconFlowProvider
from token_tide.providers.xai import XaiProvider


def provider_settings(base_url: str, proxy_url: str | None = None) -> ProviderSettings:
    values: dict[str, object] = {
        "enabled": True,
        "api-key": "secret",
        "base-url": base_url,
    }
    if proxy_url is not None:
        values["proxy-url"] = proxy_url
    return ProviderSettings.model_validate(values)


@pytest.mark.parametrize(
    ("proxy_url", "expected_proxy"),
    [
        (None, None),
        ("http://127.0.0.1:3128", "http://127.0.0.1:3128/"),
    ],
)
@pytest.mark.asyncio
async def test_provider_request_uses_only_configured_proxy(
    monkeypatch: pytest.MonkeyPatch,
    proxy_url: str | None,
    expected_proxy: str | None,
) -> None:
    captured: dict[str, Any] = {}

    class StubResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict[str, object]:
            return {"ok": True}

    class StubClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def __aenter__(self) -> "StubClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def get(self, path: str) -> StubResponse:
            captured["path"] = path
            return StubResponse()

    monkeypatch.setattr(httpx, "AsyncClient", StubClient)
    provider = OpenRouterProvider(
        provider_settings("https://openrouter.ai", proxy_url),
        10,
    )

    await provider.get_json("/api/v1/credits")

    assert captured["proxy"] == expected_proxy
    assert captured["trust_env"] is False
    assert captured["path"] == "/api/v1/credits"


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
                },
                {
                    "currency": "USD",
                    "total_balance": "5.00",
                },
            ],
        }
    )

    readings = await provider.fetch_balance()

    assert [reading.currency for reading in readings] == ["CNY", "USD"]
    assert readings[0].available_amount == Decimal("110.00")


@pytest.mark.asyncio
async def test_siliconflow_available_balance() -> None:
    provider = SiliconFlowProvider(provider_settings("https://api.siliconflow.com"), 10)
    provider.get_json = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "status": True,
            "data": {
                "totalBalance": "88.88",
            },
        }
    )

    readings = await provider.fetch_balance()

    assert readings[0].available_amount == Decimal("88.88")


@pytest.mark.asyncio
@pytest.mark.parametrize("used_value", ["135", "-135"])
async def test_xai_subtracts_used_prepaid_credits_from_available_balance(
    used_value: str,
) -> None:
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
        return_value={
            "coreInvoice": {
                "prepaidCredits": {"val": "-500"},
                "prepaidCreditsUsed": {"val": used_value},
            }
        }
    )

    readings = await provider.fetch_balance()

    provider.get_json.assert_awaited_once_with(
        "/v1/billing/teams/team-id/postpaid/invoice/preview"
    )
    assert readings[0].available_amount == Decimal("3.65")
    assert readings[0].is_available is True


@pytest.mark.asyncio
async def test_xai_requires_prepaid_usage_in_invoice_preview() -> None:
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
        return_value={
            "coreInvoice": {
                "prepaidCredits": {"val": "-500"},
            }
        }
    )

    with pytest.raises(
        ProviderError,
        match=r"xAI response is missing coreInvoice\.prepaidCreditsUsed",
    ):
        await provider.fetch_balance()
