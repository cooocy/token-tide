from token_tide.config import Settings
from token_tide.providers.base import BalanceProvider
from token_tide.providers.deepseek import DeepSeekProvider
from token_tide.providers.openrouter import OpenRouterProvider
from token_tide.providers.siliconflow import SiliconFlowProvider
from token_tide.providers.xai import XaiProvider


def create_providers(settings: Settings) -> dict[str, BalanceProvider]:
    providers: list[BalanceProvider] = [
        OpenRouterProvider(settings.providers.openrouter, settings.http.timeout_seconds),
        DeepSeekProvider(settings.providers.deepseek, settings.http.timeout_seconds),
        SiliconFlowProvider(settings.providers.siliconflow, settings.http.timeout_seconds),
        XaiProvider(settings.providers.xai, settings.http.timeout_seconds),
    ]
    return {provider.name: provider for provider in providers if provider.enabled}
