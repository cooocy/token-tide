from unittest.mock import Mock, patch

from token_tide.balance.router import router
from token_tide.main import application_info, main
from token_tide.token_usage.router import router as token_usage_router


def test_application_info_uses_unknown_commit_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("TOKEN_TIDE_COMMIT", raising=False)

    response = application_info()

    assert response.data is not None
    assert response.data.app == "token-tide"
    assert response.data.ts.endswith("Z")
    assert response.data.token_tide_commit == "unknown"


def test_main_bootstraps_before_configuring_and_starting() -> None:
    events: list[str] = []
    settings = Mock()
    settings.server.host = "127.0.0.1"
    settings.server.port = 8800

    with (
        patch(
            "token_tide.main.configure_application_logging",
            side_effect=lambda: events.append("logging"),
        ),
        patch(
            "token_tide.main.bootstrap_settings",
            side_effect=lambda: (events.append("bootstrap"), settings)[1],
        ),
        patch(
            "token_tide.main.configure_app",
            side_effect=lambda _settings: events.append("configure"),
        ),
        patch(
            "token_tide.main.uvicorn.run",
            side_effect=lambda *_args, **_kwargs: events.append("uvicorn"),
        ),
    ):
        main()

    assert events == ["logging", "bootstrap", "configure", "uvicorn"]


def test_business_routes_do_not_include_reverse_proxy_prefix() -> None:
    route_paths = {route.path for route in router.routes}

    assert route_paths == {
        "/balances",
        "/balances/{provider}/history",
        "/refresh",
        "/refresh/{provider}",
    }

    assert {route.path for route in token_usage_router.routes} == {
        "/token-usage/{tool}/checkpoint",
        "/token-usage/{tool}/events/batch",
    }
