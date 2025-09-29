from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from partyshare.config import get_settings
from partyshare.db.repo import PartyShareRepository
from partyshare.logging import get_logger


async def setup_scheduler(bot: Bot, repo: PartyShareRepository) -> AsyncIOScheduler:
    settings = get_settings()

    scheduler = AsyncIOScheduler(timezone=settings.tz)
    scheduler.add_job(
        _reminder_job,
        IntervalTrigger(minutes=1),
        kwargs={"bot": bot, "repo": repo},
    )
    scheduler.start()
    return scheduler


async def _reminder_job(bot: Bot, repo: PartyShareRepository) -> None:
    log = get_logger(__name__)
    now = datetime.now(timezone.utc)
    rows = await repo.fetch_pending_reminders(now)

    for row in rows:
        log.info("reminder.send", reminder_id=row["id"])
        participants = await repo.get_event_participants(row["event_id"])
        for participant in participants:
            tg_id = participant["tg_id"]
            if tg_id:
                await bot.send_message(
                    tg_id,
                    f"Напоминание о событии #{row['event_id']}: {row['title']} начинается {row['starts_at']}",
                )
        await repo.mark_reminder_sent(row["id"])

