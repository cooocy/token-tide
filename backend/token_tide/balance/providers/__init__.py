from token_tide.balance.config import DEFAULT_PROVIDER_ORDER, ProviderName
from token_tide.balance.providers.base import BalanceProvider
from token_tide.balance.providers.deepseek import DeepSeekProvider
from token_tide.balance.providers.opencode import OpenCodeProvider
from token_tide.balance.providers.openrouter import OpenRouterProvider
from token_tide.balance.providers.siliconflow import SiliconFlowProvider
from token_tide.balance.providers.xai import XaiProvider
from token_tide.config import Settings


def create_providers(settings: Settings) -> dict[str, BalanceProvider]:
    providers: dict[ProviderName, BalanceProvider] = {
        "openrouter": OpenRouterProvider(
            settings.providers.openrouter,
            settings.http.timeout_seconds,
        ),
        "deepseek": DeepSeekProvider(
            settings.providers.deepseek,
            settings.http.timeout_seconds,
        ),
        "siliconflow": SiliconFlowProvider(
            settings.providers.siliconflow,
            settings.http.timeout_seconds,
        ),
        "xai": XaiProvider(
            settings.providers.xai,
            settings.http.timeout_seconds,
        ),
        "opencode": OpenCodeProvider(
            settings.providers.opencode,
            settings.http.timeout_seconds,
        ),
    }
    configured_order = settings.providers.order
    resolved_order = [
        *configured_order,
        *(name for name in DEFAULT_PROVIDER_ORDER if name not in configured_order),
    ]
    return {name: providers[name] for name in resolved_order if providers[name].enabled}
