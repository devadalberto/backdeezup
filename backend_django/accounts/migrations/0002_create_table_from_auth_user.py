"""
Data migration: create accounts_backupuser table from auth_user.

Context
-------
0001_initial was applied with --fake (or --fake-initial) on an existing
deployment that already had an auth_user table.  That means Django's
migration state records the migration as done but the
accounts_backupuser table was never physically created.

This migration materialises the table and seeds it from auth_user in
one atomic operation, so Django's custom-user-model machinery works
correctly on the next restart.

PostgreSQL-only: uses "CREATE TABLE … LIKE … INCLUDING ALL" to copy the
full schema (columns, constraints, indexes, defaults) from auth_user,
then bulk-inserts every existing row.

Reverse operation drops accounts_backupuser (safe: auth_user is kept).
"""

from django.db import migrations

_CREATE_AND_SEED = """
-- Step 1: create accounts_backupuser with the same schema as auth_user
--         INCLUDING ALL copies columns, constraints, indexes, and defaults.
CREATE TABLE IF NOT EXISTS accounts_backupuser
    (LIKE auth_user INCLUDING ALL);

-- Step 2: copy every existing user row (idempotent via ON CONFLICT DO NOTHING)
INSERT INTO accounts_backupuser
SELECT * FROM auth_user
ON CONFLICT DO NOTHING;
"""

_DROP_TABLE = """
DROP TABLE IF EXISTS accounts_backupuser;
"""


class Migration(migrations.Migration):
    """Create accounts_backupuser and seed it from auth_user."""

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=_CREATE_AND_SEED,
            reverse_sql=_DROP_TABLE,
        ),
    ]
