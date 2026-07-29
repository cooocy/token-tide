import json
import re
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx

from token_tide.balance.config import OpenCodeProviderSettings
from token_tide.balance.providers.base import (
    BalanceProvider,
    BalanceReading,
    ProviderError,
    decimal_value,
)

BILLING_SERVER_ID = "c83b78a614689c38ebee981f9b39a8b377716db85c1fd7dbab604adc02d3313d"
BILLING_SCALE = Decimal("100000000")
CUSTOMER_ID_PATTERN = re.compile(
    r'(?:"customerID"|customerID)\s*:\s*'
    r'(?:\$R\[\d+\]\s*=\s*)?"[^"]+"'
)
BALANCE_PATTERN = re.compile(
    r'(?:"balance"|balance)\s*:\s*'
    r"(?:\$R\[\d+\]\s*=\s*)?(-?\d+(?:\.\d+)?)"
)


def find_raw_balance(value: object) -> Decimal | None:
    if isinstance(value, dict):
        customer_id = value.get("customerID")
        if isinstance(customer_id, str) and customer_id and "balance" in value:
            return decimal_value(value["balance"], "balance")
        for nested in value.values():
            balance = find_raw_balance(nested)
            if balance is not None:
                return balance
    elif isinstance(value, list):
        for nested in value:
            balance = find_raw_balance(nested)
            if balance is not None:
                return balance
    return None


def parse_balance_response(text: str) -> Decimal:
    lower_text = text.lower()
    if any(
        marker in lower_text
        for marker in (
            "auth/authorize",
            'actor of type "public"',
            "not associated with an account",
        )
    ):
        raise ProviderError(
            "authentication_failed",
            "OpenCode session cookie is invalid or expired",
        )

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    raw_balance = find_raw_balance(payload)
    if raw_balance is None:
        if CUSTOMER_ID_PATTERN.search(text) is None:
            raise ProviderError(
                "invalid_response",
                "OpenCode response is missing customer context",
            )
        match = BALANCE_PATTERN.search(text)
        if match is None:
            raise ProviderError(
                "invalid_response",
                "OpenCode response is missing balance",
            )
        raw_balance = decimal_value(match.group(1), "balance")
    return raw_balance / BILLING_SCALE


class OpenCodeProvider(BalanceProvider):
    name = "opencode"

    def __init__(
        self,
        settings: OpenCodeProviderSettings,
        timeout_seconds: float,
    ) -> None:
        super().__init__(settings, timeout_seconds)
        self.opencode_settings = settings

    async def fetch_balance(self) -> list[BalanceReading]:
        base_url = self.opencode_settings.base_url.rstrip("/")
        workspace_id = self.opencode_settings.workspace_id.strip()
        headers = {
            "Accept": "text/javascript, application/json;q=0.9, */*;q=0.8",
            "Cookie": self.opencode_settings.auth_cookie.get_secret_value().strip(),
            "Origin": base_url,
            "Referer": f"{base_url}/workspace/{workspace_id}",
            "User-Agent": "Mozilla/5.0",
            "X-Server-Id": BILLING_SERVER_ID,
            "X-Server-Instance": f"server-fn:{uuid4()}",
        }
        params = {
            "id": BILLING_SERVER_ID,
            "args": json.dumps([workspace_id], separators=(",", ":")),
        }

        try:
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=self.timeout_seconds,
                proxy=(
                    str(self.opencode_settings.proxy_url)
                    if self.opencode_settings.proxy_url is not None
                    else None
                ),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.get("/_server", headers=headers, params=params)
                response.raise_for_status()
                text = response.text
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise ProviderError(
                f"http_{status}",
                f"Provider returned HTTP {status}",
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("request_failed", "Provider request failed") from exc

        available = parse_balance_response(text)
        return [
            BalanceReading(
                provider=self.name,
                currency="USD",
                available_amount=available,
                is_available=available > 0,
            )
        ]
