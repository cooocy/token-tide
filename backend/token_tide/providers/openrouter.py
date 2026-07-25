from token_tide.providers.base import BalanceProvider, BalanceReading, ProviderError, decimal_value


class OpenRouterProvider(BalanceProvider):
    name = "openrouter"

    async def fetch_balance(self) -> list[BalanceReading]:
        payload = await self.get_json("/api/v1/credits")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ProviderError("invalid_response", "OpenRouter response is missing data")
        total_credits = decimal_value(data.get("total_credits"), "total_credits")
        total_usage = decimal_value(data.get("total_usage"), "total_usage")
        available = total_credits - total_usage
        return [
            BalanceReading(
                provider=self.name,
                currency="USD",
                available_amount=available,
                is_available=available > 0,
            )
        ]
