from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from partyshare.db.repo import get_global_repository
from partyshare.services.authz import assert_event_owner, assert_event_participant

expenses_router = Router()


def _extract_event_id(text: str) -> int | None:
    parts = text.split()
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            return None
    return None


@expenses_router.message(Command("addexpense"))
async def cmd_addexpense(message: Message) -> None:
    repo = get_global_repository()
    if not message.text:
        return
    parts = [part.strip() for part in message.text.replace("/addexpense", "", 1).split("|")]
    if len(parts) < 3:
        await message.answer("Использование: /addexpense <event_id> | <title> | <amount> <CUR> | shared|items")
        return

    try:
        event_id = int(parts[0])
    except ValueError:
        await message.answer("Некорректный event_id")
        return

    title = parts[1]
    amount_currency = parts[2].split()
    if len(amount_currency) < 1:
        await message.answer("Укажите сумму")
        return

    try:
        amount_cents = int(float(amount_currency[0]) * 100)
    except ValueError:
        await message.answer("Некорректная сумма")
        return

    currency = amount_currency[1] if len(amount_currency) > 1 else "EUR"
    mode = parts[3].strip() if len(parts) > 3 else "shared"

    user = message.from_user
    if not user:
        return

    user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    await assert_event_participant(repo.db, user_id, event_id)

    is_shared = mode.lower() == "shared"
    expense = await repo.create_expense(
        event_id=event_id,
        payer_id=user_id,
        created_by=user_id,
        title=title,
        amount_cents=amount_cents,
        currency=currency,
        is_shared=is_shared,
    )

    msg = f"Расход добавлен: #{expense['id']} {expense['title']}"
    if not is_shared:
        msg += (
            "\nДобавьте позиции через /additem "
            "<expense_id> | <label> | <amount> | @user1 @user2"
        )

    await message.answer(msg)


@expenses_router.message(Command("additem"))
async def cmd_additem(message: Message) -> None:
    repo = get_global_repository()
    if not message.text:
        return
    parts = [part.strip() for part in message.text.replace("/additem", "", 1).split("|")]
    if len(parts) < 3:
        await message.answer("Использование: /additem <expense_id> | <label> | <amount> | @u1 @u2 ...")
        return

    try:
        expense_id = int(parts[0])
    except ValueError:
        await message.answer("Некорректный expense_id")
        return

    label = parts[1]
    amount = parts[2].strip()
    try:
        amount_cents = int(float(amount) * 100)
    except ValueError:
        await message.answer("Некорректная сумма позиции")
        return

    consumers = []
    if len(parts) > 3:
        for username in parts[3].split():
            user = await repo.get_user_by_username(username)
            if user:
                consumers.append(user["id"])

    user = message.from_user
    if not user:
        return

    current_user_id = await repo.ensure_user(user.id, user.username, user.full_name)
    expense = await repo.get_expense(expense_id)
    if not expense:
        await message.answer("Расход не найден")
        return

    await assert_event_participant(repo.db, current_user_id, expense["event_id"])

    item = await repo.add_expense_item(expense_id, label, amount_cents, consumers)
    await message.answer(f"Позиция добавлена: #{item['id']} {item['label'] or ''}")

