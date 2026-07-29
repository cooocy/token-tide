import re
from typing import Literal

from pydantic import (
    AnyHttpUrl,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from token_tide.configuration import ConfigurationModel

ProviderName = Literal[
    "openrouter",
    "deepseek",
    "siliconflow",
    "xai",
    "opencode",
]
DEFAULT_PROVIDER_ORDER: tuple[ProviderName, ...] = (
    "openrouter",
    "deepseek",
    "siliconflow",
    "xai",
    "opencode",
)


class RefreshSettings(ConfigurationModel):
    cron: str = Field(min_length=1)
    timezone: str = Field(min_length=1)


class ProviderConnectionSettings(ConfigurationModel):
    enabled: bool = False
    base_url: str = Field(min_length=1)
    proxy_url: AnyHttpUrl | None = None


class ProviderSettings(ProviderConnectionSettings):
    api_key: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def validate_enabled_provider(self) -> "ProviderSettings":
        if self.enabled and not self.api_key.get_secret_value().strip():
            raise ValueError("api-key is required when provider is enabled")
        return self


class XaiProviderSettings(ProviderSettings):
    team_id: str = ""

    @model_validator(mode="after")
    def validate_team_id(self) -> "XaiProviderSettings":
        if self.enabled and not self.team_id.strip():
            raise ValueError("team-id is required when xAI is enabled")
        return self


class OpenCodeProviderSettings(ProviderConnectionSettings):
    base_url: str = "https://opencode.ai"
    auth_cookie: SecretStr = SecretStr("")
    workspace_id: str = ""

    @field_validator("auth_cookie", mode="before")
    @classmethod
    def normalize_auth_cookie(cls, value: object) -> object:
        if isinstance(value, SecretStr):
            raw_cookie = value.get_secret_value().strip()
        elif isinstance(value, str):
            raw_cookie = value.strip()
        else:
            return value

        if not raw_cookie:
            return raw_cookie
        if "\r" in raw_cookie or "\n" in raw_cookie:
            raise ValueError("auth-cookie must not contain line breaks")

        cookie_parts = [part.strip() for part in raw_cookie.split(";") if part.strip()]
        auth_cookies = [
            part
            for part in cookie_parts
            if part.partition("=")[0] in {"auth", "__Host-auth"}
            and bool(part.partition("=")[2])
        ]
        if len(auth_cookies) == 1:
            return auth_cookies[0]
        if len(auth_cookies) > 1:
            raise ValueError("auth-cookie contains multiple authentication cookies")
        if len(cookie_parts) == 1:
            return f"auth={raw_cookie}"
        raise ValueError("auth-cookie header does not contain auth or __Host-auth")

    @model_validator(mode="after")
    def validate_enabled_provider(self) -> "OpenCodeProviderSettings":
        if not self.enabled:
            return self

        cookie = self.auth_cookie.get_secret_value().strip()
        name, separator, value = cookie.partition("=")
        if name not in {"auth", "__Host-auth"} or not separator or not value:
            raise ValueError(
                "auth-cookie must contain exactly one auth=... or __Host-auth=... cookie"
            )
        if re.fullmatch(r"wrk_[A-Za-z0-9]+", self.workspace_id.strip()) is None:
            raise ValueError("workspace-id must use the wrk_... format")

        base_url = self.base_url.rstrip("/")
        if base_url != "https://opencode.ai":
            raise ValueError(
                "base-url must be https://opencode.ai when OpenCode is enabled"
            )
        return self


class ProvidersSettings(ConfigurationModel):
    order: list[ProviderName] = Field(
        default_factory=lambda: list(DEFAULT_PROVIDER_ORDER)
    )
    openrouter: ProviderSettings
    deepseek: ProviderSettings
    siliconflow: ProviderSettings
    xai: XaiProviderSettings
    opencode: OpenCodeProviderSettings = Field(default_factory=OpenCodeProviderSettings)

    @field_validator("order")
    @classmethod
    def validate_order(cls, value: list[ProviderName]) -> list[ProviderName]:
        if len(value) != len(set(value)):
            raise ValueError("order must not contain duplicate provider names")
        return value
