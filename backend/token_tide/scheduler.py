import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from token_tide.config import RefreshSettings
from token_tide.service import BalanceService

logger = logging.getLogger(__name__)


async def refresh_scheduled(service: BalanceService) -> None:
    results = await service.refresh_all("SCHEDULED")
    failed = [result.provider for result in results if result.status == "FAILED"]
    if failed:
        logger.warning("Scheduled balance refresh failed for: %s", ", ".join(failed))


def create_scheduler(
    service: BalanceService,
    settings: RefreshSettings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        refresh_scheduled,
        trigger=CronTrigger.from_crontab(settings.cron, timezone=settings.timezone),
        args=[service],
        id="refresh-balances",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
