from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ParticipantStatus(str, Enum):
    INVITED = "invited"
    GOING = "going"
    DECLINED = "declined"
    MAYBE = "maybe"


@dataclass(slots=True)
class User:
    id: int
    tg_id: int
    username: Optional[str]
    full_name: Optional[str]


@dataclass(slots=True)
class Event:
    id: int
    owner_id: int
    title: str
    starts_at: datetime
    location: Optional[str]
    notes: Optional[str]
    canceled: bool


@dataclass(slots=True)
class EventParticipant:
    event_id: int
    user_id: int
    status: ParticipantStatus


@dataclass(slots=True)
class Expense:
    id: int
    event_id: int
    payer_id: int
    created_by: int
    title: str
    amount_cents: int
    currency: str
    is_shared: bool
    created_at: datetime


@dataclass(slots=True)
class ExpenseItem:
    id: int
    expense_id: int
    label: Optional[str]
    amount_cents: int


@dataclass(slots=True)
class Reminder:
    id: int
    event_id: int
    remind_at: datetime
    sent: bool


@dataclass(slots=True)
class EventInviteLink:
    id: int
    event_id: int
    token: str
    max_uses: Optional[int]
    uses: int
    expires_at: Optional[datetime]

