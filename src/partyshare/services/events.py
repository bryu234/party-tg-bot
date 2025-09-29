from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from partyshare.db.models import ParticipantStatus


STATUS_CYCLE = [
    ParticipantStatus.GOING,
    ParticipantStatus.MAYBE,
    ParticipantStatus.DECLINED,
]


STATUS_LABELS = {
    ParticipantStatus.INVITED: "приглашён",
    ParticipantStatus.GOING: "иду",
    ParticipantStatus.MAYBE: "возможно",
    ParticipantStatus.DECLINED: "не иду",
}


@dataclass(slots=True)
class EventCardData:
    event_id: int
    title: str
    starts_at: datetime
    location: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[ParticipantStatus] = None
    is_owner: bool = False
    remind_at: Optional[datetime] = None


def format_event_card(card: EventCardData, tz: ZoneInfo) -> str:
    local_dt = card.starts_at.astimezone(tz)
    header = f"#{card.event_id} — {card.title}" if card.is_owner else f"#{card.event_id} {card.title}"
    lines = [header, local_dt.strftime("%d.%m.%Y %H:%M %Z")]
    if card.location:
        lines.append(f"Локация: {card.location}")
    if card.notes:
        lines.append(f"Заметки: {card.notes}")
    if card.remind_at:
        lines.append(f"Напоминание: {card.remind_at.astimezone(tz).strftime('%d.%m.%Y %H:%М %Z')}")
    if card.status:
        lines.append(f"Статус: {STATUS_LABELS.get(card.status, card.status.value)}")
    return "\n".join(lines)


def build_event_cards(rows: Iterable[dict], tz: ZoneInfo, is_owner: bool) -> list[EventCardData]:
    cards: list[EventCardData] = []
    for row in rows:
        cards.append(
            EventCardData(
                event_id=row["id"],
                title=row["title"],
                starts_at=row["starts_at"],
                location=row.get("location"),
                notes=row.get("notes"),
                remind_at=row.get("remind_at"),
                is_owner=is_owner,
                status=ParticipantStatus(row["status"]) if row.get("status") else None,
            )
        )
    return cards


def next_status(current: ParticipantStatus) -> ParticipantStatus:
    if current == ParticipantStatus.INVITED:
        return ParticipantStatus.GOING
    try:
        index = STATUS_CYCLE.index(current)
    except ValueError:
        return ParticipantStatus.GOING
    return STATUS_CYCLE[(index + 1) % len(STATUS_CYCLE)]


def humanize_status(status: ParticipantStatus) -> str:
    return STATUS_LABELS.get(status, status.value)

