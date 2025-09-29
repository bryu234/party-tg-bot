from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from partyshare.config import get_settings
from partyshare.db.repo import Database, PartyShareRepository, set_global_repository
from partyshare.handlers import basic_router, events_router, expenses_router
from partyshare.state import state
from partyshare.logging import configure_logging, get_logger
from partyshare.scheduler import setup_scheduler


async def main() -> None:
    configure_logging()
    settings = get_settings()
    bot = Bot(token=settings.bot_token, parse_mode=ParseMode.HTML)
    dp = Dispatcher()
    db = Database(settings.database_url)
    await db.connect()
    repo = PartyShareRepository(db)

    dp.include_router(basic_router)
    dp.include_router(events_router)
    dp.include_router(expenses_router)

    set_global_repository(repo)

    scheduler = await setup_scheduler(bot, repo)

    log = get_logger(__name__)
    log.info("bot.start")
    try:
        await dp.start_polling(bot)
    finally:
        await scheduler.shutdown(wait=False)
        await db.close()
        await bot.session.close()
        log.info("bot.stop")


if __name__ == "__main__":
    asyncio.run(main())

