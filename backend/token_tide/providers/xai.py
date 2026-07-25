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
            f"/v1/billing/teams/{self.xai_settings.team_id}/postpaid/invoice/preview"
        )
        core_invoice = payload.get("coreInvoice")
        if not isinstance(core_invoice, dict):
            raise ProviderError("invalid_response", "xAI response is missing coreInvoice")
        prepaid_credits = core_invoice.get("prepaidCredits")
        if not isinstance(prepaid_credits, dict):
            raise ProviderError(
                "invalid_response",
                "xAI response is missing coreInvoice.prepaidCredits",
            )
        prepaid_credits_used = core_invoice.get("prepaidCreditsUsed")
        if not isinstance(prepaid_credits_used, dict):
            raise ProviderError(
                "invalid_response",
                "xAI response is missing coreInvoice.prepaidCreditsUsed",
            )

        # 预充值额度按记账方向为负数，已使用额度为正数，单位均为美分。
        prepaid = (
            -decimal_value(
                prepaid_credits.get("val"),
                "coreInvoice.prepaidCredits.val",
            )
            / Decimal(100)
        )
        used = (
            decimal_value(
                prepaid_credits_used.get("val"),
                "coreInvoice.prepaidCreditsUsed.val",
            )
            / Decimal(100)
        )
        available = prepaid - used
        return [
            BalanceReading(
                provider=self.name,
                currency="USD",
                available_amount=available,
                prepaid_amount=prepaid,
                granted_amount=None,
                is_available=available > 0,
            )
        ]
