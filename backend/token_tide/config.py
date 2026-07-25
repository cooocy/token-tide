import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator


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


class ProviderSettings(ConfigurationModel):
    enabled: bool = False
    api_key: SecretStr = SecretStr("")
    base_url: str = Field(min_length=1)

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


class ProvidersSettings(ConfigurationModel):
    openrouter: ProviderSettings
    deepseek: ProviderSettings
    siliconflow: ProviderSettings
    xai: XaiProviderSettings


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
