from token_tide.providers.base import BalanceProvider, BalanceReading, ProviderError, decimal_value


class DeepSeekProvider(BalanceProvider):
    name = "deepseek"

    async def fetch_balance(self) -> list[BalanceReading]:
        payload = await self.get_json("/user/balance")
        balances = payload.get("balance_infos")
        if not isinstance(balances, list):
            raise ProviderError("invalid_response", "DeepSeek response is missing balance_infos")

        readings: list[BalanceReading] = []
        for balance in balances:
            if not isinstance(balance, dict):
                raise ProviderError("invalid_response", "DeepSeek returned an invalid balance item")
            currency = str(balance.get("currency", "")).upper()
            if not currency:
                raise ProviderError("invalid_response", "DeepSeek balance is missing currency")
            readings.append(
                BalanceReading(
                    provider=self.name,
                    currency=currency,
                    available_amount=decimal_value(balance.get("total_balance"), "total_balance"),
                    prepaid_amount=decimal_value(
                        balance.get("topped_up_balance"),
                        "topped_up_balance",
                    ),
                    granted_amount=decimal_value(
                        balance.get("granted_balance"),
                        "granted_balance",
                    ),
                    is_available=bool(payload.get("is_available")),
                )
            )
        return readings
