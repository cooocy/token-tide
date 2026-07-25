from unittest.mock import Mock, patch

from token_tide.bootstrap import bootstrap_settings


def test_downloads_remote_configuration_before_loading_settings() -> None:
    events: list[str] = []
    engine = object()
    settings = object()
    bookstore = Mock()
    bookstore.download_configuration.side_effect = lambda *_args: events.append(
        "download"
    )
    get_settings = Mock(side_effect=lambda: (events.append("load"), settings)[1])
    get_settings.cache_clear = Mock(side_effect=lambda: events.append("clear"))

    with (
        patch(
            "token_tide.bootstrap.StorageEngineFactory.new_storage_engine",
            return_value=engine,
        ),
        patch("token_tide.bootstrap.Bookstore", return_value=bookstore),
        patch("token_tide.bootstrap.get_settings", get_settings),
    ):
        result = bootstrap_settings()

    assert result is settings
    assert events == ["download", "clear", "load"]
    bookstore.download_configuration.assert_called_once_with(
        "token-tide/application-:tail.yaml",
        8000,
    )
