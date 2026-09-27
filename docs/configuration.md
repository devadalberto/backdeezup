# Configuration

All configuration uses environment variables via [python-decouple](https://github.com/HBNetwork/python-decouple). Copy `.env.sample` to `.env` and set values before starting.

---

## Required

| Variable | Description |
|---|---|
| `GOOGLE_ENCRYPTION_KEY` | 44-char Fernet key that encrypts the OAuth token on disk. Generate once: `python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`. Never change after first auth. |
| `GOOGLE_CLIENT_SECRETS` | Path to OAuth client JSON. Default: `secrets/google_client.json`. |

---

## Google API

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_TOKEN_FILE` | `secrets/google_token.json` | Where the encrypted token is stored after `/auth/connect`. |
| `GOOGLE_MIME_ALLOWLIST` | `image/jpeg,image/png,...,video/mp4` | Comma-separated MIME types to discover via Drive. |

---

## Deletion behaviour

| Variable | Default | Description |
|---|---|---|
| `DRIVE_DELETE_MODE` | `trash` | `trash` = Google Drive trash (recoverable 30 days). `hard` = permanent. |
| `MIN_RETENTION_DAYS` | `3` | Days an asset must be held locally before `commit-delete` will act on it. |

!!! danger "Hard delete is irreversible"
    `DRIVE_DELETE_MODE=hard` permanently removes files from Google Drive with no recovery option.

---

## Django core

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | `insecure-key` | Must be a long random string in production. |
| `DEBUG` | `True` | Set `False` in production. |
| `ALLOWED_HOSTS` | `*` | Comma-separated allowed hostnames. |
| `DATABASE_URL` | SQLite | Use `postgres://user:pass@host:5432/db` in production. |
| `TIME_ZONE` | `America/Los_Angeles` | IANA zone name for Django's `TIME_ZONE` (admin display, `localtime`). Does **not** change the Celery Beat schedule: `celery_app.py` sets `app.conf.timezone` separately and it stays `America/Los_Angeles`. |

---

## Storage

| Variable | Default | Description |
|---|---|---|
| `MEDIA_ROOT` | `backend_django/media` | Local directory for imported files (`imported/<sha[:2]>/<sha>.ext`). |
| `STATIC_ROOT` | `backend_django/staticfiles` | Collected static files for production. |

---

## CORS / CSRF

| Variable | Default | Description |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | (empty = allow all) | Comma-separated origins. Empty allows all in dev. |
| `CSRF_TRUSTED_ORIGINS` | (empty) | Required when running behind a reverse proxy in production. |

---

## Admin UI labels

| Variable | Default |
|---|---|
| `ADMIN_SITE_HEADER` | `Admin` |
| `ADMIN_SITE_TITLE` | `Admin` |
| `ADMIN_INDEX_TITLE` | `Dashboard` |

---

## Sample `.env`

```env
DJANGO_SECRET_KEY=change-me-to-a-long-random-string
DEBUG=True
ALLOWED_HOSTS=*

GOOGLE_ENCRYPTION_KEY=your-44-char-fernet-key-here==
GOOGLE_CLIENT_SECRETS=secrets/google_client.json
GOOGLE_TOKEN_FILE=secrets/google_token.json
GOOGLE_MIME_ALLOWLIST=image/jpeg,image/png,image/gif,image/webp,video/mp4,video/quicktime

DRIVE_DELETE_MODE=trash
MIN_RETENTION_DAYS=3

# DATABASE_URL=postgres://backdeezup:password@localhost:5432/backdeezup
MEDIA_ROOT=backend_django/media
STATIC_ROOT=backend_django/staticfiles
```
