from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from token_tide.config import ProviderConnectionSettings, ProviderSettings


class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class BalanceReading:
    provider: str
    currency: str
    available_amount: Decimal
    is_available: bool


def decimal_value(value: object, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ProviderError("invalid_response", f"Invalid decimal value for {field}") from exc


class BalanceProvider(ABC):
    name: str

    def __init__(
        self,
        settings: ProviderConnectionSettings,
        timeout_seconds: float,
    ) -> None:
        self.settings = settings
        self.enabled = settings.enabled
        self.timeout_seconds = timeout_seconds

    async def get_json(self, path: str) -> dict[str, Any]:
        if not isinstance(self.settings, ProviderSettings):
            raise RuntimeError("Provider does not support Bearer API requests")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.settings.api_key.get_secret_value()}",
        }
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.base_url.rstrip("/"),
                headers=headers,
                timeout=self.timeout_seconds,
                proxy=(
                    str(self.settings.proxy_url)
                    if self.settings.proxy_url is not None
                    else None
                ),
                trust_env=False,
            ) as client:
                response = await client.get(path)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            raise ProviderError(f"http_{status}", f"Provider returned HTTP {status}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("request_failed", "Provider request failed") from exc
        if not isinstance(payload, dict):
            raise ProviderError("invalid_response", "Provider returned a non-object response")
        return payload

    @abstractmethod
    async def fetch_balance(self) -> list[BalanceReading]:
        raise NotImplementedError
