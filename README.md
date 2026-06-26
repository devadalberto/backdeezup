# BackDeezUp

> Self-hosted Google Drive, Gmail & Photos backup. Because cloud storage isn't a backup, it's a subscription to anxiety.

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Django](https://img.shields.io/badge/django-6.0%2B-green)](https://www.djangoproject.com/)
[![Celery](https://img.shields.io/badge/celery-5.x-brightgreen)](https://docs.celeryq.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue)](https://devadalberto.github.io/backdeezup)

---

## TL;DR (you know what you're doing)

```bash
git clone git@github.com:devadalberto/backdeezup.git && cd backdeezup
cp .env.sample .env          # fill in the blanks, you know the drill
make gen-certs               # self-signed TLS, trust it yourself
make build && make up && make migrate && make superuser
make auth                    # OAuth dance — open URL, paste redirect back
make seed-rules              # 15 cleanup rules, all disabled, review before enabling
make gmail-discover          # finds all your email IDs
make gmail-loop LIMIT=500    # downloads everything, go make coffee
# https://localhost:8445 — it's alive
```

That's it. Everything else runs on schedule via Celery. You're done. Go touch grass.

> **New to Docker/Django/OAuth/certificates?** → [Read the full docs](https://devadalberto.github.io/backdeezup) — they won't judge you.

---

## What it does

- **Backs up** Gmail (`.eml` files), Google Drive (media + documents), Google Photos — all locally, all yours
- **Cleans up** Gmail with rule-based automation (dry-run first, never surprises you)
- **Protects** family contacts — they're always starred, labeled, never touched by cleanup rules
- **Imports** everything into a Wagtail vault — browse, triage, watch videos, read PDFs
- **Runs forever** — Celery Beat handles daily sync, cleanup, reconciliation. No babysitting.

## Stack

6 Docker containers. PostgreSQL 16. Redis. Celery. Django + Ninja API. Wagtail CMS. Nginx + TLS.

```
nginx → gunicorn/Django → PostgreSQL
                        → Redis → Celery worker
                                → Celery Beat (scheduler)
```

## Make targets

```bash
make help              # full list
make preflight         # always run this first
make redeploy          # git pull + rebuild + migrate (upgrades)
make gmail-loop        # download new emails
make docs-run          # backup Drive documents
make photos-run        # backup Google Photos
make cleanup-run       # execute cleanup rules (dry-run first with cleanup-dry)
make import-media      # import backups into Wagtail vault
make celery-status     # check workers
```

## Key URLs

| URL | What |
|---|---|
| `https://localhost:8445` | Main (TLS) |
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

## License

MIT — do whatever you want, just don't blame me when Google changes their API again.
