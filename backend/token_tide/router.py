from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from token_tide.dependencies import get_balance_service
from token_tide.response import R, ok
from token_tide.schemas import BalanceHistory, ProviderBalance, ProviderRefreshResult
from token_tide.service import BalanceService

router = APIRouter(prefix="/api")
Service = Annotated[BalanceService, Depends(get_balance_service)]


@router.get("/balances", response_model=R[list[ProviderBalance]])
def find_balances(service: Service) -> R[list[ProviderBalance]]:
    return ok(service.latest_balances())


@router.get(
    "/balances/{provider}/history",
    response_model=R[BalanceHistory],
)
def find_balance_history(
    provider: str,
    service: Service,
    currency: str | None = None,
    start_time: datetime | None = Query(default=None, alias="start-time"),
    end_time: datetime | None = Query(default=None, alias="end-time"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> R[BalanceHistory]:
    return ok(
        service.balance_history(
            provider_name=provider.lower(),
            currency=currency,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
    )


@router.post("/refresh", response_model=R[list[ProviderRefreshResult]])
async def refresh_all(service: Service) -> R[list[ProviderRefreshResult]]:
    return ok(await service.refresh_all("MANUAL"))


@router.post(
    "/refresh/{provider}",
    response_model=R[ProviderRefreshResult],
)
async def refresh_provider(
    provider: str,
    service: Service,
) -> R[ProviderRefreshResult]:
    return ok(await service.refresh_provider(provider.lower(), "MANUAL"))
