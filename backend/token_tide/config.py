import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    ValidationError,
    field_validator,
    model_validator,
)

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


def to_kebab(field_name: str) -> str:
    return field_name.replace("_", "-")


class ConfigurationError(RuntimeError):
    """Raised when application configuration cannot be loaded."""


class ConfigurationModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_kebab,
        populate_by_name=False,
        extra="forbid",
    )


class ServerSettings(ConfigurationModel):
    host: str = Field(min_length=1)
    port: int = Field(gt=0, le=65535)
    cors_origins: list[str] = Field(default_factory=list)


class DatabaseSettings(ConfigurationModel):
    url: str = Field(min_length=1)


class HttpSettings(ConfigurationModel):
    timeout_seconds: float = Field(default=15, gt=0)


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
        if (
            name not in {"auth", "__Host-auth"}
            or not separator
            or not value
        ):
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


class Settings(ConfigurationModel):
    environment: Literal["development", "production"] = "development"
    server: ServerSettings
    database: DatabaseSettings
    http: HttpSettings
    refresh: RefreshSettings
    providers: ProvidersSettings


def configuration_path() -> Path:
    tail = os.environ.get("CONFIGURATION_TAIL", "")
    if not tail:
        raise ConfigurationError("CONFIGURATION_TAIL environment variable is not set")
    return Path.cwd() / f"application-{tail}.yaml"


def load_settings(path: Path) -> Settings:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"Unable to read configuration file: {path}") from exc

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML configuration: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")

    try:
        return Settings.model_validate(data)
    except ValidationError:
        # Pydantic 的原始校验错误可能携带输入值；这里切断异常链，避免密钥进入启动日志。
        raise ConfigurationError(f"Invalid application configuration: {path}") from None


@lru_cache
def get_settings() -> Settings:
    return load_settings(configuration_path())
