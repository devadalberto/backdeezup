# Configuration

All configuration uses environment variables via [python-decouple](https://github.com/HBNetwork/python-decouple). Copy `.env.sample` to `.env` and set values before starting. The full, auto-generated list of every variable the code actually reads is at the bottom of this page — the tables here are a curated tour of the ones you're most likely to touch.

---

## Required — startup fails without these

| Variable | Description |
|---|---|
| `DJANGO_SECRET_KEY` | No default. Startup raises `ImproperlyConfigured` if unset, or if it's still `insecure-key`/`change-me`/empty. Generate: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`. |
| `GOOGLE_ENCRYPTION_KEY` | 44-char Fernet key that encrypts the OAuth token on disk. Generate once: `python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`. Never change after first auth — the existing token becomes undecryptable. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | No compose defaults — the `db` container needs all three, and `DATABASE_URL` must reference the same values. |
| `REDIS_PASSWORD` | No compose default — the `redis` container's `--requirepass` and every service's `REDIS_URL` depend on it. |

---

## Google API

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_CLIENT_SECRETS` | `secrets/google_client.json` | Path to the OAuth client JSON (Desktop app type, not Web). |
| `GOOGLE_TOKEN_FILE` | `secrets/google_token.json` | Where the encrypted token is stored after `/auth/connect`. |
| `GOOGLE_MIME_ALLOWLIST` | `image/jpeg` (see `.env.sample` for the full list) | Comma-separated MIME types to discover via Drive. |
| `GMAIL_PUBSUB_TOPIC` | (empty = disabled) | Enables Gmail push notifications instead of 6-hour polling. |

---

## Deletion & pipeline behaviour

| Variable | Default | Description |
|---|---|---|
| `DRIVE_DELETE_MODE` | `trash` | `trash` = Google Drive trash (recoverable ~30 days). `hard` = permanent. |
| `MIN_RETENTION_DAYS` | `3` | Days an asset must be held locally before cleanup will act on it. |
| `RESUME_MIN_MB` | `50` | Files at or above this size use HTTP Range resumable download (Phase 42). |
| `MAX_CONCURRENT_DOWNLOADS` | `2` | Redis-semaphore cap on simultaneous Drive downloads. `0` disables the cap (Phase 43). |
| `GOOGLE_API_MAX_RPS` | `0` (disabled) | Redis token-bucket cap on Google API calls/sec, independent of 429/5xx backoff (Phase 43). |

!!! danger "Hard delete is irreversible"
    `DRIVE_DELETE_MODE=hard` permanently removes files from Google Drive with no recovery option.

---

## Django core

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `False` | Must be explicitly set `True` for local dev; production should leave it unset/`False`. |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hostnames. |
| `DATABASE_URL` | (empty → SQLite) | `postgres://user:pass@host:5432/db` in production; must match `POSTGRES_*` above. |
| `TIME_ZONE` | `America/Los_Angeles` | IANA zone name for Django's `TIME_ZONE` (admin display, `localtime`). Does **not** change the Celery Beat schedule: `celery_app.py` sets `app.conf.timezone` separately and it stays `America/Los_Angeles`. |

---

## Storage & restore

| Variable | Default | Description |
|---|---|---|
| `MEDIA_ROOT` | `/app/media` (container) | Local directory for downloaded/imported files. Back this up — see `docs/disaster-recovery.md`. |
| `STATIC_ROOT` | `/app/staticfiles` (container) | Collected static files for production. |
| `STORAGE_WARN_PCT` / `STORAGE_PAUSE_PCT` | `85` / `95` | Disk-usage thresholds for the storage guard (Phase 32). |
| `RESTORE_ROOT` | `MEDIA_ROOT/restores` | Every restore must resolve inside this directory (Phase 37). |
| `DB_BACKUP_DIR` | `/app/backups` | Where the optional weekly DB-dump Beat task writes (Phase 38). |

---

## CORS / CSRF

| Variable | Default | Description |
|---|---|---|
| `CORS_ALLOWED_ORIGINS` | (empty = allow all in dev) | Comma-separated origins. |
| `CSRF_TRUSTED_ORIGINS` | (empty) | Required when running behind a reverse proxy or a non-`localhost` hostname. |

---

## Compose ports / bind address (Phase 39)

| Variable | Default | Description |
|---|---|---|
| `BIND_ADDR` | `127.0.0.1` | Host interface `docker-compose` publishes on. `0.0.0.0` exposes it on the LAN. |
| `WEB_PORT` | `8845` | Host port for the `web` container. |
| `NGINX_HTTP_PORT` / `NGINX_HTTPS_PORT` | `8844` / `8445` | Host ports for `nginx`. |

---

## Admin UI labels

| Variable | Default |
|---|---|
| `ADMIN_SITE_HEADER` | `BackDeezUp Admin` |
| `ADMIN_SITE_TITLE` | `BackDeezUp` |
| `ADMIN_INDEX_TITLE` | `Dashboard` |

---

## Sample `.env`

See `.env.sample` in the repo root for the complete, commented sample — it's kept next to the code so it can't silently drift from what's actually read.

---

## Common mistakes

Real problems, drawn from this repo's own history and code comments — not hypothetical:

| Mistake | Symptom | Fix |
|---|---|---|
| `DJANGO_SECRET_KEY` left as `CHANGE_ME_...` from `.env.sample` | Container won't start: `ImproperlyConfigured` | Generate a real value (see "Required" above), put it in `.env`, `make up`. |
| `GOOGLE_ENCRYPTION_KEY` changed after the first `make auth` | Gmail/Drive calls fail decrypting the token | Restore the original key, or `rm secrets/google_token.json && make auth` to re-auth under the new key. |
| `REDIS_PASSWORD` missing from `.env` | `redis` container healthcheck fails / Celery can't connect | Set `REDIS_PASSWORD` — it has no default in `docker-compose.yml`. |
| Edited `.env` then ran `docker compose restart` | Old values still in effect | Use `make up` (or `make redeploy`), not `restart` — `restart` reuses the container's existing environment. |
| New hostname/port not in `CSRF_TRUSTED_ORIGINS` | `403 Forbidden` on login (CSRF check) | Add `https://your-host:port` to `.env`, then `make up`. |
| `DRIVE_DELETE_MODE=hard` set without reading the danger box above | Deleted-from-cleanup Drive files are gone for good | Leave it at `trash` (the default) unless you specifically want permanent deletes. |
| Upgrading to a non-root image without `make fix-perms` first | Container crashes on start unable to write `MEDIA_ROOT` | Run `make fix-perms` once, then `make up` (see `docs/upgrading.md`). |

---

<!-- BEGIN GENERATED CONFIG REFERENCE (scripts/gen_config_ref.py) -->

Generated by `python3 scripts/gen_config_ref.py` — every `config(...)` call
in `backend_django/` plus every `${VAR}` interpolation in `docker-compose.yml`.
Do not hand-edit between these markers; rerun the script instead.

### Application (`backend_django/`, read via python-decouple)

| Variable | Cast | Default | Required | Read in |
|---|---|---|---|---|
| `ADMIN_INDEX_TITLE` | `str` | `'Dashboard'` | no | `backend_django/config/settings.py:238` |
| `ADMIN_SITE_HEADER` | `str` | `'BackDeezUp Admin'` | no | `backend_django/config/settings.py:236` |
| `ADMIN_SITE_TITLE` | `str` | `'BackDeezUp'` | no | `backend_django/config/settings.py:237` |
| `ALLOWED_HOSTS` | `str` | `'localhost,127.0.0.1'` | no | `backend_django/config/settings.py:25` |
| `CLEANUP_DRY_RUN_MAX_AGE_HOURS` | `int` | `24` | no | `backend_django/config/settings.py:186` |
| `CLEANUP_PAUSED` | `bool` | `False` | no | `backend_django/config/settings.py:182` |
| `CLEANUP_REQUIRE_DRY_RUN` | `bool` | `True` | no | `backend_django/config/settings.py:185` |
| `CORS_ALLOWED_ORIGINS` | `str` | `''` | no | `backend_django/config/settings.py:29` |
| `CSRF_TRUSTED_ORIGINS` | `str` | `''` | no | `backend_django/config/settings.py:41` |
| `DATABASE_URL` | `str` | `''` | no | `backend_django/config/settings.py:128` |
| `DB_BACKUP_DIR` | `str` | `'/app/backups'` | no | `backend_django/config/settings.py:209` |
| `DB_BACKUP_ENABLED` | `bool` | `False` | no | `backend_django/config/settings.py:207` |
| `DB_BACKUP_KEEP_LAST` | `int` | `14` | no | `backend_django/config/settings.py:208` |
| `DEBUG` | `bool` | `False` | no | `backend_django/config/settings.py:22` |
| `DEFAULT_FROM_EMAIL` | `str` | `'backdeezup@localhost'` | no | `backend_django/config/settings.py:177` |
| `DJANGO_SECRET_KEY` | `str` | *(none)* | **yes** | `backend_django/config/settings.py:11` |
| `DRIVE_DELETE_MODE` | `str` | `'trash'` | no | `backend_django/google_media_backup/management/commands/drive_pipeline.py:289`, `backend_django/google_media_backup/tasks.py:119` |
| `EMAIL_BACKEND` | `str` | `'django.core.mail.backends.smtp.EmailBackend'` | no | `backend_django/config/settings.py:171` |
| `EMAIL_HOST` | `str` | `''` | no | `backend_django/config/settings.py:172` |
| `EMAIL_HOST_PASSWORD` | `str` | `''` | no | `backend_django/config/settings.py:175` |
| `EMAIL_HOST_USER` | `str` | `''` | no | `backend_django/config/settings.py:174` |
| `EMAIL_PORT` | `int` | `587` | no | `backend_django/config/settings.py:173` |
| `EMAIL_USE_TLS` | `bool` | `True` | no | `backend_django/config/settings.py:176` |
| `EXPORT_ASYNC_THRESHOLD` | `int` | `200` | no | `backend_django/config/settings.py:192` |
| `GMAIL_PUBSUB_TOPIC` | `str` | `''` | no | `backend_django/google_gmail_backup/management/commands/setup_gmail_watch.py:39`, `backend_django/google_gmail_backup/tasks.py:400` |
| `GOOGLE_API_MAX_RPS` | `int` | `0` | no | `backend_django/core/ratelimit.py:22` |
| `GOOGLE_CLIENT_SECRETS` | `str` | `'secrets/google_client.json'` | no | `backend_django/google_gmail_backup/services_gmail.py:16`, `backend_django/google_media_backup/services_google.py:34` |
| `GOOGLE_ENCRYPTION_KEY` | `str` | `''` | no | `backend_django/google_media_backup/utils.py:42` |
| `GOOGLE_MIME_ALLOWLIST` | `str` | `'image/jpeg'` | no | `backend_django/google_media_backup/services_google.py:38` |
| `GOOGLE_TOKEN_FILE` | `str` | `'secrets/google_token.json'` | no | `backend_django/google_gmail_backup/services_gmail.py:17`, `backend_django/google_media_backup/services_google.py:35` |
| `INTEGRITY_CHECK_ENABLED` | `bool` | `True` | no | `backend_django/config/settings.py:154` |
| `INTEGRITY_CHECK_SAMPLE_SIZE` | `int` | `200` | no | `backend_django/config/settings.py:155` |
| `MAX_CONCURRENT_DOWNLOADS` | `int` | `2` | no | `backend_django/core/ratelimit.py:21` |
| `MEDIA_ROOT` | `str` | `'media'`; `str(BASE_DIR / 'media')` | no | `backend_django/config/settings.py:149`, `backend_django/google_media_backup/utils.py:12` |
| `MIN_RETENTION_DAYS` | `str` | `'3'` | no | `backend_django/google_media_backup/management/commands/drive_pipeline.py:288`, `backend_django/google_media_backup/tasks.py:118` |
| `NOTIFY_DISCORD_URL` | `str` | `''` | no | `backend_django/config/settings.py:165` |
| `NOTIFY_EMAIL_TO` | `str` | `''` | no | `backend_django/config/settings.py:166` |
| `NOTIFY_SLACK_URL` | `str` | `''` | no | `backend_django/config/settings.py:164` |
| `NOTIFY_STALE_BACKUP_HOURS` | `int` | `0` | no | `backend_django/config/settings.py:168` |
| `NOTIFY_WEBHOOK_URL` | `str` | `''` | no | `backend_django/config/settings.py:163` |
| `REDIS_URL` | `str` | `'redis://redis:6379/0'` | no | `backend_django/config/settings.py:262`, `backend_django/config/settings.py:274` |
| `RESTORE_ROOT` | `str` | `str(Path(MEDIA_ROOT) / 'restores')` | no | `backend_django/config/settings.py:197` |
| `RESTORE_SMOKE_TEST_ENABLED` | `bool` | `False` | no | `backend_django/config/settings.py:200` |
| `RESUME_MIN_MB` | `int` | `50` | no | `backend_django/google_media_backup/services_google.py:21` |
| `SECURE_HSTS_SECONDS` | `int` | `0` | no | `backend_django/config/settings.py:100` |
| `SECURE_SSL_REDIRECT` | `bool` | `False` | no | `backend_django/config/settings.py:99` |
| `SENTRY_DSN` | `str` | `''` | no | `backend_django/config/settings.py:288` |
| `SENTRY_ENVIRONMENT` | `str` | `'production'` | no | `backend_django/config/settings.py:299` |
| `SENTRY_RELEASE` | `str` | `''` | no | `backend_django/config/settings.py:300` |
| `STATIC_ROOT` | `str` | `str(BASE_DIR / 'staticfiles')` | no | `backend_django/config/settings.py:146` |
| `STORAGE_GUARD_ENABLED` | `bool` | `True` | no | `backend_django/config/settings.py:160` |
| `STORAGE_PAUSE_PCT` | `int` | `95` | no | `backend_django/config/settings.py:159` |
| `STORAGE_WARN_PCT` | `int` | `85` | no | `backend_django/config/settings.py:158` |
| `SWAGGER_DESCRIPTION` | `str` | `''` | no | `backend_django/config/settings.py:241`, `backend_django/google_media_backup/api.py:24` |
| `SWAGGER_TITLE` | `str` | `'API'`; `'BackDeezUp API'` | no | `backend_django/config/settings.py:240`, `backend_django/google_media_backup/api.py:23` |
| `SWAGGER_VERSION` | `str` | `'0.1.0'` | no | `backend_django/config/settings.py:242`, `backend_django/google_media_backup/api.py:25` |
| `TIME_ZONE` | `str` | `'America/Los_Angeles'` | no | `backend_django/config/settings.py:141` |
| `WAGTAILADMIN_BASE_URL` | `str` | `'http://localhost:8844'` | no | `backend_django/config/settings.py:246` |
| `WAGTAIL_SITE_NAME` | `str` | `'BackDeezUp Media Vault'` | no | `backend_django/config/settings.py:245` |

### Docker Compose (`docker-compose.yml` — read by containers directly, not Django)

| Variable | Default | Required |
|---|---|---|
| `BACKDEEZUP_IMAGE` | `backdeezup:local` | no |
| `BIND_ADDR` | `127.0.0.1` | no |
| `CADDY_TLS_MODE` | `internal` | no |
| `DOMAIN` | `localhost` | no |
| `NGINX_HTTPS_PORT` | `8445` | no |
| `NGINX_HTTP_PORT` | `8844` | no |
| `POSTGRES_DB` | *(none)* | **yes** |
| `POSTGRES_PASSWORD` | *(none)* | **yes** |
| `POSTGRES_USER` | *(none)* | **yes** |
| `REDIS_PASSWORD` | *(none)* | **yes** |
| `WEB_PORT` | `8845` | no |

<!-- END GENERATED CONFIG REFERENCE -->
