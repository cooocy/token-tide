from pathlib import Path

import pytest
from pydantic import ValidationError

from token_tide.config import ConfigurationError, ProviderSettings, load_settings


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
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigurationError):
        load_settings(path)


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
