from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

basic_router = Router()


@basic_router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я PartyShare — помогу собрать друзей и честно поделить расходы."
    )


@basic_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Основные команды:\n"
        "/newevent — создать событие\n"
        "/myevents — список событий\n"
        "/addexpense — добавить расход\n"
        "/summary — сводка по балансу"
    )

