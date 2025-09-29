from datetime import datetime, timezone

from partyshare.services.events import EventCardData, format_event_card, humanize_status
from partyshare.db.models import ParticipantStatus


def test_format_event_card_owner():
    card = EventCardData(
        event_id=1,
        title="Вечеринка",
        starts_at=datetime(2024, 5, 10, 18, 0, tzinfo=timezone.utc),
        location="Бар",
        notes="Принести десерт",
        status=ParticipantStatus.GOING,
        is_owner=True,
    )
    text = format_event_card(card, timezone.utc)
    assert "Вечеринка" in text
    assert "Принести десерт" in text


def test_humanize_status():
    assert humanize_status(ParticipantStatus.GOING) == "иду"
    assert humanize_status(ParticipantStatus.MAYBE) == "возможно"

