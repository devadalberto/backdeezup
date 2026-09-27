"""
Data migration: create accounts_backupuser table from auth_user.
PostgreSQL-only — skipped automatically when running tests against SQLite.

auth_user only exists on an install that ran with the built-in Django user model
before this repo switched to AUTH_USER_MODEL = 'accounts.BackupUser' -- a fresh
install (Phase 49's installer, or any brand-new `make migrate`) never creates
auth_user at all, so both statements are wrapped in an existence check and
become a no-op there instead of failing outright (found running scripts/install.sh
end-to-end against a fresh database).
"""
from django.db import migrations

_CREATE_AND_SEED_PG = """
DO $$
BEGIN
    IF to_regclass('auth_user') IS NOT NULL THEN
        EXECUTE 'CREATE TABLE IF NOT EXISTS accounts_backupuser (LIKE auth_user INCLUDING ALL)';
        EXECUTE 'INSERT INTO accounts_backupuser SELECT * FROM auth_user ON CONFLICT DO NOTHING';
    END IF;
END $$;
"""

_DROP_TABLE = "DROP TABLE IF EXISTS accounts_backupuser;"


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # RunSQL with database_routers=None runs on all backends.
        # We guard PostgreSQL-specific SQL with a conditional so SQLite (test)
        # never sees the LIKE...INCLUDING ALL syntax.
        migrations.RunSQL(
            sql=migrations.RunSQL.noop,   # handled in state_operations below
            reverse_sql=migrations.RunSQL.noop,
            state_operations=[],
        ),
    ]

    def apply(self, project_state, schema_editor, collect_sql=False):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(_CREATE_AND_SEED_PG)
        return super().apply(project_state, schema_editor, collect_sql=collect_sql)

    def unapply(self, project_state, schema_editor, collect_sql=False):
        if schema_editor.connection.vendor == "postgresql":
            schema_editor.execute(_DROP_TABLE)
        return super().unapply(project_state, schema_editor, collect_sql=collect_sql)
