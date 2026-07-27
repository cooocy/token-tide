import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import cast, overload

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from token_tide.models import BalanceChangeEvent, BalanceSnapshot, RefreshRun
from token_tide.providers.base import BalanceProvider, ProviderError
from token_tide.response import ApplicationError
from token_tide.schemas import (
    BalanceChangeEventValue,
    BalanceChangeType,
    BalanceHistory,
    BalanceValue,
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
                    previous = session.scalar(
                        select(BalanceSnapshot)
                        .where(
                            BalanceSnapshot.provider == reading.provider,
                            BalanceSnapshot.currency == reading.currency,
                        )
                        .order_by(
                            desc(BalanceSnapshot.observed_at),
                            desc(BalanceSnapshot.id),
                        )
                        .limit(1)
                    )
                    snapshot = BalanceSnapshot(
                        provider=reading.provider,
                        currency=reading.currency,
                        available_amount=normalize_amount(reading.available_amount),
                        is_available=reading.is_available,
                        observed_at=finished_at,
                    )
                    session.add(snapshot)
                    session.flush()
                    event = self._new_change_event(snapshot, previous)
                    if event is not None:
                        session.add(event)
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
        statement: Select[tuple[BalanceChangeEvent]] = select(
            BalanceChangeEvent
        ).where(
            BalanceChangeEvent.provider == provider_name
        )
        normalized_currency = currency.upper() if currency else None
        if normalized_currency:
            statement = statement.where(
                BalanceChangeEvent.currency == normalized_currency
            )
        if start_time:
            statement = statement.where(BalanceChangeEvent.occurred_at >= start_time)
        if end_time:
            statement = statement.where(BalanceChangeEvent.occurred_at <= end_time)
        statement = statement.order_by(
            desc(BalanceChangeEvent.occurred_at),
            desc(BalanceChangeEvent.id),
        ).limit(limit)

        with self.session_factory() as session:
            events = list(reversed(session.scalars(statement).all()))
        return BalanceHistory(
            provider=provider_name,
            currency=normalized_currency,
            events=[self._change_event_value(event) for event in events],
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
                    .order_by(
                        desc(BalanceSnapshot.observed_at),
                        desc(BalanceSnapshot.id),
                    )
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

    @staticmethod
    def _new_change_event(
        snapshot: BalanceSnapshot,
        previous: BalanceSnapshot | None,
    ) -> BalanceChangeEvent | None:
        if previous is None:
            change_amount = None
            change_type: BalanceChangeType = "INITIAL"
        else:
            change_amount = normalize_amount(
                snapshot.available_amount - previous.available_amount
            )
            if change_amount == 0:
                return None
            change_type = "SUPPLY" if change_amount > 0 else "CONSUMPTION"

        return BalanceChangeEvent(
            snapshot_id=snapshot.id,
            provider=snapshot.provider,
            currency=snapshot.currency,
            previous_amount=previous.available_amount if previous else None,
            current_amount=snapshot.available_amount,
            change_amount=change_amount,
            change_type=change_type,
            occurred_at=snapshot.observed_at,
        )

    @staticmethod
    def _change_event_value(event: BalanceChangeEvent) -> BalanceChangeEventValue:
        return BalanceChangeEventValue(
            id=event.id,
            currency=event.currency,
            previous_amount=decimal_string(event.previous_amount),
            current_amount=decimal_string(event.current_amount) or "0.00",
            change_amount=decimal_string(event.change_amount),
            change_type=cast(BalanceChangeType, event.change_type),
            occurred_at=event.occurred_at,
        )
