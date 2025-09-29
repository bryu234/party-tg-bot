from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, engine_from_config, pool
from sqlalchemy.engine import make_url

from partyshare.config import get_settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _sync_database_url() -> str:
    url = make_url(get_settings().database_url)
    if "+asyncpg" in url.drivername:
        url = url.set(drivername=url.drivername.replace("+asyncpg", ""))
    return str(url)


def run_migrations_offline() -> None:
    url = _sync_database_url()
    context.configure(url=url, literal_binds=True, render_as_batch=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_sync_database_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, render_as_batch=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

