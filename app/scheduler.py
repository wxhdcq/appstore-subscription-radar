from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings
from .services.refresh import refresh_all_apps


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    scheduler.add_job(
        refresh_all_apps,
        CronTrigger(hour=settings.refresh_hour, minute=settings.refresh_minute),
        id="daily-price-refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler

