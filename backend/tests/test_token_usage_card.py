from datetime import UTC, date, datetime
from unittest.mock import Mock

import pytest

from token_tide.response import ApplicationError
from token_tide.token_usage.card import (
    CARD_HEIGHT,
    CARD_WIDTH,
    UsageCardPeriod,
    UsageCardTheme,
    UsageCardTool,
    find_card_summary,
    format_compact_count,
    render_usage_card,
)
from token_tide.token_usage.domain import TokenUsageTool
from token_tide.token_usage.router import find_card
from token_tide.token_usage.schemas import (
    TokenUsageDay,
    TokenUsageSummary,
    TokenUsageToolSummary,
    TokenUsageTotals,
)
from token_tide.token_usage.service import TokenUsageService


def summary(total_tokens: int = 145) -> TokenUsageSummary:
    return TokenUsageSummary(
        start_time=datetime(2026, 7, 29, 16, tzinfo=UTC),
        end_time=datetime(2026, 8, 5, 8, tzinfo=UTC),
        timezone_offset_minutes=480,
        totals=TokenUsageTotals(
            event_count=2,
            input_tokens=95,
            output_tokens=50,
            total_tokens=total_tokens,
        ),
        tools=[
            TokenUsageToolSummary(
                tool=TokenUsageTool.CLAUDE,
                event_count=1,
                total_tokens=45 if total_tokens else 0,
            ),
            TokenUsageToolSummary(
                tool=TokenUsageTool.CODEX,
                event_count=1,
                total_tokens=100 if total_tokens else 0,
            ),
            TokenUsageToolSummary(tool=TokenUsageTool.OPENCODE),
            TokenUsageToolSummary(tool=TokenUsageTool.PI),
        ],
        timeline=[
            TokenUsageDay(
                date=date(2026, 8, 4),
                total_tokens=100 if total_tokens else 0,
                tools={
                    TokenUsageTool.CLAUDE: 0,
                    TokenUsageTool.CODEX: 100 if total_tokens else 0,
                    TokenUsageTool.OPENCODE: 0,
                    TokenUsageTool.PI: 0,
                },
            ),
            TokenUsageDay(
                date=date(2026, 8, 5),
                total_tokens=45 if total_tokens else 0,
                tools={
                    TokenUsageTool.CLAUDE: 45 if total_tokens else 0,
                    TokenUsageTool.CODEX: 0,
                    TokenUsageTool.OPENCODE: 0,
                    TokenUsageTool.PI: 0,
                },
            ),
        ],
        models=[],
    )


@pytest.mark.parametrize(
    ("period", "expected_start"),
    [
        (UsageCardPeriod.SEVEN_DAYS, "2026-07-30T00:00:00+08:00"),
        (UsageCardPeriod.THIRTY_DAYS, "2026-07-07T00:00:00+08:00"),
    ],
)
def test_find_card_summary_uses_local_calendar_range(
    period: UsageCardPeriod,
    expected_start: str,
) -> None:
    service = Mock(spec=TokenUsageService)
    service.summary.return_value = summary()
    now = datetime(2026, 8, 5, 8, tzinfo=UTC)

    result = find_card_summary(
        service=service,
        period=period,
        tool=UsageCardTool.CODEX,
        timezone_name="Asia/Shanghai",
        now=now,
    )

    assert result is service.summary.return_value
    arguments = service.summary.call_args.kwargs
    assert arguments["tool"] is TokenUsageTool.CODEX
    assert arguments["start_time"].isoformat() == expected_start
    assert arguments["end_time"] == now
    assert arguments["timezone_offset_minutes"] == 480
    assert arguments["calendar_timezone"].key == "Asia/Shanghai"


def test_card_query_values_are_stable() -> None:
    assert [period.value for period in UsageCardPeriod] == ["7d", "30d"]
    assert [tool.value for tool in UsageCardTool] == [
        "all",
        "claude",
        "codex",
        "opencode",
        "pi",
    ]
    assert [theme.value for theme in UsageCardTheme] == ["dark", "light"]


def test_find_card_summary_rejects_unknown_timezone() -> None:
    service = Mock(spec=TokenUsageService)

    with pytest.raises(ApplicationError) as error:
        find_card_summary(
            service=service,
            period=UsageCardPeriod.SEVEN_DAYS,
            tool=UsageCardTool.ALL,
            timezone_name="Mars/Olympus_Mons",
        )

    assert error.value.status_code == 422
    assert error.value.code == 42205
    service.summary.assert_not_called()


def test_render_usage_card_contains_metrics_tide_and_dark_palette() -> None:
    svg = render_usage_card(
        summary(),
        UsageCardPeriod.SEVEN_DAYS,
        UsageCardTool.ALL,
        UsageCardTheme.DARK,
    )

    assert f'width="{CARD_WIDTH}" height="{CARD_HEIGHT}"' in svg
    assert 'viewBox="0 0 720 220"' in svg
    assert "7 DAY TOKENS" in svg
    assert ">145<" in svg
    assert ">45<" in svg
    assert "2 requests" in svg
    assert "Claude" in svg
    assert "31.0%" in svg
    assert "Codex" in svg
    assert "69.0%" in svg
    assert '<polyline points="' in svg
    assert '#071820' in svg
    assert '<script' not in svg
    assert '<foreignObject' not in svg


def test_render_usage_card_uses_one_background_and_aligned_columns() -> None:
    svg = render_usage_card(
        summary(),
        UsageCardPeriod.SEVEN_DAYS,
        UsageCardTool.ALL,
        UsageCardTheme.DARK,
    )

    assert 'x="12" y="12" width="210" height="196"' not in svg
    assert "Tokens by local day" not in svg
    assert "Share of Tokens" not in svg
    assert '<path d="M230 20V200M548 20V200"' in svg
    assert '<text class="display" x="50" y="38"' in svg
    assert '<text class="kicker" x="250" y="38">DAILY TIDE</text>' in svg
    assert '<text class="kicker" x="570" y="38">TOOL MIX</text>' in svg
    assert 'y="56.00"' in svg
    assert '<text class="data" x="24" y="193"' in svg
    assert '<rect x="570" y="177" width="126" height="22"' in svg


def test_render_usage_card_has_light_theme_and_empty_direction() -> None:
    svg = render_usage_card(
        summary(total_tokens=0),
        UsageCardPeriod.THIRTY_DAYS,
        UsageCardTool.PI,
        UsageCardTheme.LIGHT,
    )

    assert "30 DAY TOKENS" in svg
    assert "No usage yet" in svg
    assert "PI" in svg
    assert "#f2fbfa" in svg
    assert "#12333a" in svg


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (999, "999"),
        (1_200, "1.2K"),
        (1_250, "1.3K"),
        (999_999, "1M"),
        (12_340_000, "12.3M"),
        (1_000_000_000, "1B"),
    ],
)
def test_format_compact_count(value: int, expected: str) -> None:
    assert format_compact_count(value) == expected


def test_card_route_returns_svg_with_cache_and_security_headers() -> None:
    service = Mock(spec=TokenUsageService)
    service.summary.return_value = summary()

    response = find_card(
        service=service,
        period=UsageCardPeriod.SEVEN_DAYS,
        tool=UsageCardTool.ALL,
        theme=UsageCardTheme.DARK,
        timezone="Asia/Shanghai",
    )

    assert response.media_type == "image/svg+xml"
    assert response.headers["content-type"] == "image/svg+xml"
    assert response.headers["cache-control"] == (
        "public, max-age=600, stale-while-revalidate=60"
    )
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; style-src 'unsafe-inline'"
    )
    assert response.body.startswith(b"<svg")
