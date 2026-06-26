# Quick Start

Everything runs in Docker. You do **not** need Python, uv, or anything else installed locally.

---

## Prerequisites

- Docker + Docker Compose (that's it)
- A Google Cloud project with a Desktop App OAuth client (type `installed`, not `web`)

---

## 1. Clone and configure

```bash
git clone https://github.com/devadalberto/backdeezup.git
cd backdeezup
cp .env.sample .env
```

Open `.env` and fill in:

```env
# Generate with: python3 -c "import secrets; print(secrets.token_urlsafe(50))"
DJANGO_SECRET_KEY=<long random string>

# Generate with: python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
GOOGLE_ENCRYPTION_KEY=<44-char Fernet key>
```

Everything else can stay as the defaults for now.

!!! tip "Don't have Python to generate those keys?"
    Run it inside the container after you build: `docker compose run --rm web python3 -c "import secrets; print(secrets.token_urlsafe(50))"`

---

## 2. Place Google credentials

Download your Desktop App OAuth JSON from Google Cloud Console and copy it:

```bash
mkdir -p secrets
cp ~/Downloads/client_secret_*.json secrets/google_client.json
```

The file must be type `installed` (Desktop App). Verify with:

```bash
python3 -c "import json; d=json.load(open('secrets/google_client.json')); print(list(d.keys())[0])"
# Must print: installed
```

---

## 3. Generate TLS certificates

```bash
make gen-certs
```

This creates `nginx/certs/server.crt` and `server.key` for local HTTPS. Trust the cert in your browser once to stop the warning.

---

## 4. Pre-flight check

```bash
make preflight
```

Must show all OK. Fix anything it reports before continuing.

---

## 5. Build and start

```bash
make build && make up && make migrate && make superuser
```

All 6 containers start. `make superuser` prompts for your admin username/password.

---

## 6. Authenticate with Google

```bash
make auth
```

This prints a URL. Open it in your browser, approve access, then copy the full redirect URL (it'll look like `http://localhost/?code=...`) and paste it back.

---

## 7. Seed rules and run initial backup

```bash
make seed-rules        # loads 15 cleanup rules (all disabled by default — review before enabling)
make gmail-discover    # finds all your Gmail message IDs
make gmail-loop        # downloads emails (runs until queue is empty)
make docs-run          # discovers and downloads Google Drive documents
make photos-run        # discovers and downloads Google Photos
```

---

## 8. Browse

Open **https://localhost:8445** (or your server's IP + port 8445).

| URL | What |
|-----|------|
| `/admin/gmail/dashboard/` | Gmail backup progress |
| `/admin/gmail/ops/` | Cleanup rules + empty trash |
| `/vault/gallery/` | Photos and videos |
| `/documents/<id>/` | Documents |
| `/cms/` | Wagtail CMS |

---

!!! note "Celery Beat takes over from here"
    After the initial run, Celery Beat handles daily incremental sync, reconciliation, and cleanup automatically. You don't need to run any commands manually again.
