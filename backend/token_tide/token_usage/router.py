from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Response

from token_tide.response import ApplicationError, R, ok
from token_tide.token_usage.card import (
    UsageCardPeriod,
    UsageCardTheme,
    UsageCardTool,
    find_card_summary,
    render_usage_card,
)
from token_tide.token_usage.dependencies import (
    get_token_usage_service,
    require_token_usage_token,
)
from token_tide.token_usage.domain import TokenUsageTool
from token_tide.token_usage.schemas import (
    TokenUsageBatchInput,
    TokenUsageBatchResult,
    TokenUsageCalendar,
    TokenUsageCheckpointValue,
    TokenUsageOverview,
    TokenUsageSummary,
    TokenUsageTotals,
)
from token_tide.token_usage.service import TokenUsageService

router = APIRouter(prefix="/token-usage")
Service = Annotated[TokenUsageService, Depends(get_token_usage_service)]


@router.get(
    "/card.svg",
    response_class=Response,
    responses={
        200: {
            "content": {"image/svg+xml": {}},
            "description": "GitHub Profile token usage card",
        }
    },
)
def find_card(
    service: Service,
    period: UsageCardPeriod = UsageCardPeriod.SEVEN_DAYS,
    tool: UsageCardTool = UsageCardTool.ALL,
    theme: UsageCardTheme = UsageCardTheme.DARK,
    timezone: str = Query(default="Asia/Shanghai", min_length=1, max_length=64),
) -> Response:
    summary = find_card_summary(
        service=service,
        period=period,
        tool=tool,
        timezone_name=timezone,
    )
    return Response(
        content=render_usage_card(summary, period, tool, theme),
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=600, stale-while-revalidate=60",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/overview",
    response_model=R[TokenUsageOverview],
)
def find_overview(service: Service) -> R[TokenUsageOverview]:
    return ok(service.overview())


@router.get(
    "/calendar",
    response_model=R[TokenUsageCalendar],
)
def find_calendar(
    service: Service,
    start_date: date = Query(alias="start-date"),
    end_date: date = Query(alias="end-date"),
    timezone: str = Query(min_length=1, max_length=64),
) -> R[TokenUsageCalendar]:
    try:
        calendar_timezone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ApplicationError(
            422,
            42208,
            "Unknown token usage calendar timezone",
        ) from None
    return ok(
        service.calendar(
            start_date=start_date,
            end_date=end_date,
            calendar_timezone=calendar_timezone,
            timezone_name=timezone,
        )
    )


@router.get(
    "/summary",
    response_model=R[TokenUsageSummary],
)
def find_summary(
    service: Service,
    start_time: datetime = Query(alias="start-time"),
    end_time: datetime = Query(alias="end-time"),
    timezone_offset_minutes: int = Query(
        alias="timezone-offset-minutes",
        ge=-840,
        le=840,
    ),
    tool: TokenUsageTool | None = None,
) -> R[TokenUsageSummary]:
    return ok(
        service.summary(
            tool=tool,
            start_time=start_time,
            end_time=end_time,
            timezone_offset_minutes=timezone_offset_minutes,
        )
    )


@router.get(
    "/totals",
    response_model=R[TokenUsageTotals],
)
def find_totals(
    service: Service,
    tool: TokenUsageTool | None = None,
) -> R[TokenUsageTotals]:
    return ok(service.totals(tool))


@router.get(
    "/{tool}/checkpoint",
    response_model=R[TokenUsageCheckpointValue],
    dependencies=[Depends(require_token_usage_token)],
)
def find_checkpoint(
    tool: TokenUsageTool,
    service: Service,
) -> R[TokenUsageCheckpointValue]:
    return ok(service.checkpoint(tool))


@router.post(
    "/{tool}/events/batch",
    response_model=R[TokenUsageBatchResult],
    dependencies=[Depends(require_token_usage_token)],
)
def ingest_events(
    tool: TokenUsageTool,
    batch: TokenUsageBatchInput,
    service: Service,
) -> R[TokenUsageBatchResult]:
    return ok(service.ingest(tool, batch))
