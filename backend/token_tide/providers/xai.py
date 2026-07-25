from decimal import Decimal

from token_tide.config import XaiProviderSettings
from token_tide.providers.base import BalanceProvider, BalanceReading, ProviderError, decimal_value


class XaiProvider(BalanceProvider):
    name = "xai"

    def __init__(self, settings: XaiProviderSettings, timeout_seconds: float) -> None:
        super().__init__(settings, timeout_seconds)
        self.xai_settings = settings

    async def fetch_balance(self) -> list[BalanceReading]:
        payload = await self.get_json(
            f"/v1/billing/teams/{self.xai_settings.team_id}/prepaid/balance"
        )
        total = payload.get("total")
        if not isinstance(total, dict):
            raise ProviderError("invalid_response", "xAI response is missing total")

        # Management API 以记账方向返回余额；可用预付额度是负数美分。
        available = -decimal_value(total.get("val"), "total.val") / Decimal(100)
        return [
            BalanceReading(
                provider=self.name,
                currency="USD",
                available_amount=available,
                prepaid_amount=available,
                granted_amount=None,
                is_available=available > 0,
            )
        ]
