from pathlib import Path

import pytest
from pydantic import ValidationError

from token_tide.config import (
    ConfigurationError,
    OpenCodeProviderSettings,
    ProviderSettings,
    load_settings,
)


def test_enabled_provider_requires_api_key(tmp_path: Path) -> None:
    path = tmp_path / "application-test.yaml"
    path.write_text(
        """
server:
  host: 127.0.0.1
  port: 8800
database:
  url: mysql+pymysql://user:pass@localhost/token_tide
http:
  timeout-seconds: 10
refresh:
  cron: "0 * * * *"
  timezone: UTC
providers:
  openrouter:
    enabled: true
    api-key: ""
    base-url: https://openrouter.ai
  deepseek:
    enabled: false
    api-key: ""
    base-url: https://api.deepseek.com
  siliconflow:
    enabled: false
    api-key: ""
    base-url: https://api.siliconflow.com
  xai:
    enabled: false
    api-key: ""
    base-url: https://management-api.x.ai
    team-id: ""
  opencode:
    enabled: false
    auth-cookie: ""
    workspace-id: ""
    base-url: https://opencode.ai
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_settings(path)


def test_configuration_without_opencode_defaults_to_disabled(tmp_path: Path) -> None:
    path = tmp_path / "application-test.yaml"
    path.write_text(
        """
server:
  host: 127.0.0.1
  port: 8800
database:
  url: mysql+pymysql://user:pass@localhost/token_tide
http:
  timeout-seconds: 10
refresh:
  cron: "0 * * * *"
  timezone: UTC
providers:
  openrouter:
    enabled: false
    api-key: ""
    base-url: https://openrouter.ai
  deepseek:
    enabled: false
    api-key: ""
    base-url: https://api.deepseek.com
  siliconflow:
    enabled: false
    api-key: ""
    base-url: https://api.siliconflow.com
  xai:
    enabled: false
    api-key: ""
    base-url: https://management-api.x.ai
    team-id: ""
""",
        encoding="utf-8",
    )

    settings = load_settings(path)

    assert settings.providers.opencode.enabled is False
    assert settings.providers.opencode.base_url == "https://opencode.ai"


def test_provider_proxy_url_accepts_http_proxy() -> None:
    settings = ProviderSettings.model_validate(
        {
            "enabled": True,
            "api-key": "secret",
            "base-url": "https://management-api.x.ai",
            "proxy-url": "http://127.0.0.1:3128",
        }
    )

    assert str(settings.proxy_url) == "http://127.0.0.1:3128/"


def test_provider_proxy_url_rejects_non_http_scheme() -> None:
    with pytest.raises(ValidationError):
        ProviderSettings.model_validate(
            {
                "enabled": True,
                "api-key": "secret",
                "base-url": "https://management-api.x.ai",
                "proxy-url": "socks5://127.0.0.1:1080",
            }
        )


def test_enabled_opencode_extracts_auth_cookie_from_cookie_header() -> None:
    settings = OpenCodeProviderSettings.model_validate(
        {
            "enabled": True,
            "auth-cookie": "theme=dark; auth=secret; another=value",
            "workspace-id": "wrk_01EXAMPLE",
            "base-url": "https://opencode.ai",
        }
    )

    assert settings.auth_cookie.get_secret_value() == "auth=secret"


def test_enabled_opencode_accepts_raw_cookie_value() -> None:
    settings = OpenCodeProviderSettings.model_validate(
        {
            "enabled": True,
            "auth-cookie": "session-secret",
            "workspace-id": "wrk_01EXAMPLE",
            "base-url": "https://opencode.ai",
        }
    )

    assert settings.auth_cookie.get_secret_value() == "auth=session-secret"


def test_enabled_opencode_rejects_non_opencode_base_url() -> None:
    with pytest.raises(ValidationError):
        OpenCodeProviderSettings.model_validate(
            {
                "enabled": True,
                "auth-cookie": "auth=secret",
                "workspace-id": "wrk_01EXAMPLE",
                "base-url": "https://example.com",
            }
        )


def test_enabled_opencode_accepts_host_auth_cookie() -> None:
    settings = OpenCodeProviderSettings.model_validate(
        {
            "enabled": True,
            "auth-cookie": "__Host-auth=secret",
            "workspace-id": "wrk_01EXAMPLE",
            "base-url": "https://opencode.ai",
        }
    )

    assert settings.workspace_id == "wrk_01EXAMPLE"
