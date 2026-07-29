from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from token_tide.balance.config import (
    OpenCodeProviderSettings,
    ProviderSettings,
    XaiProviderSettings,
)
from token_tide.balance.providers import create_providers
from token_tide.balance.providers.base import ProviderError
from token_tide.balance.providers.deepseek import DeepSeekProvider
from token_tide.balance.providers.opencode import (
    OpenCodeProvider,
    parse_balance_response,
)
from token_tide.balance.providers.openrouter import OpenRouterProvider
from token_tide.balance.providers.siliconflow import SiliconFlowProvider
from token_tide.balance.providers.xai import XaiProvider
from token_tide.config import Settings


def provider_settings(base_url: str, proxy_url: str | None = None) -> ProviderSettings:
    values: dict[str, object] = {
        "enabled": True,
        "api-key": "secret",
        "base-url": base_url,
    }
    if proxy_url is not None:
        values["proxy-url"] = proxy_url
    return ProviderSettings.model_validate(values)


def test_create_providers_applies_custom_order_and_appends_omissions() -> None:
    settings = Settings.model_validate(
        {
            "server": {
                "host": "127.0.0.1",
                "port": 8800,
            },
            "database": {
                "url": "mysql+pymysql://user:pass@localhost/token_tide",
            },
            "http": {
                "timeout-seconds": 10,
            },
            "refresh": {
                "cron": "0 * * * *",
                "timezone": "UTC",
            },
            "providers": {
                "order": ["opencode", "xai"],
                "openrouter": {
                    "enabled": True,
                    "api-key": "secret",
                    "base-url": "https://openrouter.ai",
                },
                "deepseek": {
                    "enabled": True,
                    "api-key": "secret",
                    "base-url": "https://api.deepseek.com",
                },
                "siliconflow": {
                    "enabled": False,
                    "api-key": "",
                    "base-url": "https://api.siliconflow.com",
                },
                "xai": {
                    "enabled": False,
                    "api-key": "",
                    "base-url": "https://management-api.x.ai",
                    "team-id": "",
                },
                "opencode": {
                    "enabled": True,
                    "auth-cookie": "auth=session-secret",
                    "workspace-id": "wrk_01EXAMPLE",
                    "base-url": "https://opencode.ai",
                },
            },
        }
    )

    providers = create_providers(settings)

    assert list(providers) == ["opencode", "openrouter", "deepseek"]


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


def opencode_settings(
    proxy_url: str | None = None,
) -> OpenCodeProviderSettings:
    values: dict[str, object] = {
        "enabled": True,
        "auth-cookie": "auth=session-secret",
        "workspace-id": "wrk_01EXAMPLE",
        "base-url": "https://opencode.ai",
    }
    if proxy_url is not None:
        values["proxy-url"] = proxy_url
    return OpenCodeProviderSettings.model_validate(values)


@pytest.mark.asyncio
async def test_opencode_requests_billing_rpc_without_redirects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class StubResponse:
        text = '{"billing":{"customerID":"cus_example","balance":1916000000}}'

        def raise_for_status(self) -> None:
            pass

    class StubClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def __aenter__(self) -> "StubClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            pass

        async def get(
            self,
            path: str,
            **kwargs: Any,
        ) -> StubResponse:
            captured["path"] = path
            captured.update(kwargs)
            return StubResponse()

    monkeypatch.setattr(httpx, "AsyncClient", StubClient)
    provider = OpenCodeProvider(
        opencode_settings("http://127.0.0.1:3128"),
        10,
    )

    readings = await provider.fetch_balance()

    assert captured["base_url"] == "https://opencode.ai"
    assert captured["proxy"] == "http://127.0.0.1:3128/"
    assert captured["trust_env"] is False
    assert captured["follow_redirects"] is False
    assert captured["path"] == "/_server"
    assert captured["params"]["args"] == '["wrk_01EXAMPLE"]'
    assert captured["headers"]["Cookie"] == "auth=session-secret"
    assert captured["headers"]["Origin"] == "https://opencode.ai"
    assert readings[0].available_amount == Decimal("19.16")
    assert readings[0].currency == "USD"


def test_opencode_parses_server_javascript_response() -> None:
    response = (
        '{customerID:$R[0]="cus_example",'
        'balance:$R[1]=1916000000}'
    )

    assert parse_balance_response(response) == Decimal("19.16")


def test_opencode_requires_customer_context() -> None:
    with pytest.raises(
        ProviderError,
        match="OpenCode response is missing customer context",
    ):
        parse_balance_response('{"balance":1916000000}')


def test_opencode_recognizes_expired_session_response() -> None:
    with pytest.raises(
        ProviderError,
        match="OpenCode session cookie is invalid or expired",
    ):
        parse_balance_response('Actor of type "public" cannot access workspace')
