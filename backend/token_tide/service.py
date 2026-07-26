import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import overload

from sqlalchemy import Select, and_, desc, or_, select
from sqlalchemy.orm import Session

from token_tide.models import BalanceSnapshot, RefreshRun
from token_tide.providers.base import BalanceProvider, ProviderError
from token_tide.response import ApplicationError
from token_tide.schemas import (
    BalanceChangeType,
    BalanceHistory,
    BalanceValue,
    HistoryPoint,
    ProviderBalance,
    ProviderRefreshResult,
)

logger = logging.getLogger(__name__)
AMOUNT_QUANTUM = Decimal("0.01")


@overload
def normalize_amount(value: Decimal) -> Decimal: ...


@overload
def normalize_amount(value: None) -> None: ...


def normalize_amount(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(AMOUNT_QUANTUM, rounding=ROUND_HALF_UP)


def decimal_string(value: Decimal | None) -> str | None:
    normalized = normalize_amount(value)
    return None if normalized is None else format(normalized, ".2f")


class BalanceService:
    def __init__(
        self,
        providers: dict[str, BalanceProvider],
        session_factory: Callable[[], Session],
    ) -> None:
        self.providers = providers
        self.session_factory = session_factory

    def require_provider(self, provider_name: str) -> BalanceProvider:
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ApplicationError(404, 40401, f"Provider is not enabled: {provider_name}")
        return provider

    async def refresh_all(self, trigger: str) -> list[ProviderRefreshResult]:
        return list(
            await asyncio.gather(
                *(
                    self.refresh_provider(provider_name, trigger)
                    for provider_name in self.providers
                )
            )
        )

    async def refresh_provider(
        self,
        provider_name: str,
        trigger: str,
    ) -> ProviderRefreshResult:
        provider = self.require_provider(provider_name)
        started_at = datetime.now(UTC)
        run_id = self._create_refresh_run(provider_name, trigger, started_at)

        try:
            readings = await provider.fetch_balance()
            finished_at = datetime.now(UTC)
            with self.session_factory() as session:
                for reading in readings:
                    session.add(
                        BalanceSnapshot(
                            provider=reading.provider,
                            currency=reading.currency,
                            available_amount=normalize_amount(reading.available_amount),
                            is_available=reading.is_available,
                            observed_at=finished_at,
                        )
                    )
                run = session.get(RefreshRun, run_id)
                if run is None:
                    raise RuntimeError("Refresh run disappeared")
                run.status = "SUCCESS"
                run.finished_at = finished_at
                session.commit()
            return ProviderRefreshResult(
                provider=provider_name,
                status="SUCCESS",
                started_at=started_at,
                finished_at=finished_at,
                snapshot_count=len(readings),
            )
        except ProviderError as exc:
            return self._finish_failed_run(run_id, provider_name, started_at, exc.code, str(exc))
        except Exception:
            logger.exception("Unexpected refresh failure for provider %s", provider_name)
            return self._finish_failed_run(
                run_id,
                provider_name,
                started_at,
                "internal_error",
                "Unexpected provider refresh failure",
            )

    def latest_balances(self) -> list[ProviderBalance]:
        with self.session_factory() as session:
            return [
                self._latest_provider_balance(session, provider_name)
                for provider_name in self.providers
            ]

    def balance_history(
        self,
        provider_name: str,
        currency: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> BalanceHistory:
        self.require_provider(provider_name)
        statement: Select[tuple[BalanceSnapshot]] = select(BalanceSnapshot).where(
            BalanceSnapshot.provider == provider_name
        )
        normalized_currency = currency.upper() if currency else None
        if normalized_currency:
            statement = statement.where(BalanceSnapshot.currency == normalized_currency)
        if start_time:
            statement = statement.where(BalanceSnapshot.observed_at >= start_time)
        if end_time:
            statement = statement.where(BalanceSnapshot.observed_at <= end_time)
        statement = statement.order_by(
            desc(BalanceSnapshot.observed_at),
            desc(BalanceSnapshot.id),
        ).limit(limit)

        with self.session_factory() as session:
            snapshots = list(reversed(session.scalars(statement).all()))
            points = self._history_points(session, snapshots)
        return BalanceHistory(
            provider=provider_name,
            currency=normalized_currency,
            points=points,
        )

    def _create_refresh_run(self, provider: str, trigger: str, started_at: datetime) -> int:
        with self.session_factory() as session:
            run = RefreshRun(
                provider=provider,
                trigger=trigger,
                status="RUNNING",
                started_at=started_at,
            )
            session.add(run)
            session.commit()
            return run.id

    def _finish_failed_run(
        self,
        run_id: int,
        provider: str,
        started_at: datetime,
        error_code: str,
        error_message: str,
    ) -> ProviderRefreshResult:
        finished_at = datetime.now(UTC)
        with self.session_factory() as session:
            run = session.get(RefreshRun, run_id)
            if run is not None:
                run.status = "FAILED"
                run.finished_at = finished_at
                run.error_code = error_code
                run.error_message = error_message
                session.commit()
        return ProviderRefreshResult(
            provider=provider,
            status="FAILED",
            started_at=started_at,
            finished_at=finished_at,
            snapshot_count=0,
            error_code=error_code,
            error_message=error_message,
        )

    def _latest_provider_balance(
        self,
        session: Session,
        provider_name: str,
    ) -> ProviderBalance:
        last_run = session.scalar(
            select(RefreshRun)
            .where(RefreshRun.provider == provider_name)
            .order_by(desc(RefreshRun.started_at))
            .limit(1)
        )
        currencies = session.scalars(
            select(BalanceSnapshot.currency)
            .where(BalanceSnapshot.provider == provider_name)
            .distinct()
            .order_by(BalanceSnapshot.currency)
        ).all()
        snapshots = [
            snapshot
            for currency in currencies
            if (
                snapshot := session.scalar(
                    select(BalanceSnapshot)
                    .where(
                        BalanceSnapshot.provider == provider_name,
                        BalanceSnapshot.currency == currency,
                    )
                    .order_by(desc(BalanceSnapshot.observed_at))
                    .limit(1)
                )
            )
            is not None
        ]
        last_success_at = max(
            (snapshot.observed_at for snapshot in snapshots),
            default=None,
        )
        return ProviderBalance(
            provider=provider_name,
            status=last_run.status if last_run else "NEVER_REFRESHED",
            last_refresh_at=(
                (last_run.finished_at or last_run.started_at) if last_run else None
            ),
            last_success_at=last_success_at,
            error_code=last_run.error_code if last_run else None,
            error_message=last_run.error_message if last_run else None,
            balances=[self._balance_value(snapshot) for snapshot in snapshots],
        )

    @staticmethod
    def _balance_value(snapshot: BalanceSnapshot) -> BalanceValue:
        return BalanceValue(
            currency=snapshot.currency,
            available_amount=decimal_string(snapshot.available_amount) or "0",
            is_available=snapshot.is_available,
            observed_at=snapshot.observed_at,
        )

    def _history_points(
        self,
        session: Session,
        snapshots: list[BalanceSnapshot],
    ) -> list[HistoryPoint]:
        first_by_currency: dict[str, BalanceSnapshot] = {}
        for snapshot in snapshots:
            first_by_currency.setdefault(snapshot.currency, snapshot)

        previous_by_currency = {
            currency: self._previous_snapshot(session, first)
            for currency, first in first_by_currency.items()
        }
        points: list[HistoryPoint] = []
        for snapshot in snapshots:
            previous = previous_by_currency.get(snapshot.currency)
            points.append(self._history_point(snapshot, previous))
            previous_by_currency[snapshot.currency] = snapshot
        return points

    @staticmethod
    def _previous_snapshot(
        session: Session,
        snapshot: BalanceSnapshot,
    ) -> BalanceSnapshot | None:
        return session.scalar(
            select(BalanceSnapshot)
            .where(
                BalanceSnapshot.provider == snapshot.provider,
                BalanceSnapshot.currency == snapshot.currency,
                or_(
                    BalanceSnapshot.observed_at < snapshot.observed_at,
                    and_(
                        BalanceSnapshot.observed_at == snapshot.observed_at,
                        BalanceSnapshot.id < snapshot.id,
                    ),
                ),
            )
            .order_by(
                desc(BalanceSnapshot.observed_at),
                desc(BalanceSnapshot.id),
            )
            .limit(1)
        )

    @classmethod
    def _history_point(
        cls,
        snapshot: BalanceSnapshot,
        previous: BalanceSnapshot | None,
    ) -> HistoryPoint:
        change_amount: Decimal | None = None
        change_type: BalanceChangeType | None = None
        if previous is not None:
            change_amount = normalize_amount(
                snapshot.available_amount - previous.available_amount
            )
            if change_amount > 0:
                change_type = "SUPPLY"
            elif change_amount < 0:
                change_type = "CONSUMPTION"
            else:
                change_type = "UNCHANGED"

        return HistoryPoint(
            **cls._balance_value(snapshot).model_dump(),
            change_amount=decimal_string(change_amount),
            change_type=change_type,
        )
