from __future__ import annotations

from typing import Any, Iterable, Optional

import asyncpg

from partyshare.logging import get_logger, sql_logger


class Database:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None
        self._log = get_logger(__name__)

    async def connect(self) -> None:
        if self._pool is None:
            # asyncpg ожидает схему postgresql/postgres, без "+asyncpg"
            dsn = self._dsn.replace("+asyncpg", "")
            self._pool = await asyncpg.create_pool(dsn)
            self._log.info("db.pool.created")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            self._log.info("db.pool.closed")

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        await self._ensure_pool()
        assert self._pool
        sql_logger.info("sql.fetch", query=query, args=args)
        return await self._pool.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        await self._ensure_pool()
        assert self._pool
        sql_logger.info("sql.fetchrow", query=query, args=args)
        return await self._pool.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        await self._ensure_pool()
        assert self._pool
        sql_logger.info("sql.fetchval", query=query, args=args)
        return await self._pool.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        await self._ensure_pool()
        assert self._pool
        sql_logger.info("sql.execute", query=query, args=args)
        return await self._pool.execute(query, *args)

    async def executemany(self, command: str, args: Iterable[Iterable[Any]]) -> None:
        await self._ensure_pool()
        assert self._pool
        sql_logger.info("sql.executemany", query=command)
        await self._pool.executemany(command, args)

    async def _ensure_pool(self) -> None:
        if self._pool is None:
            await self.connect()


class PartyShareRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def ensure_user(self, tg_id: int, username: Optional[str], full_name: Optional[str]) -> int:
        row = await self.db.fetchrow(
            """
            INSERT INTO users (tg_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (tg_id) DO UPDATE
                SET username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name
            RETURNING id
            """,
            tg_id,
            username,
            full_name,
        )
        assert row is not None
        return int(row["id"])

    async def get_user_by_username(self, username: str) -> asyncpg.Record | None:
        clean = username.lstrip("@")
        return await self.db.fetchrow("SELECT * FROM users WHERE username = $1", clean)

    async def create_event(
        self,
        owner_id: int,
        title: str,
        starts_at,
        location: Optional[str],
        notes: Optional[str],
    ) -> asyncpg.Record:
        row = await self.db.fetchrow(
            """
            INSERT INTO events (owner_id, title, starts_at, location, notes)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING *
            """,
            owner_id,
            title,
            starts_at,
            location,
            notes,
        )
        assert row is not None
        await self.db.execute(
            """
            INSERT INTO event_participants (event_id, user_id, status)
            VALUES ($1, $2, 'going')
            ON CONFLICT (event_id, user_id) DO UPDATE SET status = 'going'
            """,
            row["id"],
            owner_id,
        )
        return row

    async def get_event(self, event_id: int) -> asyncpg.Record | None:
        return await self.db.fetchrow("SELECT * FROM events WHERE id = $1", event_id)

    async def update_event_field(self, event_id: int, field: str, value: Any) -> None:
        if field not in {"title", "starts_at", "location", "notes", "canceled", "owner_id"}:
            raise ValueError("Недопустимое поле для обновления")
        await self.db.execute(f"UPDATE events SET {field} = $1 WHERE id = $2", value, event_id)

    async def list_owner_events(self, owner_id: int) -> list[asyncpg.Record]:
        return await self.db.fetch(
            """
            SELECT e.*, r.remind_at
            FROM events e
            LEFT JOIN reminders r ON r.event_id = e.id
            WHERE e.owner_id = $1
            ORDER BY e.starts_at
            """,
            owner_id,
        )

    async def list_participant_events(self, user_id: int) -> list[asyncpg.Record]:
        return await self.db.fetch(
            """
            SELECT e.*, ep.status, r.remind_at
            FROM events e
            JOIN event_participants ep ON ep.event_id = e.id
            LEFT JOIN reminders r ON r.event_id = e.id
            WHERE ep.user_id = $1
            ORDER BY e.starts_at
            """,
            user_id,
        )

    async def set_participant_status(self, event_id: int, user_id: int, status: str) -> None:
        await self.db.execute(
            """
            INSERT INTO event_participants (event_id, user_id, status)
            VALUES ($1, $2, $3)
            ON CONFLICT (event_id, user_id) DO UPDATE SET status = EXCLUDED.status
            """,
            event_id,
            user_id,
            status,
        )

    async def get_participant(self, event_id: int, user_id: int) -> asyncpg.Record | None:
        return await self.db.fetchrow(
            "SELECT * FROM event_participants WHERE event_id = $1 AND user_id = $2",
            event_id,
            user_id,
        )

    async def add_invite_link(
        self,
        event_id: int,
        token: str,
        max_uses: Optional[int],
        expires_at,
    ) -> asyncpg.Record:
        row = await self.db.fetchrow(
            """
            INSERT INTO event_invite_links (event_id, token, max_uses, expires_at)
            VALUES ($1, $2, $3, $4)
            RETURNING *
            """,
            event_id,
            token,
            max_uses,
            expires_at,
        )
        assert row is not None
        return row

    async def get_invite_link_by_token(self, token: str) -> asyncpg.Record | None:
        return await self.db.fetchrow(
            "SELECT * FROM event_invite_links WHERE token = $1",
            token,
        )

    async def get_invite_link(self, event_id: int) -> asyncpg.Record | None:
        return await self.db.fetchrow(
            "SELECT * FROM event_invite_links WHERE event_id = $1 ORDER BY id DESC LIMIT 1",
            event_id,
        )

    async def increment_invite_use(self, invite_id: int) -> None:
        await self.db.execute(
            "UPDATE event_invite_links SET uses = uses + 1 WHERE id = $1",
            invite_id,
        )

    async def create_reminder(self, event_id: int, remind_at) -> None:
        await self.db.execute(
            """
            INSERT INTO reminders (event_id, remind_at)
            VALUES ($1, $2)
            ON CONFLICT DO NOTHING
            """,
            event_id,
            remind_at,
        )

    async def fetch_pending_reminders(self, now) -> list[asyncpg.Record]:
        return await self.db.fetch(
            """
            SELECT r.id, r.event_id, e.title, e.starts_at, e.owner_id
            FROM reminders r
            JOIN events e ON e.id = r.event_id
            WHERE r.sent = false
              AND r.remind_at <= $1
              AND e.canceled = false
            """,
            now,
        )

    async def mark_reminder_sent(self, reminder_id: int) -> None:
        await self.db.execute("UPDATE reminders SET sent = true WHERE id = $1", reminder_id)

    async def get_event_participants(self, event_id: int) -> list[asyncpg.Record]:
        return await self.db.fetch(
            """
            SELECT ep.*, u.tg_id, u.username, u.full_name
            FROM event_participants ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.event_id = $1
            """,
            event_id,
        )

    async def remove_participant(self, event_id: int, user_id: int) -> None:
        await self.db.execute(
            "DELETE FROM event_participants WHERE event_id = $1 AND user_id = $2",
            event_id,
            user_id,
        )

    async def create_expense(
        self,
        event_id: int,
        payer_id: int,
        created_by: int,
        title: str,
        amount_cents: int,
        currency: str,
        is_shared: bool,
    ) -> asyncpg.Record:
        row = await self.db.fetchrow(
            """
            INSERT INTO expenses (event_id, payer_id, created_by, title, amount_cents, currency, is_shared)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
            """,
            event_id,
            payer_id,
            created_by,
            title,
            amount_cents,
            currency,
            is_shared,
        )
        assert row is not None
        return row

    async def add_expense_item(
        self,
        expense_id: int,
        label: Optional[str],
        amount_cents: int,
        consumer_ids: Iterable[int],
    ) -> asyncpg.Record:
        row = await self.db.fetchrow(
            """
            INSERT INTO expense_items (expense_id, label, amount_cents)
            VALUES ($1, $2, $3)
            RETURNING *
            """,
            expense_id,
            label,
            amount_cents,
        )
        assert row is not None
        if consumer_ids:
            await self.db.executemany(
                """
                INSERT INTO expense_item_consumers (item_id, user_id)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
                """,
                ((row["id"], consumer) for consumer in consumer_ids),
            )
        return row

    async def get_expense_items(self, expense_id: int) -> list[asyncpg.Record]:
        return await self.db.fetch(
            """
            SELECT ei.*, array_agg(eic.user_id) FILTER (WHERE eic.user_id IS NOT NULL) AS consumers
            FROM expense_items ei
            LEFT JOIN expense_item_consumers eic ON eic.item_id = ei.id
            WHERE ei.expense_id = $1
            GROUP BY ei.id
            ORDER BY ei.id
            """,
            expense_id,
        )

    async def get_event_expenses(self, event_id: int) -> list[asyncpg.Record]:
        return await self.db.fetch(
            """
            SELECT e.*,
                   u.username AS payer_username,
                   u.full_name AS payer_full_name,
                   u.tg_id AS payer_tg_id
            FROM expenses e
            LEFT JOIN users u ON u.id = e.payer_id
            WHERE e.event_id = $1
            ORDER BY e.created_at
            """,
            event_id,
        )

    async def delete_expense(self, expense_id: int) -> None:
        await self.db.execute("DELETE FROM expenses WHERE id = $1", expense_id)

    async def get_user(self, user_id: int) -> asyncpg.Record | None:
        return await self.db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)

    async def transfer_ownership(self, event_id: int, new_owner_id: int) -> None:
        await self.db.execute("UPDATE events SET owner_id = $1 WHERE id = $2", new_owner_id, event_id)
        await self.set_participant_status(event_id, new_owner_id, "going")

    async def cancel_event(self, event_id: int) -> None:
        await self.db.execute("UPDATE events SET canceled = true WHERE id = $1", event_id)

    async def list_event_participants_with_status(self, event_id: int) -> list[asyncpg.Record]:
        return await self.db.fetch(
            """
            SELECT ep.user_id, ep.status, u.tg_id, u.username, u.full_name
            FROM event_participants ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.event_id = $1
            """,
            event_id,
        )

    async def get_expense(self, expense_id: int) -> asyncpg.Record | None:
        return await self.db.fetchrow("SELECT * FROM expenses WHERE id = $1", expense_id)


_global_repo: PartyShareRepository | None = None


def set_global_repository(repo: PartyShareRepository) -> None:
    global _global_repo
    _global_repo = repo


def get_global_repository() -> PartyShareRepository:
    if _global_repo is None:
        raise RuntimeError("Репозиторий не инициализирован")
    return _global_repo

