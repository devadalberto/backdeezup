"""
One-shot migration fix for custom user model.
Inserts the accounts.0001_initial migration record then runs all pending migrations.
Run with: docker compose exec web python fix_migration.py
"""
import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, "/app/backend_django")
django.setup()

from django.db import connection
from django.utils import timezone

with connection.cursor() as cursor:
    cursor.execute("""
        INSERT INTO django_migrations (app, name, applied)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING
    """, ["accounts", "0001_initial", timezone.now()])
    print("Inserted accounts.0001_initial into django_migrations")

from django.core.management import call_command
call_command("migrate", verbosity=1)
print("All migrations complete.")
