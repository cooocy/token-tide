from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from token_tide.models import BalanceSnapshot, Base, RefreshRun
from token_tide.providers.base import BalanceProvider, BalanceReading, ProviderError
from token_tide.schemas import BalanceValue, ProviderBalance, ProviderRefreshResult
from token_tide.service import BalanceService, decimal_string, normalize_amount


class StubProvider(BalanceProvider):
    name = "stub"

    def __init__(
        self,
        should_fail: bool = False,
        amount: Decimal = Decimal("12.34"),
    ) -> None:
        self.enabled = True
        self.should_fail = should_fail
        self.amount = amount

    async def fetch_balance(self) -> list[BalanceReading]:
        if self.should_fail:
            raise ProviderError("upstream_failed", "Provider request failed")
        return [
            BalanceReading(
                provider=self.name,
                currency="USD",
                available_amount=self.amount,
                is_available=True,
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


def test_balance_history_identifies_supply_consumption_and_unchanged(
    session_factory: sessionmaker[Session],
) -> None:
    service = BalanceService({"stub": StubProvider()}, session_factory)
    observed_at = datetime(2026, 7, 26, 8, tzinfo=UTC)
    with session_factory() as session:
        session.add_all(
            [
                BalanceSnapshot(
                    provider="stub",
                    currency="USD",
                    available_amount=amount,
                    is_available=True,
                    observed_at=observed_at + timedelta(hours=index),
                )
                for index, amount in enumerate(
                    [
                        Decimal("10.00"),
                        Decimal("7.50"),
                        Decimal("12.00"),
                        Decimal("12.00"),
                    ]
                )
            ]
        )
        session.commit()

    history = service.balance_history("stub", "USD", None, None, 100)

    assert [
        (point.change_amount, point.change_type)
        for point in history.points
    ] == [
        (None, None),
        ("-2.50", "CONSUMPTION"),
        ("4.50", "SUPPLY"),
        ("0.00", "UNCHANGED"),
    ]


def test_balance_history_uses_preceding_snapshot_outside_limit(
    session_factory: sessionmaker[Session],
) -> None:
    service = BalanceService({"stub": StubProvider()}, session_factory)
    observed_at = datetime(2026, 7, 26, 8, tzinfo=UTC)
    with session_factory() as session:
        session.add_all(
            [
                BalanceSnapshot(
                    provider="stub",
                    currency="USD",
                    available_amount=amount,
                    is_available=True,
                    observed_at=observed_at + timedelta(hours=index),
                )
                for index, amount in enumerate(
                    [Decimal("10.00"), Decimal("8.00"), Decimal("18.00")]
                )
            ]
        )
        session.add(
            BalanceSnapshot(
                provider="stub",
                currency="EUR",
                available_amount=Decimal("8.00"),
                is_available=True,
                observed_at=observed_at + timedelta(minutes=30),
            )
        )
        session.commit()

    history = service.balance_history("stub", "USD", None, None, 1)

    assert len(history.points) == 1
    assert history.points[0].change_amount == "10.00"
    assert history.points[0].change_type == "SUPPLY"


def test_balance_history_keeps_currency_changes_isolated(
    session_factory: sessionmaker[Session],
) -> None:
    service = BalanceService({"stub": StubProvider()}, session_factory)
    observed_at = datetime(2026, 7, 26, 8, tzinfo=UTC)
    snapshots = [
        ("USD", Decimal("10.00")),
        ("EUR", Decimal("50.00")),
        ("USD", Decimal("9.00")),
        ("EUR", Decimal("70.00")),
    ]
    with session_factory() as session:
        session.add_all(
            [
                BalanceSnapshot(
                    provider="stub",
                    currency=currency,
                    available_amount=amount,
                    is_available=True,
                    observed_at=observed_at + timedelta(hours=index),
                )
                for index, (currency, amount) in enumerate(snapshots)
            ]
        )
        session.commit()

    history = service.balance_history("stub", None, None, None, 100)

    assert [
        (point.currency, point.change_amount, point.change_type)
        for point in history.points
    ] == [
        ("USD", None, None),
        ("EUR", None, None),
        ("USD", "-1.00", "CONSUMPTION"),
        ("EUR", "20.00", "SUPPLY"),
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
