from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from partyshare.db.repo import get_global_repository
from partyshare.config import get_settings

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
    if not user:
        return
    
    state.clear_user(user.id)
    user_name = user.first_name
    
    # Проверяем, есть ли параметр deep link (приглашение)
    if message.text and len(message.text.split()) > 1:
        param = message.text.split()[1]
        
        # Обработка приглашения
        if param.startswith("invite_"):
            token = param[7:]  # Убираем "invite_"
            repo = get_global_repository()
            
            # Получаем приглашение по токену
            invite = await repo.get_invite_link_by_token(token)
            
            if not invite:
                await message.answer(
                    "❌ Приглашение не найдено или устарело.\n\n"
                    "Попроси друга отправить новую ссылку!",
                    reply_markup=get_main_menu_keyboard()
                )
                return
            
            # Получаем событие
            event = await repo.get_event(invite['event_id'])
            
            if not event:
                await message.answer(
                    "❌ Событие не найдено.\n\n"
                    "Возможно, оно было удалено.",
                    reply_markup=get_main_menu_keyboard()
                )
                return
            
            # Регистрируем пользователя в базе
            repo_user_id = await repo.ensure_user(user.id, user.username, user.full_name)
            
            # Проверяем, не является ли пользователь уже участником
            participants = await repo.get_event_participants(invite['event_id'])
            already_participant = any(p['user_id'] == repo_user_id for p in participants)
            
            if already_participant:
                settings = get_settings()
                local_dt = event['starts_at'].astimezone(settings.zoneinfo)
                date_str = local_dt.strftime("%d.%m.%Y в %H:%M")
                
                await message.answer(
                    f"✅ Ты уже участник события!\n\n"
                    f"🎉 <b>{event['title']}</b>\n"
                    f"📅 {date_str}\n\n"
                    "Используй меню ниже для управления событиями:",
                    reply_markup=get_main_menu_keyboard()
                )
                return
            
            # Добавляем участника
            await repo.set_participant_status(
                event_id=invite['event_id'],
                user_id=repo_user_id,
                status='going'
            )
            
            # Увеличиваем счётчик использований
            await repo.increment_invite_use(invite['id'])
            
            # Форматируем дату
            settings = get_settings()
            local_dt = event['starts_at'].astimezone(settings.zoneinfo)
            date_str = local_dt.strftime("%d.%m.%Y в %H:%M")
            
            success_text = (
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"Ты присоединился к событию:\n\n"
                f"<b>{event['title']}</b>\n"
                f"📅 {date_str}\n"
            )
            
            if event.get('location'):
                success_text += f"📍 {event['location']}\n"
            
            if event.get('notes'):
                success_text += f"\n📋 {event['notes']}\n"
            
            success_text += "\n👇 Используй меню для управления событиями:"
            
            await message.answer(success_text, reply_markup=get_main_menu_keyboard())
            return
    
    # Обычный /start без параметров
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

