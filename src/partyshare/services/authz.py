from __future__ import annotations

from typing import Protocol


class Repository(Protocol):
    async def fetchval(self, query: str, *args: object) -> object: ...


class AuthorizationError(PermissionError):
    pass


async def is_event_owner(repo: Repository, user_id: int, event_id: int) -> bool:
    owner_id = await repo.fetchval(
        "SELECT owner_id FROM events WHERE id = $1",
        event_id,
    )
    return owner_id == user_id


async def assert_event_owner(repo: Repository, user_id: int, event_id: int) -> None:
    if not await is_event_owner(repo, user_id, event_id):
        raise AuthorizationError("Только владелец события может выполнять это действие.")


async def assert_event_participant(repo: Repository, user_id: int, event_id: int) -> None:
    participant_id = await repo.fetchval(
        "SELECT user_id FROM event_participants WHERE event_id = $1 AND user_id = $2",
        event_id,
        user_id,
    )
    if participant_id is None:
        raise AuthorizationError("Вы не участвуете в этом событии.")

