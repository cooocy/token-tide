from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from token_tide.response import R, ok
from token_tide.token_usage.dependencies import (
    get_token_usage_service,
    require_token_usage_token,
)
from token_tide.token_usage.domain import TokenUsageTool
from token_tide.token_usage.schemas import (
    TokenUsageBatchInput,
    TokenUsageBatchResult,
    TokenUsageCheckpointValue,
    TokenUsageOverview,
    TokenUsageSummary,
    TokenUsageTotals,
)
from token_tide.token_usage.service import TokenUsageService

router = APIRouter(prefix="/token-usage")
Service = Annotated[TokenUsageService, Depends(get_token_usage_service)]


@router.get(
    "/overview",
    response_model=R[TokenUsageOverview],
)
def find_overview(service: Service) -> R[TokenUsageOverview]:
    return ok(service.overview())


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
