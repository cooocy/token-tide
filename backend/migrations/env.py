import logging

from alembic import context
from sqlalchemy import engine_from_config, pool

from token_tide.balance import models as balance_models  # noqa: F401
from token_tide.token_usage import models as token_usage_models  # noqa: F401
from token_tide.bootstrap import bootstrap_settings
from token_tide.database import Base
from token_tide.logging import configure_alembic_logging

config = context.config
configure_alembic_logging()
logger = logging.getLogger(__name__)
try:
    settings = bootstrap_settings()
except Exception:
    logger.exception("Alembic configuration bootstrap failed")
    raise
config.set_main_option("sqlalchemy.url", settings.database.url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


try:
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
except Exception:
    logger.exception("Database migration failed")
    raise
