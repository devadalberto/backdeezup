# BackDeezUp

**Self-hosted backup for Google Drive, Gmail, and Google Photos.**

!!! tip "Already know what you're doing?"
    Skip straight to the [Quick Start](quickstart.md) or just read the `README.md` in the repo — it's deliberately sarcastic and very short.

---

## Why does this exist?

Because your Google account is not a backup. It's a single point of failure with a monthly fee attached. When Google locks your account, gets hacked, or changes their terms, your photos, emails, and documents are gone.

BackDeezUp downloads everything to a server you control, organizes it, and gives you a web UI to browse it. It also runs cleanup rules on your Gmail (with dry-run safety) so you stop paying for storage you don't need.

---

## What gets backed up

| Source | What | Where |
|--------|------|-------|
| Gmail | Every email as `.eml` (full RFC822) | `media/gmail/<account>/<year>/<month>/` |
| Google Drive | Images, videos, PDFs, Office docs, Google Docs exported as PDF | `media/` |
| Google Photos | All photos and videos via Drive API | `media/image/` and `media/video/` |

Everything is stored on disk in your Docker volume. The database tracks state (downloaded, verified, deleted, etc.) but never replaces the actual files.

---

## How it works

```
Your Google Account
        │
        ▼ (OAuth — you authenticate once)
   BackDeezUp
        │
        ├── Discovers new emails/files
        ├── Downloads them locally
        ├── Verifies integrity (SHA-256)
        ├── Imports to Wagtail vault (browse in browser)
        └── Runs cleanup rules (optional — always dry-run first)
```

Celery Beat runs all of this on a schedule. After the first setup you shouldn't need to touch it.

---

## Before you start

You need:

- A Linux server (or WSL2 on Windows) with Docker + Docker Compose installed
- A Google Cloud project with OAuth credentials (Desktop app type — **not** Web)
- About 30 minutes the first time

You do **not** need:

- Python installed locally (everything runs in Docker)
- Knowledge of Django, Celery, or PostgreSQL
- A public domain or SSL certificate from a CA (self-signed works for home use)

---

## Documentation sections

- **[Quick Start](quickstart.md)** — Clone → configure → start → authenticate
- **[Operations Manual](operations.md)** — Day-to-day: run backups, cleanup rules, check progress
- **[Configuration Reference](configuration.md)** — Every `.env` variable explained
- **[Authentication](authentication.md)** — Google OAuth setup step by step
- **[Architecture](architecture.md)** — How the 6 containers connect, state machines, data flow
- **[API Reference](api.md)** — All REST endpoints and schemas

---

## Quick orientation

Once running, your main URLs:

| URL | What you'll find |
|-----|-----------------|
| `https://localhost:8445` | Landing page with live stats |
| `/admin/gmail/dashboard/` | Gmail backup progress |
| `/admin/gmail/ops/` | Run cleanup rules, empty Gmail trash |
| `/vault/gallery/` | Browse backed-up photos and videos |
| `/documents/<id>/` | Open a document inline |
| `/cms/` | Wagtail CMS |

---

## FAQ

**Will it delete anything from my Google account without asking?**
No. Cleanup rules default to dry-run. Nothing is deleted unless you explicitly execute after reviewing results.

**What happens if I lose the server?**
Back up the Docker `media/` volume and the PostgreSQL data directory. If you lose the DB but keep the files, a re-run will re-discover and re-verify everything.

**Does it work with multiple Google accounts?**
The infrastructure supports it (per-account token files). Multi-account onboarding UI is planned.

**Can I use it with Outlook or Yahoo?**
Not yet — IMAP support is on the roadmap (Phases 16-21 in `docs/ai-dev/GOALS.md`).

**Is my data sent anywhere?**
No. Only to Google's APIs to download your own data, and optionally Sentry if you configure `SENTRY_DSN`.
