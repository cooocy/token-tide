from datetime import date
from unittest.mock import Mock, patch

import pytest

from token_tide.balance.router import router
from token_tide.main import application_info, main
from token_tide.response import ApplicationError
from token_tide.token_usage.router import (
    find_calendar,
    router as token_usage_router,
)


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

    token_usage_routes = {
        route.path: route
        for route in token_usage_router.routes
    }
    assert set(token_usage_routes) == {
        "/token-usage/card.svg",
        "/token-usage/calendar",
        "/token-usage/overview",
        "/token-usage/summary",
        "/token-usage/totals",
        "/token-usage/{tool}/checkpoint",
        "/token-usage/{tool}/events/batch",
    }
    assert token_usage_routes["/token-usage/card.svg"].dependencies == []
    assert token_usage_routes["/token-usage/calendar"].dependencies == []
    assert token_usage_routes["/token-usage/overview"].dependencies == []
    assert token_usage_routes["/token-usage/summary"].dependencies == []
    assert token_usage_routes["/token-usage/totals"].dependencies == []
    assert len(
        token_usage_routes["/token-usage/{tool}/checkpoint"].dependencies
    ) == 1
    assert len(
        token_usage_routes["/token-usage/{tool}/events/batch"].dependencies
    ) == 1


def test_token_usage_calendar_rejects_unknown_timezone() -> None:
    with pytest.raises(ApplicationError, match="Unknown"):
        find_calendar(
            service=Mock(),
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 8),
            timezone="Mars/Olympus",
        )
