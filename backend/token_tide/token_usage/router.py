from typing import Annotated

from fastapi import APIRouter, Depends

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
)
from token_tide.token_usage.service import TokenUsageService

router = APIRouter(
    prefix="/token-usage",
    dependencies=[Depends(require_token_usage_token)],
)
Service = Annotated[TokenUsageService, Depends(get_token_usage_service)]


@router.get(
    "/{tool}/checkpoint",
    response_model=R[TokenUsageCheckpointValue],
)
def find_checkpoint(
    tool: TokenUsageTool,
    service: Service,
) -> R[TokenUsageCheckpointValue]:
    return ok(service.checkpoint(tool))


@router.post(
    "/{tool}/events/batch",
    response_model=R[TokenUsageBatchResult],
)
def ingest_events(
    tool: TokenUsageTool,
    batch: TokenUsageBatchInput,
    service: Service,
) -> R[TokenUsageBatchResult]:
    return ok(service.ingest(tool, batch))
