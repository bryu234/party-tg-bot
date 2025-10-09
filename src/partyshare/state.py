"""Вспомогательные утилиты PartyShare."""

from __future__ import annotations

from typing import Optional, Tuple

OWNER_VIEW = "owner"
PARTICIPANT_VIEW = "participant"


class UserStateManager:
    def __init__(self) -> None:
        self._current_event: dict[int, int] = {}
        self._active_view: dict[int, str] = {}
        self._view_events: dict[int, dict[str, int]] = {}
        self._pending_edit: dict[int, tuple[int, str]] = {}
        self._creating_event: dict[int, bool] = {}
        self._adding_expense: dict[int, bool] = {}
        self._event_data: dict[int, dict[str, str]] = {}  # Временные данные события
        self._event_step: dict[int, str] = {}  # Текущий шаг создания события

    def set_current_event(self, user_id: int, event_id: int) -> None:
        self._current_event[user_id] = event_id

    def get_current_event(self, user_id: int) -> Optional[int]:
        return self._current_event.get(user_id)

    def clear_current_event(self, user_id: int) -> None:
        self._current_event.pop(user_id, None)

    def set_view(self, user_id: int, view: str) -> None:
        self._active_view[user_id] = view

    def get_view(self, user_id: int) -> Optional[str]:
        return self._active_view.get(user_id)

    def set_view_event(self, user_id: int, view: str, event_id: int) -> None:
        self._view_events.setdefault(user_id, {})[view] = event_id
        self.set_view(user_id, view)
        self.set_current_event(user_id, event_id)

    def get_view_event(self, user_id: int, view: str) -> Optional[int]:
        return self._view_events.get(user_id, {}).get(view)

    def set_pending_edit(self, user_id: int, event_id: int, field: str) -> None:
        self._pending_edit[user_id] = (event_id, field)

    def pop_pending_edit(self, user_id: int) -> Optional[Tuple[int, str]]:
        return self._pending_edit.pop(user_id, None)

    def get_pending_edit(self, user_id: int) -> Optional[Tuple[int, str]]:
        return self._pending_edit.get(user_id)

    def set_creating_event(self, user_id: int) -> None:
        self._creating_event[user_id] = True

    def is_creating_event(self, user_id: int) -> bool:
        return self._creating_event.get(user_id, False)

    def clear_creating_event(self, user_id: int) -> None:
        self._creating_event.pop(user_id, None)

    def set_adding_expense(self, user_id: int) -> None:
        self._adding_expense[user_id] = True

    def is_adding_expense(self, user_id: int) -> bool:
        return self._adding_expense.get(user_id, False)

    def clear_adding_expense(self, user_id: int) -> None:
        self._adding_expense.pop(user_id, None)

    def set_event_step(self, user_id: int, step: str) -> None:
        self._event_step[user_id] = step

    def get_event_step(self, user_id: int) -> Optional[str]:
        return self._event_step.get(user_id)

    def set_event_data(self, user_id: int, key: str, value: str) -> None:
        if user_id not in self._event_data:
            self._event_data[user_id] = {}
        self._event_data[user_id][key] = value

    def get_event_data(self, user_id: int) -> dict[str, str]:
        return self._event_data.get(user_id, {})

    def clear_event_data(self, user_id: int) -> None:
        self._event_data.pop(user_id, None)
        self._event_step.pop(user_id, None)

    def clear_user(self, user_id: int) -> None:
        self._current_event.pop(user_id, None)
        self._active_view.pop(user_id, None)
        self._view_events.pop(user_id, None)
        self._pending_edit.pop(user_id, None)
        self._creating_event.pop(user_id, None)
        self._adding_expense.pop(user_id, None)
        self._event_data.pop(user_id, None)
        self._event_step.pop(user_id, None)


state = UserStateManager()

