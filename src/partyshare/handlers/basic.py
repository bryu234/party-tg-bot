from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

basic_router = Router()


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню личного кабинета"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Мои события", callback_data="menu:myevents")],
        [InlineKeyboardButton(text="➕ Создать событие", callback_data="menu:newevent")],
        [InlineKeyboardButton(text="💰 Добавить расход", callback_data="menu:addexpense")],
        [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help")],
    ])
    return keyboard


@basic_router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    # Очищаем все состояния пользователя
    from partyshare.state import state
    user = message.from_user
    if user:
        state.clear_user(user.id)
    
    user_name = user.first_name if user else "друг"
    await message.answer(
        f"👋 Привет, {user_name}!\n\n"
        "Я <b>PartyShare</b> — помогу собрать друзей и честно поделить расходы.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )


@basic_router.callback_query(lambda c: c.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery) -> None:
    """Возврат в главное меню"""
    # Очищаем все состояния
    from partyshare.state import state
    user = callback.from_user
    if user:
        state.clear_user(user.id)
    
    user_name = user.first_name if user else "друг"
    await callback.message.edit_text(
        f"👋 Привет, {user_name}!\n\n"
        "Я <b>PartyShare</b> — помогу собрать друзей и честно поделить расходы.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@basic_router.callback_query(lambda c: c.data == "menu:help")
async def cb_help_menu(callback: CallbackQuery) -> None:
    """Меню помощи"""
    help_text = (
        "<b>📖 Справка по командам</b>\n\n"
        "<b>События:</b>\n"
        "/newevent - создать событие\n"
        "/myevents - список твоих событий\n"
        "/status - изменить статус участия\n"
        "/invite - пригласить друга\n"
        "/invitelink - создать инвайт-ссылку\n"
        "/manage - управление событием\n\n"
        "<b>Расходы:</b>\n"
        "/addexpense - добавить расход\n"
        "/additem - добавить позицию\n"
        "/summary - сводка по балансам\n"
        "/settle - расчёты между участниками\n\n"
        "<b>Формат команд:</b>\n"
        "• /newevent [название] | [дата] | [место] | [заметки]\n"
        "• /addexpense [event_id] | [название] | [сумма валюта] | shared/items\n"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu:main")]
    ])
    await callback.message.edit_text(help_text, reply_markup=keyboard)
    await callback.answer()


@basic_router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Команда /help"""
    help_text = (
        "<b>📖 Справка по командам</b>\n\n"
        "<b>События:</b>\n"
        "/newevent - создать событие\n"
        "/myevents - список твоих событий\n"
        "/status - изменить статус участия\n"
        "/invite - пригласить друга\n"
        "/invitelink - создать инвайт-ссылку\n"
        "/manage - управление событием\n\n"
        "<b>Расходы:</b>\n"
        "/addexpense - добавить расход\n"
        "/additem - добавить позицию\n"
        "/summary - сводка по балансам\n"
        "/settle - расчёты между участниками\n\n"
        "Используй /start чтобы вернуться в главное меню"
    )
    await message.answer(help_text)

