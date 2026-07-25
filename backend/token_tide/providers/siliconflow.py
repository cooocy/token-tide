from token_tide.providers.base import BalanceProvider, BalanceReading, ProviderError, decimal_value


class SiliconFlowProvider(BalanceProvider):
    name = "siliconflow"

    async def fetch_balance(self) -> list[BalanceReading]:
        payload = await self.get_json("/v1/user/info")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderError("invalid_response", "SiliconFlow response is missing data")
        available = decimal_value(data.get("totalBalance"), "totalBalance")
        return [
            BalanceReading(
                provider=self.name,
                currency="CNY",
                available_amount=available,
                granted_amount=decimal_value(data.get("balance"), "balance"),
                is_available=bool(payload.get("status")) and available > 0,
            )
        ]
