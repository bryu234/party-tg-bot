from datetime import datetime, timedelta, timezone

import pytest

from partyshare.db.repo import PartyShareRepository


class DummyDB:
    def __init__(self) -> None:
        self.links = {}

    async def fetchrow(self, query: str, *args):
        if "event_invite_links" in query:
            token = args[0]
            return self.links.get(token)
        return None

    async def execute(self, query: str, *args):
        return "OK"


@pytest.mark.asyncio
async def test_invitelink_expired():
    db = DummyDB()
    repo = PartyShareRepository(db)  # type: ignore[arg-type]
    token = "abc"
    db.links[token] = {
        "id": 1,
        "event_id": 1,
        "token": token,
        "max_uses": None,
        "uses": 0,
        "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),
    }

    link = await repo.get_invite_link_by_token(token)
    assert link is not None
    assert link["expires_at"] < datetime.now(timezone.utc)

