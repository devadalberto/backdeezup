# Dev Quickstart

The README used to be this terse. It moved here (Phase 45) so the README itself
could walk through the actual setup wizard and every user task step by step — this
page is what's left for anyone who already knows Docker/Django/OAuth and just wants
the command list, no explanation.

```bash
git clone git@github.com:devadalberto/backdeezup.git && cd backdeezup
cp .env.sample .env          # fill in the blanks, you know the drill
make gen-certs                # self-signed TLS, trust it yourself
make build && make up && make migrate && make superuser
make auth                    # OAuth dance — open URL, paste redirect back
make seed-rules               # 15 cleanup rules, all disabled, review before enabling
make gmail-discover           # finds all your email IDs
make gmail-loop LIMIT=500     # downloads everything, go make coffee
# https://localhost:8445 — it's alive
```

Everything else that runs on a schedule (Gmail incremental sync, protected senders,
cleanup rules) runs via Celery Beat automatically from here. Drive documents and
Google Photos are **not** on a schedule yet — run `make docs-run` / `make
photos-run` yourself (or use the dashboard's action buttons), or see the main
README's "First backup" and "Schedules" sections.

## Make targets

```bash
make help              # full list
make preflight         # always run this first
make compose-check     # validate docker-compose.yml
make redeploy          # git pull + rebuild + migrate (upgrades)
make fix-perms          # one-time volume chown when upgrading to the non-root image
make gmail-loop        # download new emails
make docs-run          # backup Drive documents
make photos-run        # backup Google Photos
make cleanup-run       # execute cleanup rules (dry-run first with cleanup-dry)
make import-media      # import backups into Wagtail vault
make db-backup         # pg_dump the database
make celery-status     # check workers
```

## Key URLs

| URL | What |
|---|---|
| `https://localhost:8445` | Main (TLS) |
| `/dashboard/` | Unified status + action buttons |
| `/dashboard/verification/` | Verification report |
| `/health/` | System health page |
| `/admin/gmail/dashboard/` | Gmail backup progress |
| `/admin/gmail/ops/` | Run cleanup rules, empty trash |
| `/vault/gallery/` | Browse photos/videos |
| `/documents/<id>/` | Read documents inline |
| `/cms/` | Wagtail CMS |
| `/admin/django_celery_beat/` | Edit schedules |

## Troubleshooting

| Problem | Fix |
|---|---|
| Stack dead after reboot | `make up` |
| Gmail 403 | `rm secrets/google_token.json && make auth` |
| CSRF 403 on login | Add `https://your-host:port` to `CSRF_TRUSTED_ORIGINS` in `.env`, then `make up` |
| Progress bar stuck at "Loading..." | Hard refresh (Ctrl+Shift+R) |
| Celery not running | `docker compose restart celery celerybeat` |
| `docker compose restart` didn't pick up `.env` | Use `make up`, not `restart` |
