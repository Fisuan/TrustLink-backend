import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from app.core.config import settings
from app.db.base_class import Base
from app.models import User, Incident, ChatMessage, Attachment

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

# Переводим URL из асинхронного в синхронное для Alembic
sync_url = str(settings.DATABASE_URI).replace('+asyncpg', '')
config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=False,
        dialect_opts={"paramstyle": "named"},
        # Используем as_sql, чтобы не подключаться к базе данных
        as_sql=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Принудительно использовать offline режим для генерации миграции
    # без подключения к базе данных
    # TODO: Удалите эту строку, когда сервер базы данных будет доступен
    return run_migrations_offline()
    
    connectable = config.attributes.get("connection", None)
    
    if connectable is None:
        connectable = context.config.attributes.get("connection", None)
    
    if connectable is None:
        # Используем синхронную строку подключения, заменив asyncpg на psycopg2
        url = config.get_main_option("sqlalchemy.url")
        connectable = context.config.attributes.get("connection", None)
        if connectable is None:
            from sqlalchemy import create_engine
            connectable = create_engine(url)

    with connectable.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online() 