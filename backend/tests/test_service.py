from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from token_tide.models import BalanceChangeEvent, BalanceSnapshot, Base, RefreshRun
from token_tide.providers.base import BalanceProvider, BalanceReading, ProviderError
from token_tide.schemas import (
    BalanceChangeEventValue,
    BalanceValue,
    ProviderBalance,
    ProviderRefreshResult,
)
from token_tide.service import BalanceService, decimal_string, normalize_amount


class StubProvider(BalanceProvider):
    name = "stub"

    def __init__(
        self,
        should_fail: bool = False,
        amount: Decimal = Decimal("12.34"),
        is_available: bool = True,
    ) -> None:
        self.enabled = True
        self.should_fail = should_fail
        self.amount = amount
        self.is_available = is_available

    async def fetch_balance(self) -> list[BalanceReading]:
        if self.should_fail:
            raise ProviderError("upstream_failed", "Provider request failed")
        return [
            BalanceReading(
                provider=self.name,
                currency="USD",
                available_amount=self.amount,
                is_available=self.is_available,
            )
        ]


@pytest.fixture
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_successful_refresh_persists_snapshot(
    session_factory: sessionmaker[Session],
) -> None:
    service = BalanceService(
        {"stub": StubProvider(amount=Decimal("12.345"))},
        session_factory,
    )

    result = await service.refresh_provider("stub", "MANUAL")

    assert result.status == "SUCCESS"
    with session_factory() as session:
        snapshot = session.scalar(select(BalanceSnapshot))
        assert snapshot is not None
        assert snapshot.available_amount == Decimal("12.35")
        event = session.scalar(select(BalanceChangeEvent))
        assert event is not None
        assert event.snapshot_id == snapshot.id
        assert event.previous_amount is None
        assert event.current_amount == Decimal("12.35")
        assert event.change_amount is None
        assert event.change_type == "INITIAL"
        assert session.scalar(select(RefreshRun)).status == "SUCCESS"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_failed_provider_does_not_block_other_provider(
    session_factory: sessionmaker[Session],
) -> None:
    healthy = StubProvider()
    healthy.name = "healthy"
    failed = StubProvider(should_fail=True)
    failed.name = "failed"
    service = BalanceService({"healthy": healthy, "failed": failed}, session_factory)

    results: list[ProviderRefreshResult] = await service.refresh_all("SCHEDULED")

    assert [result.provider for result in results] == ["healthy", "failed"]
    assert [result.status for result in results] == ["SUCCESS", "FAILED"]
    with session_factory() as session:
        snapshots = session.scalars(select(BalanceSnapshot)).all()
        assert len(snapshots) == 1
        events = session.scalars(select(BalanceChangeEvent)).all()
        assert len(events) == 1
        assert events[0].provider == "healthy"


def test_latest_balances_preserves_provider_order(
    session_factory: sessionmaker[Session],
) -> None:
    first = StubProvider()
    first.name = "first"
    second = StubProvider()
    second.name = "second"
    service = BalanceService(
        {"second": second, "first": first},
        session_factory,
    )

    latest = service.latest_balances()

    assert [provider.provider for provider in latest] == ["second", "first"]


@pytest.mark.asyncio
async def test_refresh_persists_only_initial_and_changed_balance_events(
    session_factory: sessionmaker[Session],
) -> None:
    provider = StubProvider(amount=Decimal("10.00"))
    service = BalanceService({"stub": provider}, session_factory)

    await service.refresh_provider("stub", "SCHEDULED")
    provider.amount = Decimal("10.00")
    provider.is_available = False
    await service.refresh_provider("stub", "SCHEDULED")
    provider.amount = Decimal("7.50")
    await service.refresh_provider("stub", "SCHEDULED")
    provider.amount = Decimal("12.00")
    await service.refresh_provider("stub", "SCHEDULED")

    history = service.balance_history("stub", "USD", None, None, 100)

    assert [(event.change_amount, event.change_type) for event in history.events] == [
        (None, "INITIAL"),
        ("-2.50", "CONSUMPTION"),
        ("4.50", "SUPPLY"),
    ]
    with session_factory() as session:
        assert len(session.scalars(select(BalanceSnapshot)).all()) == 4
        assert len(session.scalars(select(BalanceChangeEvent)).all()) == 3


@pytest.mark.asyncio
async def test_balance_history_reads_latest_events_in_chronological_order(
    session_factory: sessionmaker[Session],
) -> None:
    provider = StubProvider(amount=Decimal("10.00"))
    service = BalanceService({"stub": provider}, session_factory)
    await service.refresh_provider("stub", "SCHEDULED")
    provider.amount = Decimal("8.00")
    await service.refresh_provider("stub", "SCHEDULED")
    provider.amount = Decimal("18.00")
    await service.refresh_provider("stub", "SCHEDULED")

    history = service.balance_history("stub", "usd", None, None, 2)

    assert history.currency == "USD"
    assert [(event.change_amount, event.change_type) for event in history.events] == [
        ("-2.00", "CONSUMPTION"),
        ("10.00", "SUPPLY"),
    ]


def test_balance_history_does_not_derive_events_from_snapshots(
    session_factory: sessionmaker[Session],
) -> None:
    service = BalanceService({"stub": StubProvider()}, session_factory)
    observed_at = datetime(2026, 7, 26, 8, tzinfo=UTC)
    with session_factory() as session:
        session.add_all(
            [
                BalanceSnapshot(
                    provider="stub", currency="USD", available_amount=amount,
                    is_available=True,
                    observed_at=observed_at + timedelta(hours=index),
                )
                for index, amount in enumerate(
                    [Decimal("10.00"), Decimal("9.00")]
                )
            ]
        )
        session.commit()

    history = service.balance_history("stub", None, None, None, 100)

    assert history.events == []


def test_balance_history_filters_events_by_currency_and_time(
    session_factory: sessionmaker[Session],
) -> None:
    service = BalanceService({"stub": StubProvider()}, session_factory)
    observed_at = datetime(2026, 7, 26, 8, tzinfo=UTC)
    with session_factory() as session:
        usd_initial = BalanceSnapshot(
            provider="stub",
            currency="USD",
            available_amount=Decimal("10.00"),
            is_available=True,
            observed_at=observed_at,
        )
        eur_initial = BalanceSnapshot(
            provider="stub",
            currency="EUR",
            available_amount=Decimal("20.00"),
            is_available=True,
            observed_at=observed_at + timedelta(hours=1),
        )
        usd_supply = BalanceSnapshot(
            provider="stub",
            currency="USD",
            available_amount=Decimal("12.00"),
            is_available=True,
            observed_at=observed_at + timedelta(hours=2),
        )
        session.add_all([usd_initial, eur_initial, usd_supply])
        session.flush()
        session.add_all(
            [
                BalanceChangeEvent(
                    snapshot_id=usd_initial.id,
                    provider="stub",
                    currency="USD",
                    previous_amount=None,
                    current_amount=Decimal("10.00"),
                    change_amount=None,
                    change_type="INITIAL",
                    occurred_at=usd_initial.observed_at,
                ),
                BalanceChangeEvent(
                    snapshot_id=eur_initial.id,
                    provider="stub",
                    currency="EUR",
                    previous_amount=None,
                    current_amount=Decimal("20.00"),
                    change_amount=None,
                    change_type="INITIAL",
                    occurred_at=eur_initial.observed_at,
                ),
                BalanceChangeEvent(
                    snapshot_id=usd_supply.id,
                    provider="stub",
                    currency="USD",
                    previous_amount=Decimal("10.00"),
                    current_amount=Decimal("12.00"),
                    change_amount=Decimal("2.00"),
                    change_type="SUPPLY",
                    occurred_at=usd_supply.observed_at,
                ),
            ]
        )
        session.commit()

    history = service.balance_history(
        "stub",
        "usd",
        observed_at + timedelta(minutes=1),
        observed_at + timedelta(hours=3),
        100,
    )

    assert [(event.currency, event.change_type) for event in history.events] == [
        ("USD", "SUPPLY")
    ]


@pytest.mark.asyncio
async def test_latest_balance_keeps_last_success_after_failure(
    session_factory: sessionmaker[Session],
) -> None:
    provider = StubProvider()
    service = BalanceService({"stub": provider}, session_factory)
    await service.refresh_provider("stub", "MANUAL")
    provider.should_fail = True
    await service.refresh_provider("stub", "MANUAL")

    latest = service.latest_balances()[0]

    assert latest.status == "FAILED"
    assert latest.balances[0].available_amount == "12.34"
    assert "prepaid_amount" not in latest.balances[0].model_dump()
    assert "granted_amount" not in latest.balances[0].model_dump()
    assert latest.last_success_at is not None


def test_amount_rounding_uses_round_half_up() -> None:
    assert normalize_amount(Decimal("1.234")) == Decimal("1.23")
    assert normalize_amount(Decimal("1.235")) == Decimal("1.24")
    assert normalize_amount(Decimal("-1.235")) == Decimal("-1.24")
    assert decimal_string(Decimal("1")) == "1.00"


def test_observed_at_serializes_as_utc() -> None:
    balance = BalanceValue(
        currency="USD",
        available_amount="12.34",
        is_available=True,
        observed_at=datetime(2026, 7, 25, 10, 21, 10),
    )

    assert balance.model_dump(mode="json")["observed_at"] == "2026-07-25T10:21:10Z"


def test_provider_timestamps_serialize_as_utc_z() -> None:
    provider = ProviderBalance(
        provider="stub",
        status="SUCCESS",
        last_refresh_at=datetime(
            2026,
            7,
            25,
            18,
            21,
            10,
            tzinfo=timezone(timedelta(hours=8)),
        ),
        last_success_at=datetime(2026, 7, 25, 10, 21, 10),
        error_code=None,
        error_message=None,
        balances=[],
    )

    payload = provider.model_dump(mode="json")

    assert payload["last_refresh_at"] == "2026-07-25T10:21:10Z"
    assert payload["last_success_at"] == "2026-07-25T10:21:10Z"


def test_refresh_result_timestamps_serialize_as_utc_z() -> None:
    result = ProviderRefreshResult(
        provider="stub",
        status="SUCCESS",
        started_at=datetime(2026, 7, 25, 10, 21, 10),
        finished_at=datetime(2026, 7, 25, 10, 22, 10, tzinfo=UTC),
        snapshot_count=1,
    )

    payload = result.model_dump(mode="json")

    assert payload["started_at"] == "2026-07-25T10:21:10Z"
    assert payload["finished_at"] == "2026-07-25T10:22:10Z"


def test_balance_change_event_timestamp_serializes_as_utc_z() -> None:
    event = BalanceChangeEventValue(
        id=1,
        currency="USD",
        previous_amount="8.00",
        current_amount="10.00",
        change_amount="2.00",
        change_type="SUPPLY",
        occurred_at=datetime(
            2026,
            7,
            25,
            18,
            21,
            10,
            tzinfo=timezone(timedelta(hours=8)),
        ),
    )

    assert event.model_dump(mode="json")["occurred_at"] == "2026-07-25T10:21:10Z"
