from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

from partyshare.config import get_settings
from partyshare.db.repo import get_global_repository
from partyshare.keyboards import build_events_keyboard, manage_keyboard
from partyshare.services.authz import assert_event_owner, assert_event_participant
from partyshare.services.events import (
    build_event_cards,
    format_event_card,
    humanize_status,
    next_status,
)
from partyshare.services.split import ExpenseItemShare, ExpenseShare, calculate_balances
from partyshare.services.settlement import settle
from partyshare.state import OWNER_VIEW, PARTICIPANT_VIEW, state
from partyshare.utils.parse import parse_event_datetime, parse_russian_date
from partyshare.db.models import ParticipantStatus

events_router = Router()


def get_repo():
    return get_global_repository()


@events_router.callback_query(lambda c: c.data == "menu:myevents")
async def cb_menu_myevents(callback: CallbackQuery) -> None:
    """Показать список событий из главного меню"""
    repo = get_repo()
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка: пользователь не найден")
        return

    # Получаем события пользователя (где он владелец или участник)
    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    owner_events = await repo.list_owner_events(user_id)
    participant_events = await repo.list_participant_events(user_id)
    
    # Объединяем списки и убираем дубликаты
    event_ids_seen = set()
    events = []
    for event in owner_events:
        if event['id'] not in event_ids_seen:
            events.append(event)
            event_ids_seen.add(event['id'])
    for event in participant_events:
        if event['id'] not in event_ids_seen:
            events.append(event)
            event_ids_seen.add(event['id'])

    if not events:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать событие", callback_data="menu:newevent")],
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu:main")]
        ])
        await callback.message.edit_text(
            "📅 <b>Мои события</b>\n\n"
            "У тебя пока нет событий.\n"
            "Создай первое или присоединись к существующему!",
            reply_markup=keyboard
        )
    else:
        cards = await build_event_cards(repo, events, user_id)
        keyboard = build_events_keyboard(
            events,
            cards,
            is_owner_view=True,
            page_size=5,
            page=0
        )
        
        # Добавляем кнопку возврата в меню
        keyboard.inline_keyboard.append(
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu:main")]
        )
        
        await callback.message.edit_text(
            "📅 <b>Мои события</b>\n\n"
            "Выбери событие для управления:",
            reply_markup=keyboard
        )
    
    await callback.answer()


@events_router.callback_query(lambda c: c.data == "menu:newevent")
async def cb_menu_newevent(callback: CallbackQuery) -> None:
    """Начало создания события - запрос названия"""
    user = callback.from_user
    if not user:
        await callback.answer("Ошибка")
        return
    
    # Устанавливаем состояние "создание события" и шаг "название"
    state.set_creating_event(user.id)
    state.set_event_step(user.id, "title")
    state.clear_event_data(user.id)
    
    text = (
        "➕ <b>Создание нового события</b>\n\n"
        "📝 <b>Шаг 1/4: Название</b>\n\n"
        "Как назовём событие?\n\n"
        "Например: <i>День рождения Макса</i> или <i>Корпоратив</i>"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить", callback_data="menu:cancel_create")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@events_router.callback_query(lambda c: c.data == "menu:cancel_create")
async def cb_cancel_create(callback: CallbackQuery) -> None:
    """Отмена создания события"""
    user = callback.from_user
    if user:
        state.clear_creating_event(user.id)
        state.clear_event_data(user.id)
    
    # Возвращаемся в главное меню
    user_name = callback.from_user.first_name if callback.from_user else "друг"
    from partyshare.handlers.basic import get_main_menu_keyboard
    await callback.message.edit_text(
        f"👋 Привет, {user_name}!\n\n"
        "Я <b>PartyShare</b> — помогу собрать друзей и честно поделить расходы.\n\n"
        "Выбери действие:",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer("Отменено")


@events_router.callback_query(lambda c: c.data == "event:skip_location")
async def cb_skip_location(callback: CallbackQuery) -> None:
    """Пропуск указания места"""
    user = callback.from_user
    if not user:
        return
    
    state.set_event_step(user.id, "notes")
    
    await callback.message.edit_text(
        "✅ Место пропущено!\n\n"
        "📋 <b>Шаг 4/4: Заметки</b>\n\n"
        "Есть дополнительная информация?\n\n"
        "Например: <i>Приносите подарки!</i> или <i>Дресс-код: casual</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏩ Пропустить", callback_data="event:skip_notes")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="menu:cancel_create")]
        ])
    )
    await callback.answer()


@events_router.callback_query(lambda c: c.data == "event:skip_notes")
async def cb_skip_notes(callback: CallbackQuery) -> None:
    """Пропуск заметок и создание события"""
    user = callback.from_user
    if not user or not callback.message:
        return
    
    repo = get_repo()
    await create_event_from_data(callback.message, repo, user)
    await callback.answer("Событие создано!")


@events_router.callback_query(lambda c: c.data == "menu:addexpense")
async def cb_menu_addexpense(callback: CallbackQuery) -> None:
    """Инструкция по добавлению расхода"""
    text = (
        "💰 <b>Добавление расхода</b>\n\n"
        "Чтобы добавить расход, отправь команду в формате:\n\n"
        "<code>/addexpense [event_id] | [название] | [сумма валюта] | shared/items</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>/addexpense 1 | Пицца | 2500 RUB | shared</code>\n\n"
        "<b>Параметры:</b>\n"
        "• event_id - ID события (найди в списке событий)\n"
        "• название - что купили\n"
        "• сумма - число и валюта (RUB, EUR, USD)\n"
        "• shared - делить поровну\n"
        "• items - делить по позициям\n\n"
        "Сначала посмотри свои события:"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Мои события", callback_data="menu:myevents")],
        [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="menu:main")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


def format_event_details(event, participants) -> str:
    lines = [
        f"Управление событием #{event['id']}",
        f"Название: {event['title']}",
        f"Место: {event['location'] or '—'}",
        f"Старт: {event['starts_at'].astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "\nУчастники:",
    ]
    for p in participants:
        label = p["username"] or p["full_name"] or str(p["tg_id"])
        lines.append(f"• {label} — {p['status']}")
    return "\n".join(lines)


def format_summary(balances: dict[int, int], participants: list) -> str:
    lines = ["Сводка по балансу:"]
    for participant in participants:
        uid = participant["user_id"]
        label = participant["username"] or participant["full_name"] or str(participant["tg_id"])
        balance = balances.get(uid, 0)
        lines.append(f"• {label}: {balance / 100:.2f} EUR")
    return "\n".join(lines)


def build_expense_summary(expenses: list[dict]) -> list[str]:
    expense_lines = ["\nРасходы:"]
    if not expenses:
        expense_lines.append("• пока нет расходов")
        return expense_lines

    for exp in expenses:
        payer = exp["payer_username"] or exp["payer_full_name"] or str(exp["payer_tg_id"])
        expense_lines.append(
            f"• #{exp['id']} {exp['title']} — {exp['amount_cents'] / 100:.2f} {exp['currency']} (платил {payer})"
        )
    return expense_lines


async def build_summary_message(repo, event_id: int) -> str:
    participants = await repo.list_event_participants_with_status(event_id)
    expenses = await repo.get_event_expenses(event_id)
    going_ids = [p["user_id"] for p in participants if p["status"] == "going"]

    expense_shares = []
    for exp in expenses:
        items = await repo.get_expense_items(exp["id"])
        item_shares = [
            ExpenseItemShare(amount_cents=item["amount_cents"], consumers=item["consumers"] or going_ids)
            for item in items
        ] if not exp["is_shared"] else None
        expense_shares.append(
            ExpenseShare(
                payer_id=exp["payer_id"],
                amount_cents=exp["amount_cents"],
                is_shared=exp["is_shared"],
                going_participants=going_ids,
                items=item_shares,
            )
        )

    balances = calculate_balances(expense_shares)
    summary_text = format_summary(balances, participants)
    expense_lines = build_expense_summary(expenses)
    return "\n".join([summary_text, *expense_lines])


async def build_myevents_view(
    user_id: int,
    *,
    active_view: Optional[str] = None,
    direction: Optional[str] = None,
) -> tuple[str, InlineKeyboardMarkup]:
    repo = get_repo()
    settings = get_settings()

    owner_cards = build_event_cards(
        await repo.list_owner_events(user_id), settings.zoneinfo, True
    )
    participant_cards = build_event_cards(
        await repo.list_participant_events(user_id), settings.zoneinfo, False
    )

    views = {
        OWNER_VIEW: owner_cards,
        PARTICIPANT_VIEW: participant_cards,
    }

    if active_view is None:
        active_view = state.get_view(user_id)

    if not active_view or not views.get(active_view):
        if owner_cards:
            active_view = OWNER_VIEW
        elif participant_cards:
            active_view = PARTICIPANT_VIEW
        else:
            state.clear_user(user_id)
            return (
                "Событий пока нет. Создайте новое командой /newevent.",
                build_events_keyboard(OWNER_VIEW, None),
            )

    cards = views[active_view]
    ids = [card.event_id for card in cards]

    current_event_id = state.get_view_event(user_id, active_view)
    if current_event_id not in ids:
        current_event_id = ids[0]

    try:
        idx = ids.index(current_event_id)
    except ValueError:
        idx = 0

    if direction == "prev" and idx > 0:
        idx -= 1
    elif direction == "next" and idx < len(ids) - 1:
        idx += 1

    current_card = cards[idx]
    state.set_view_event(user_id, active_view, current_card.event_id)

    title = "Раздел «Я владелец»" if active_view == OWNER_VIEW else "Раздел «Я участник»"
    body = format_event_card(current_card, settings.zoneinfo)
    status_label = humanize_status(current_card.status) if current_card.status else None

    keyboard = build_events_keyboard(
        active_view,
        current_card.event_id,
        status_label=status_label,
        has_prev=idx > 0,
        has_next=idx < len(cards) - 1,
    )

    return f"{title}\n\n{body}", keyboard


@events_router.message(Command("newevent"))
async def cmd_newevent(message: Message) -> None:
    repo = get_repo()
    parts = message.text.split("|", maxsplit=3) if message.text else []
    if len(parts) < 2:
        await message.answer("Использование: /newevent [название] | [YYYY-MM-DD HH:MM TZ] | [место?] | [заметки?]")
        return

    title = parts[0].replace("/newevent", "").strip()
    raw_dt = parts[1].strip()
    location = parts[2].strip() if len(parts) > 2 else None
    notes = parts[3].strip() if len(parts) > 3 else None

    settings = get_settings()

    try:
        dt = parse_event_datetime(raw_dt, settings.zoneinfo)
    except ValueError:
        await message.answer("Не удалось распарсить дату и время.")
        return

    user = message.from_user
    if not user:
        return

    owner_id = await repo.ensure_user(user.id, user.username, user.full_name)

    event = await repo.create_event(owner_id, title, dt, location, notes)

    remind_at = dt - timedelta(days=3)
    await repo.create_reminder(event["id"], remind_at)

    await message.answer(
        f"Событие создано: {event['title']} {event['starts_at']}"
    )


@events_router.message(Command("myevents"))
async def cmd_myevents(message: Message) -> None:
    repo = get_repo()
    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    state.clear_user(user_id)
    text, keyboard = await build_myevents_view(user_id)
    await message.answer(text, reply_markup=keyboard)


@events_router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    repo = get_repo()
    if not message.text:
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /status [event_id] going|declined|maybe")
        return

    try:
        event_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный ID события")
        return
    status = parts[2]
    if status not in {"going", "declined", "maybe"}:
        await message.answer("Допустимые статусы: going, declined, maybe")
        return

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_participant(repo.db, user_id, event_id)
    await repo.set_participant_status(event_id, user_id, status)
    await message.answer("Статус обновлён")


@events_router.message(Command("invite"))
async def cmd_invite(message: Message) -> None:
    repo = get_repo()
    if not message.text:
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /invite [event_id] @username")
        return

    event_id = int(parts[1])
    username = parts[2]
    user = message.from_user
    if not user:
        return

    current_user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_owner(repo.db, current_user_id, event_id)

    invited = await repo.get_user_by_username(username)
    if not invited:
        await message.answer("Пользователь не найден, пусть сначала напишет боту.")
        return

    await repo.set_participant_status(event_id, invited["id"], "invited")
    await message.answer(f"Пользователь {username} приглашён.")


@events_router.message(Command("summary"))
async def cmd_summary(message: Message) -> None:
    repo = get_repo()
    if not message.text:
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /summary [event_id]")
        return

    event_id = int(parts[1])

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_participant(repo.db, user_id, event_id)

    summary_message = await build_summary_message(repo, event_id)
    await message.answer(summary_message)


@events_router.message(Command("settle"))
async def cmd_settle(message: Message) -> None:
    repo = get_repo()
    if not message.text:
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /settle [event_id]")
        return

    event_id = int(parts[1])
    user = message.from_user
    if not user:
        return
    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_participant(repo.db, user_id, event_id)

    expenses = await repo.get_event_expenses(event_id)
    going_ids = [p["user_id"] for p in await repo.list_event_participants_with_status(event_id) if p["status"] == "going"]

    expense_shares = []
    for exp in expenses:
        items = await repo.get_expense_items(exp["id"])
        item_shares = [
            ExpenseItemShare(
                amount_cents=item["amount_cents"],
                consumers=item["consumers"] or going_ids,
            )
            for item in items
        ] if not exp["is_shared"] else None
        expense_shares.append(
            ExpenseShare(
                payer_id=exp["payer_id"],
                amount_cents=exp["amount_cents"],
                is_shared=exp["is_shared"],
                going_participants=going_ids,
                items=item_shares,
            )
        )

    balances = calculate_balances(expense_shares)
    transfers = settle(balances)

    lines = ["Для сведения долгов:"]
    for t in transfers:
        lines.append(f"• {t.from_user} → {t.to_user}: {t.amount_cents / 100:.2f} EUR")
    await message.answer("\n".join(lines))


@events_router.message(Command("manage"))
async def cmd_manage(message: Message) -> None:
    repo = get_repo()
    if not message.text:
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /manage [event_id]")
        return

    try:
        event_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный ID события")
        return

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_owner(repo.db, user_id, event_id)
    state.set_view_event(user_id, OWNER_VIEW, event_id)

    text, keyboard = await build_myevents_view(user_id, active_view=OWNER_VIEW)
    await message.answer(text, reply_markup=keyboard)


@events_router.callback_query(F.data == "myevents_owner")
async def cb_myevents_owner(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    text, keyboard = await build_myevents_view(user.id, active_view=OWNER_VIEW)
    await callback.answer("Раздел владельца")
    await callback.message.edit_text(text, reply_markup=keyboard)


@events_router.callback_query(F.data == "myevents_participant")
async def cb_myevents_participant(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    text, keyboard = await build_myevents_view(user.id, active_view=PARTICIPANT_VIEW)
    await callback.answer("Раздел участника")
    await callback.message.edit_text(text, reply_markup=keyboard)


@events_router.callback_query(F.data.startswith("event_nav:"))
async def cb_event_nav(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, view, direction = callback.data.split(":")
    text, keyboard = await build_myevents_view(user.id, active_view=view, direction=direction)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=keyboard)


@events_router.callback_query(F.data.startswith("manage:"))
async def cb_manage(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    repo = get_repo()
    event = await repo.get_event(event_id)
    participants = await repo.get_event_participants(event_id)
    text = format_event_details(event, participants)

    await callback.answer()
    await callback.message.edit_text(text, reply_markup=manage_keyboard(event_id))


@events_router.callback_query(F.data == "manage_back")
async def cb_manage_back(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    text, keyboard = await build_myevents_view(user.id, active_view=OWNER_VIEW)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=keyboard)


@events_router.callback_query(F.data.startswith("manage_edit:"))
async def cb_manage_edit(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, field, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    prompts = {
        "title": "Введите новое название:",
        "time": "Введите новую дату/время в формате YYYY-MM-DD HH:MM TZ:",
        "location": "Введите новое место (или '-' чтобы очистить):",
        "notes": "Введите новые заметки (или '-' чтобы очистить):",
    }
    state.set_pending_edit(user.id, event_id, field)
    await callback.answer()
    await callback.message.answer(f"#{event_id} {prompts[field]}")


@events_router.callback_query(F.data.startswith("manage_cancel:"))
async def cb_manage_cancel(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    repo = get_repo()
    await repo.cancel_event(event_id)
    await callback.answer("Событие отменено")
    text, keyboard = await build_myevents_view(user.id, active_view=OWNER_VIEW)
    await callback.message.edit_text(text, reply_markup=keyboard)


@events_router.callback_query(F.data.startswith("manage_remove:"))
async def cb_manage_remove(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    repo = get_repo()
    participants = await repo.get_event_participants(event_id)
    lines = ["Кого удалить? Отправьте /remove <event_id> @username", "\nТекущие участники:"]
    for p in participants:
        label = p["username"] or p["full_name"] or str(p["tg_id"])
        lines.append(f"• {label} — {p['status']}")

    await callback.answer()
    await callback.message.answer("\n".join(lines))


@events_router.message(Command("invitelink"))
async def cmd_invitelink(message: Message) -> None:
    repo = get_repo()
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /invitelink [event_id] [--max=N] [--ttl=hours]")
        return

    try:
        event_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный event_id")
        return

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_owner(repo.db, user_id, event_id)

    max_uses: Optional[int] = None
    ttl_hours: Optional[int] = None
    for arg in parts[2:]:
        if arg.startswith("--max="):
            max_uses = int(arg.split("=", 1)[1])
        if arg.startswith("--ttl="):
            ttl_hours = int(arg.split("=", 1)[1])

    token = secrets.token_urlsafe(8)
    expires_at = None
    if ttl_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    link = await repo.add_invite_link(event_id, token, max_uses, expires_at)
    await message.answer(f"Пригласительная ссылка:\n/join {link['token']}")


@events_router.message(Command("join"))
async def cmd_join(message: Message) -> None:
    repo = get_repo()
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /join [token]")
        return

    token = parts[1]
    link = await repo.get_invite_link_by_token(token)
    if not link:
        await message.answer("Ссылка недействительна")
        return

    if link["expires_at"] and link["expires_at"] < datetime.now(timezone.utc):
        await message.answer("Срок действия ссылки истёк")
        return

    if link["max_uses"] and link["uses"] >= link["max_uses"]:
        await message.answer("Превышено максимальное число использований")
        return

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await repo.set_participant_status(link["event_id"], user_id, "invited")
    await repo.increment_invite_use(link["id"])
    await message.answer("Вы присоединились к событию! Обновите /myevents")


@events_router.callback_query(F.data.startswith("invite:"))
async def cb_invite(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    text = (
        "Чтобы пригласить друга, отправьте ему команду /invitelink"
        f" или используйте: /invitelink {event_id}"
    )
    await callback.answer()
    await callback.message.answer(text)


@events_router.callback_query(F.data.startswith("cycle_status:"))
async def cb_cycle_status(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    repo = get_repo()
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    participant = await repo.get_participant(event_id, user_id)
    if not participant:
        await callback.answer("Вы не участник события", show_alert=True)
        return

    current_status = ParticipantStatus(participant["status"])
    new_status = next_status(current_status)

    await repo.set_participant_status(event_id, user_id, new_status.value)
    text, keyboard = await build_myevents_view(user_id, active_view=PARTICIPANT_VIEW)
    await callback.answer("Статус обновлён")
    await callback.message.edit_text(text, reply_markup=keyboard)


@events_router.message(Command("transfer_ownership"))
async def cmd_transfer_ownership(message: Message) -> None:
    repo = get_repo()
    if not message.text:
        return
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /transfer_ownership [event_id] @username")
        return

    try:
        event_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный event_id")
        return

    username = parts[2]
    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_owner(repo.db, user_id, event_id)

    new_owner = await repo.get_user_by_username(username)
    if not new_owner:
        await message.answer("Пользователь не найден. Попросите его написать боту /start.")
        return

    await repo.transfer_ownership(event_id, new_owner["id"])
    await message.answer("Владение событием передано.")


@events_router.message(Command("remove"))
async def cmd_remove(message: Message) -> None:
    repo = get_repo()
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("Использование: /remove [event_id] @username")
        return

    try:
        event_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный event_id")
        return

    username = parts[2]
    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_owner(repo.db, user_id, event_id)

    target = await repo.get_user_by_username(username)
    if not target:
        await message.answer("Пользователь не найден")
        return

    await repo.remove_participant(event_id, target["id"])
    await message.answer("Участник удалён")


## Дублирующийся блок /invitelink удалён ниже
## Дублирующийся блок /join удалён ниже
## Дублирующийся блок callback invite: удалён ниже
## Дублирующийся блок callback cycle_status: удалён ниже
    repo = get_repo()
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /invitelink [event_id] [--max=N] [--ttl=hours]")
        return

    try:
        event_id = int(parts[1])
    except ValueError:
        await message.answer("Некорректный event_id")
        return

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_owner(repo.db, user_id, event_id)

    max_uses: Optional[int] = None
    ttl_hours: Optional[int] = None
    for arg in parts[2:]:
        if arg.startswith("--max="):
            max_uses = int(arg.split("=", 1)[1])
        if arg.startswith("--ttl="):
            ttl_hours = int(arg.split("=", 1)[1])

    token = secrets.token_urlsafe(8)
    expires_at = None
    if ttl_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

    link = await repo.add_invite_link(event_id, token, max_uses, expires_at)
    await message.answer(f"Пригласительная ссылка: /join {link['token']}")


@events_router.message(Command("join"))
async def cmd_join(message: Message) -> None:
    repo = get_repo()
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Использование: /join [token]")
        return

    token = parts[1]
    link = await repo.get_invite_link_by_token(token)
    if not link:
        await message.answer("Ссылка недействительна")
        return

    if link["expires_at"] and link["expires_at"] < datetime.now(timezone.utc):
        await message.answer("Срок действия ссылки истёк")
        return

    if link["max_uses"] and link["uses"] >= link["max_uses"]:
        await message.answer("Превышено максимальное число использований")
        return

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await repo.set_participant_status(link["event_id"], user_id, "invited")
    await repo.increment_invite_use(link["id"])
    await message.answer("Вы присоединились к событию! Обновите /myevents")


@events_router.callback_query(F.data.startswith("invite:"))
async def cb_invite(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    text = (
        "Чтобы пригласить друга, отправьте ему команду /invitelink"
        f" или используйте: /invitelink {event_id}"
    )
    await callback.answer()
    await callback.message.answer(text)


@events_router.callback_query(F.data.startswith("cycle_status:"))
async def cb_cycle_status(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    repo = get_repo()
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    participant = await repo.get_participant(event_id, user_id)
    if not participant:
        await callback.answer("Вы не участник события", show_alert=True)
        return

    current_status = ParticipantStatus(participant["status"])
    new_status = next_status(current_status)

    await repo.set_participant_status(event_id, user_id, new_status.value)
    text, keyboard = await build_myevents_view(user_id, active_view=PARTICIPANT_VIEW)
    await callback.answer("Статус обновлён")
    await callback.message.edit_text(text, reply_markup=keyboard)


@events_router.callback_query(F.data.startswith("summary:"))
async def cb_summary(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not user or not callback.message:
        return
    _, raw_event_id = callback.data.split(":")
    event_id = int(raw_event_id)

    repo = get_repo()
    summary_message = await build_summary_message(repo, event_id)

    await callback.answer()
    await callback.message.answer(summary_message)


async def handle_create_event_input(message: Message, repo, user) -> None:
    """Обработка пошагового ввода данных для создания события"""
    if not message.text:
        await message.answer("❌ Отправь текст")
        return
    
    step = state.get_event_step(user.id)
    text = message.text.strip()
    
    # Шаг 1: Название
    if step == "title":
        state.set_event_data(user.id, "title", text)
        state.set_event_step(user.id, "datetime")
        
        await message.answer(
            "✅ Отлично!\n\n"
            "📅 <b>Шаг 2/4: Дата и время</b>\n\n"
            "Когда пройдёт событие?\n\n"
            "<b>Примеры:</b>\n"
            "• <code>20 декабря 2025 19:00</code>\n"
            "• <code>20.12.2025 19:00</code>\n"
            "• <code>31/12/2025 23:59</code>\n\n"
            "Таймзона: <b>Москва (+3)</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data="menu:cancel_create")]
            ])
        )
        return
    
    # Шаг 2: Дата и время
    elif step == "datetime":
        try:
            dt = parse_russian_date(text)
            state.set_event_data(user.id, "datetime", dt.isoformat())
            state.set_event_step(user.id, "location")
            
            await message.answer(
                "✅ Дата сохранена!\n\n"
                "📍 <b>Шаг 3/4: Место</b>\n\n"
                "Где пройдёт событие?\n\n"
                "Например: <i>Кафе Пушкин</i> или <i>Офис на Тверской</i>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⏩ Пропустить", callback_data="event:skip_location")],
                    [InlineKeyboardButton(text="❌ Отменить", callback_data="menu:cancel_create")]
                ])
            )
        except ValueError as e:
            await message.answer(
                "❌ Не могу распознать дату!\n\n"
                "<b>Используй один из форматов:</b>\n"
                "• 20 декабря 2025 19:00\n"
                "• 20.12.2025 19:00\n"
                "• 31/12/2025 23:59\n\n"
                "Попробуй ещё раз:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отменить", callback_data="menu:cancel_create")]
                ])
            )
        return
    
    # Шаг 3: Место
    elif step == "location":
        state.set_event_data(user.id, "location", text)
        state.set_event_step(user.id, "notes")
        
        await message.answer(
            "✅ Место сохранено!\n\n"
            "📋 <b>Шаг 4/4: Заметки</b>\n\n"
            "Есть дополнительная информация?\n\n"
            "Например: <i>Приносите подарки!</i> или <i>Дресс-код: casual</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏩ Пропустить", callback_data="event:skip_notes")],
                [InlineKeyboardButton(text="❌ Отменить", callback_data="menu:cancel_create")]
            ])
        )
        return
    
    # Шаг 4: Заметки - создаём событие
    elif step == "notes":
        state.set_event_data(user.id, "notes", text)
        await create_event_from_data(message, repo, user)
        return


async def create_event_from_data(message: Message, repo, user) -> None:
    """Создание события из собранных данных"""
    data = state.get_event_data(user.id)
    
    # Очищаем состояние
    state.clear_creating_event(user.id)
    state.clear_event_data(user.id)
    
    # Получаем данные
    title = data.get("title", "")
    dt_str = data.get("datetime", "")
    location = data.get("location")
    notes = data.get("notes")
    
    if not title or not dt_str:
        await message.answer("❌ Ошибка: недостаточно данных")
        return
    
    dt = datetime.fromisoformat(dt_str)
    
    # Создаём событие
    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    event = await repo.create_event(
        owner_id=user_id,
        title=title,
        starts_at=dt,
        location=location,
        notes=notes,
    )
    
    # Показываем успешное создание
    event_text = (
        f"✅ <b>Событие #{event['id']} создано!</b>\n\n"
        f"📝 <b>Название:</b> {title}\n"
        f"📅 <b>Дата:</b> {dt.strftime('%d.%m.%Y %H:%M')} МСК\n"
    )
    if location:
        event_text += f"📍 <b>Место:</b> {location}\n"
    if notes:
        event_text += f"📋 <b>Заметки:</b> {notes}\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Управление событием", callback_data=f"owner:{event['id']}")],
        [InlineKeyboardButton(text="📅 Мои события", callback_data="menu:myevents")],
        [InlineKeyboardButton(text="◀️ В меню", callback_data="menu:main")]
    ])
    
    await message.answer(event_text, reply_markup=keyboard)


@events_router.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: Message) -> None:
    """Обработка текстового ввода для создания события или редактирования"""
    user = message.from_user
    if not user:
        return
    
    repo = get_repo()
    
    # Проверяем, создаёт ли пользователь событие
    if state.is_creating_event(user.id):
        await handle_create_event_input(message, repo, user)
        return
    
    # Проверяем pending edit
    pending = state.pop_pending_edit(user.id)
    if not pending:
        return

    event_id, field = pending
    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_owner(repo.db, user_id, event_id)

    value = message.text.strip() if message.text else ""
    if field == "time":
        settings = get_settings()
        try:
            value_dt = parse_event_datetime(value, settings.zoneinfo)
        except ValueError:
            await message.answer("Не удалось распарсить дату/время. Попробуйте снова.")
            state.set_pending_edit(user.id, event_id, field)
            return
        await repo.update_event_field(event_id, "starts_at", value_dt)
    elif field in {"title", "location", "notes"}:
        if value == "-":
            value = None
        await repo.update_event_field(event_id, field, value)
    else:
        await message.answer("Неизвестное поле для обновления.")
        return

    await message.answer("Поле обновлено.")
    text, keyboard = await build_myevents_view(user_id, active_view=OWNER_VIEW)
    await message.answer(text, reply_markup=keyboard)

