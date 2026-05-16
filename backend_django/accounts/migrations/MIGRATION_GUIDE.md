# Custom User Model Migration Guide

## Context

This migration adds `accounts.BackupUser` as the custom user model.
The DB already has the `auth_user` table from Django's default User.

## For a fresh deployment (no existing data)

```bash
make migrate
```

## For an existing deployment with users already in the DB

The `accounts_backupuser` table is identical to `auth_user`.
Use `--fake-initial` to tell Django the table already exists:

```bash
docker compose exec web python manage.py migrate accounts --fake-initial
docker compose exec web python manage.py migrate
```

This skips creating the `accounts_backupuser` table (since `auth_user` already covers it)
and applies all other pending migrations normally.

## Verify

```bash
docker compose exec web python manage.py shell -c "
from django.contrib.auth import get_user_model
U = get_user_model()
print('User model:', U)
print('Users:', U.objects.count())
"
```

Should print: `User model: <class 'accounts.models.BackupUser'>`
