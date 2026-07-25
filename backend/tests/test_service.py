from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from token_tide.models import BalanceSnapshot, Base, RefreshRun
from token_tide.providers.base import BalanceProvider, BalanceReading, ProviderError
from token_tide.schemas import ProviderRefreshResult
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
                granted_amount=None,
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

    assert [result.status for result in results] == ["SUCCESS", "FAILED"]
    with session_factory() as session:
        snapshots = session.scalars(select(BalanceSnapshot)).all()
        assert len(snapshots) == 1


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
    assert latest.last_success_at is not None


def test_amount_rounding_uses_round_half_up() -> None:
    assert normalize_amount(Decimal("1.234")) == Decimal("1.23")
    assert normalize_amount(Decimal("1.235")) == Decimal("1.24")
    assert normalize_amount(Decimal("-1.235")) == Decimal("-1.24")
    assert decimal_string(Decimal("1")) == "1.00"
