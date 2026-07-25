from pathlib import Path

import pytest

from token_tide.config import ConfigurationError, load_settings


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
