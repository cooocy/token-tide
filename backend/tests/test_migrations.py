import importlib
from io import StringIO

from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_amount_migration_cleans_data_before_narrowing_columns() -> None:
    revision = importlib.import_module(
        "migrations.versions.202607251610_round_balance_amounts_to_two_decimals"
    )
    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": output},
    )

    with Operations.context(context):
        revision.upgrade()

    sql = output.getvalue()
    update_position = sql.index("UPDATE balance_snapshot")
    alter_position = sql.index("ALTER TABLE balance_snapshot")
    assert update_position < alter_position
    assert "available_amount = ROUND(available_amount, 2)" in sql
    assert "MODIFY available_amount NUMERIC(20, 2) NOT NULL" in sql


def test_prepaid_amount_migration_drops_and_restores_column() -> None:
    revision = importlib.import_module(
        "migrations.versions.202607251710_drop_prepaid_amount"
    )

    upgrade_output = StringIO()
    upgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": upgrade_output},
    )
    with Operations.context(upgrade_context):
        revision.upgrade()

    assert "ALTER TABLE balance_snapshot DROP COLUMN prepaid_amount" in (
        upgrade_output.getvalue()
    )

    downgrade_output = StringIO()
    downgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": downgrade_output},
    )
    with Operations.context(downgrade_context):
        revision.downgrade()

    assert "ALTER TABLE balance_snapshot ADD COLUMN prepaid_amount NUMERIC(20, 2)" in (
        downgrade_output.getvalue()
    )


def test_granted_amount_migration_drops_and_restores_column() -> None:
    revision = importlib.import_module(
        "migrations.versions.202607251800_drop_granted_amount"
    )

    upgrade_output = StringIO()
    upgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": upgrade_output},
    )
    with Operations.context(upgrade_context):
        revision.upgrade()

    assert "ALTER TABLE balance_snapshot DROP COLUMN granted_amount" in (
        upgrade_output.getvalue()
    )

    downgrade_output = StringIO()
    downgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": downgrade_output},
    )
    with Operations.context(downgrade_context):
        revision.downgrade()

    assert "ALTER TABLE balance_snapshot ADD COLUMN granted_amount NUMERIC(20, 2)" in (
        downgrade_output.getvalue()
    )


def test_balance_change_event_migration_creates_latest_snapshot_baselines() -> None:
    revision = importlib.import_module(
        "migrations.versions.202607271231_create_balance_change_event"
    )

    upgrade_output = StringIO()
    upgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": upgrade_output},
    )
    with Operations.context(upgrade_context):
        revision.upgrade()

    sql = upgrade_output.getvalue()
    assert "CREATE TABLE balance_change_event" in sql
    assert "UNIQUE (snapshot_id)" in sql
    assert "INSERT INTO balance_change_event" in sql
    assert "'INITIAL'" in sql
    assert "newer.observed_at > snapshot.observed_at" in sql
    assert "newer.id > snapshot.id" in sql

    downgrade_output = StringIO()
    downgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": downgrade_output},
    )
    with Operations.context(downgrade_context):
        revision.downgrade()

    assert "DROP TABLE balance_change_event" in downgrade_output.getvalue()


def test_token_usage_migration_creates_event_and_checkpoint_tables() -> None:
    revision = importlib.import_module(
        "migrations.versions.202607301226_create_token_usage_tables"
    )
    upgrade_output = StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": upgrade_output},
    )

    with Operations.context(context):
        revision.upgrade()

    sql = upgrade_output.getvalue()
    assert "CREATE TABLE token_usage_event" in sql
    assert "CREATE TABLE token_usage_checkpoint" in sql
    assert "UNIQUE (tool, source_event_id)" in sql

    downgrade_output = StringIO()
    downgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": downgrade_output},
    )
    with Operations.context(downgrade_context):
        revision.downgrade()

    downgrade_sql = downgrade_output.getvalue()
    assert "DROP TABLE token_usage_checkpoint" in downgrade_sql
    assert "DROP TABLE token_usage_event" in downgrade_sql


def test_token_usage_summary_migration_adds_occurred_time_index() -> None:
    revision = importlib.import_module(
        "migrations.versions.202607301546_index_token_usage_occurred_at"
    )
    upgrade_output = StringIO()
    context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": upgrade_output},
    )

    with Operations.context(context):
        revision.upgrade()

    assert (
        "CREATE INDEX idx_token_usage_event_occurred "
        "ON token_usage_event (occurred_at)"
    ) in upgrade_output.getvalue()

    downgrade_output = StringIO()
    downgrade_context = MigrationContext.configure(
        dialect_name="mysql",
        opts={"as_sql": True, "output_buffer": downgrade_output},
    )
    with Operations.context(downgrade_context):
        revision.downgrade()

    assert "DROP INDEX idx_token_usage_event_occurred" in (
        downgrade_output.getvalue()
    )
