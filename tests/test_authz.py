import pytest

from partyshare.services.authz import AuthorizationError, assert_event_owner, assert_event_participant, is_event_owner


class StubRepo:
    def __init__(self, owner_id: int, participants: set[int]) -> None:
        self.owner_id = owner_id
        self.participants = participants

    async def fetchval(self, query: str, *args: object) -> object:
        if "owner_id" in query:
            return self.owner_id if args[0] == 1 else None
        return args[1] if args[1] in self.participants else None


@pytest.mark.asyncio
async def test_is_event_owner():
    repo = StubRepo(owner_id=42, participants={42, 100})
    result = await is_event_owner(repo, 42, 1)
    assert result is True


@pytest.mark.asyncio
async def test_assert_event_owner_denied():
    repo = StubRepo(owner_id=10, participants={10})
    with pytest.raises(AuthorizationError):
        await assert_event_owner(repo, 11, 1)


@pytest.mark.asyncio
async def test_assert_event_participant():
    repo = StubRepo(owner_id=10, participants={10, 20})
    await assert_event_participant(repo, 20, 1)


@pytest.mark.asyncio
async def test_assert_event_participant_denied():
    repo = StubRepo(owner_id=10, participants={10})
    with pytest.raises(AuthorizationError):
        await assert_event_participant(repo, 99, 1)

