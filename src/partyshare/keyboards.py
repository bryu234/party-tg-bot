from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from partyshare.state import OWNER_VIEW, PARTICIPANT_VIEW


def _tabs_row(active_view: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text="· Я владелец" if active_view == OWNER_VIEW else "Я владелец",
            callback_data="myevents_owner",
        ),
        InlineKeyboardButton(
            text="· Я участник" if active_view == PARTICIPANT_VIEW else "Я участник",
            callback_data="myevents_participant",
        ),
    ]


def build_events_keyboard(
    active_view: str,
    event_id: int | None,
    *,
    status_label: str | None = None,
    has_prev: bool = False,
    has_next: bool = False,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [_tabs_row(active_view)]

    if event_id is not None:
        if active_view == OWNER_VIEW:
            rows.append([InlineKeyboardButton(text="Управлять", callback_data=f"manage:{event_id}")])
            rows.append(
                [
                    InlineKeyboardButton(text="Сводка", callback_data=f"summary:{event_id}"),
                    InlineKeyboardButton(text="Пригласить", callback_data=f"invite:{event_id}"),
                ]
            )
        else:
            rows.append([InlineKeyboardButton(text="Сводка", callback_data=f"summary:{event_id}")])
            rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Статус: {status_label}" if status_label else "Обновить статус",
                        callback_data=f"cycle_status:{event_id}",
                    )
                ]
            )

        nav_row: list[InlineKeyboardButton] = []
        if has_prev:
            nav_row.append(
                InlineKeyboardButton(text="« Пред", callback_data=f"event_nav:{active_view}:prev")
            )
        if has_next:
            nav_row.append(
                InlineKeyboardButton(text="След »", callback_data=f"event_nav:{active_view}:next")
            )
        if nav_row:
            rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_keyboard(event_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Переименовать", callback_data=f"manage_edit:title:{event_id}")],
            [InlineKeyboardButton(text="Изменить время", callback_data=f"manage_edit:time:{event_id}")],
            [InlineKeyboardButton(text="Изменить место", callback_data=f"manage_edit:location:{event_id}")],
            [InlineKeyboardButton(text="Изменить заметки", callback_data=f"manage_edit:notes:{event_id}")],
            [InlineKeyboardButton(text="Удалить участника", callback_data=f"manage_remove:{event_id}")],
            [InlineKeyboardButton(text="Отменить событие", callback_data=f"manage_cancel:{event_id}")],
            [InlineKeyboardButton(text="Назад", callback_data="manage_back")],
        ]
    )

