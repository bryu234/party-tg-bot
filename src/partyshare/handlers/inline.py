"""Inline-режим для приглашения участников."""

import secrets
from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from partyshare.config import get_settings
from partyshare.db.repo import get_global_repository

inline_router = Router()


@inline_router.inline_query()
async def inline_query_handler(inline_query: InlineQuery) -> None:
    """Обработчик inline-запросов для приглашений на события."""
    user = inline_query.from_user
    query = inline_query.query.strip()
    
    results = []
    
    # Если запрос начинается с "invite_", показываем конкретное событие
    if query.startswith("invite_"):
        try:
            event_id = int(query.split("_")[1])
            repo = get_global_repository()
            event = await repo.get_event(event_id)
            
            if event:
                # Получаем user_id
                repo_user_id = await repo.ensure_user(user.id, user.username, user.full_name)
                
                # Проверяем, что пользователь - владелец события
                if event['owner_id'] == repo_user_id:
                    # Получаем или создаём invite link
                    invite = await repo.get_invite_link(event_id)
                    
                    if not invite:
                        token = secrets.token_urlsafe(16)
                        invite = await repo.add_invite_link(
                            event_id=event_id,
                            token=token,
                            max_uses=None,
                            expires_at=None
                        )
                    
                    # Форматируем дату
                    settings = get_settings()
                    local_dt = event['starts_at'].astimezone(settings.zoneinfo)
                    date_str = local_dt.strftime("%d.%m.%Y в %H:%M")
                    
                    # Формируем текст приглашения
                    invite_text = (
                        f"🎉 <b>Приглашение на событие!</b>\n\n"
                        f"<b>{event['title']}</b>\n\n"
                        f"📅 <b>Когда:</b> {date_str}\n"
                    )
                    
                    if event.get('location'):
                        invite_text += f"📍 <b>Где:</b> {event['location']}\n"
                    
                    if event.get('notes'):
                        invite_text += f"\n📋 {event['notes']}\n"
                    
                    invite_text += "\n👇 Нажми кнопку ниже, чтобы присоединиться!"
                    
                    # Создаём кнопку для присоединения
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(
                            text="✅ Присоединиться к событию",
                            url=f"https://t.me/{inline_query.bot.username}?start=invite_{invite['token']}"
                        )]
                    ])
                    
                    # Создаём результат
                    result = InlineQueryResultArticle(
                        id=f"invite_{event_id}",
                        title=f"🎉 {event['title']}",
                        description=f"Пригласить на событие {date_str}",
                        input_message_content=InputTextMessageContent(
                            message_text=invite_text,
                            parse_mode="HTML"
                        ),
                        reply_markup=keyboard,
                        thumbnail_url="https://telegram.org/img/t_logo.png"
                    )
                    
                    results.append(result)
        except (ValueError, IndexError):
            pass
    
    # Отправляем результаты
    await inline_query.answer(
        results,
        cache_time=10,
        is_personal=True
    )

