# Deployment

Full production deployment runbook — tested on Debian 13 WSL2 on Windows Server 2025.

---

## Prerequisites

- Docker Engine installed (see [Installation](installation.md))
- `git` and `ssh` configured for GitHub access
- Google OAuth credentials (`google_client.json`)
- Access to the repo: `git@github.com:devadalberto/backdeezup.git`

---

## 1. Clone the repo

```bash
git clone git@github.com:devadalberto/backdeezup.git
cd backdeezup
```

---

## 2. Create `.env`

```bash
cp .env.sample .env
vim .env
```

Fill in every `CHANGE_ME` value. Minimum required:

```env
DJANGO_SECRET_KEY=<generate below>
DEBUG=False
ALLOWED_HOSTS=<your-server-ip>,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://<your-server-ip>:8844,http://localhost:8844

POSTGRES_USER=backdeezup
POSTGRES_PASSWORD=<your-db-password>
POSTGRES_DB=backdeezup
DATABASE_URL=postgres://backdeezup:<your-db-password>@db:5432/backdeezup

GOOGLE_ENCRYPTION_KEY=<generate below>
GOOGLE_CLIENT_SECRETS=secrets/google_client.json
GOOGLE_TOKEN_FILE=secrets/google_token.json
```

Generate values:

```bash
# Django secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Fernet encryption key (stdlib only — no dependencies needed)
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

---

## 3. Place Google OAuth credentials

```bash
mkdir -p secrets
cp /path/to/client_secret_*.json secrets/google_client.json
```

!!! warning
    `secrets/` is git-ignored and never committed. Keep backups of both `google_client.json` and `GOOGLE_ENCRYPTION_KEY`.

---

## 4. Build the image

```bash
docker compose build
```

This pulls Python 3.12-slim, installs all dependencies via uv, and copies the app. Takes ~90 seconds on first build, ~5 seconds after that (cached layers).

---

## 5. Start all services

```bash
docker compose up -d
```

Starts: **postgres** → waits for healthcheck → **web** (gunicorn) → **nginx** → **redis**

Verify all are running:

```bash
docker compose ps
```

Expected output — all 4 containers `Up`:

```
NAME                 IMAGE                 STATUS
backdeezup-db-1      postgres:16           Up (healthy)
backdeezup-nginx-1   nginx:stable-alpine   Up
backdeezup-redis-1   redis:7-alpine        Up
backdeezup-web-1     backdeezup-web        Up
```

Check web logs:

```bash
docker compose logs web --tail=20
```

Should end with:
```
[entrypoint] Collecting static files...
130 static files copied to '/app/staticfiles'
[entrypoint] Starting gunicorn...
Listening at: http://0.0.0.0:8000
```

---

## 6. Run migrations

```bash
docker compose exec web python manage.py migrate
```

---

## 7. Create superuser

```bash
docker compose exec web python manage.py createsuperuser
```

---

## 8. Authenticate with Google

Open the Swagger UI and call `POST /auth/connect`:

```
http://<your-server-ip>:8844/api/docs
```

A browser OAuth flow will open. After approving, the encrypted token is saved to `secrets/google_token.json` inside the container (mounted from `./secrets/`).

---

## 9. Run the backup pipeline

Work through these endpoints in order. Use the Swagger UI at `/api/docs` or curl:

```bash
# Discover media in Google Photos
curl -X POST http://localhost:8844/api/sync/discover-photos

# Discover files in Google Drive
curl -X POST "http://localhost:8844/api/sync/discover-files?page_size=200&max_pages=10"

# Download discovered assets to local disk
curl -X POST "http://localhost:8844/api/sync/download?limit=20"

# Import: SHA-256 hash + copy to media/
curl -X POST "http://localhost:8844/api/sync/import?limit=20"

# Verify both proofs (file on disk + DB record)
curl -X POST "http://localhost:8844/api/sync/verify?limit=50"

# Queue verified assets for deletion from Drive
curl -X POST "http://localhost:8844/api/sync/mark-delete?limit=100"

# Execute deletion (default: trash mode, recoverable 30 days)
curl -X POST "http://localhost:8844/api/sync/commit-delete?limit=50"
```

!!! tip "Use the Ops Console"
    `/admin/ops/` provides a one-click UI for all pipeline steps with live output.

!!! danger "Deletion is real"
    `commit-delete` moves files to Google Drive trash by default (`DRIVE_DELETE_MODE=trash`).
    Set `DRIVE_DELETE_MODE=hard` only if you want permanent deletion.

---

## 10. Monitor progress

```bash
# Admin dashboard with asset counts and run history
http://<your-server-ip>:8844/admin/reports/

# Django Admin for browsing assets
http://<your-server-ip>:8844/admin/

# API docs
http://<your-server-ip>:8844/api/docs
```

---

## Ongoing operations

```bash
# Tail all logs
docker compose logs -f --tail=100

# Tail web only
docker compose logs -f web

# Restart after .env change
docker compose down && docker compose up -d

# Rebuild after code change
git pull origin main && docker compose build && docker compose down && docker compose up -d

# Apply new migrations after code change
docker compose exec web python manage.py migrate

# Django shell
docker compose exec web python manage.py shell

# Stop everything (keeps volumes)
docker compose down

# Wipe everything including database (DESTRUCTIVE)
docker compose down -v
```

---

## WSL2 external access (Windows Server only)

If running inside WSL2 on Windows, the app is only accessible on `localhost` by default. To expose it on the Windows VM's IP:

```powershell
# Run in PowerShell (as Administrator) — replace WSL_IP with output of: wsl hostname -I
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8844 connectaddress=<WSL_IP> connectport=8844
New-NetFirewallRule -DisplayName "BackDeezUp 8844" -Direction Inbound -Protocol TCP -LocalPort 8844 -Action Allow
```

Get the WSL IP:
```bash
wsl -d Debian -- hostname -I
```

!!! warning "WSL IP changes on restart"
    Re-run the `netsh` command after each WSL restart. To automate, add it to a PowerShell startup script.

---

## Production checklist

- [ ] `DEBUG=False` in `.env`
- [ ] `DJANGO_SECRET_KEY` is a long random string
- [ ] `ALLOWED_HOSTS` includes your server IP/hostname
- [ ] `CSRF_TRUSTED_ORIGINS` includes your server URL with port
- [ ] `POSTGRES_PASSWORD` is not the sample value
- [ ] `GOOGLE_ENCRYPTION_KEY` is backed up securely
- [ ] `secrets/google_client.json` is in place
- [ ] All 4 containers are `Up` (`docker compose ps`)
- [ ] Migrations applied (`docker compose exec web python manage.py migrate`)
- [ ] Superuser created
- [ ] OAuth completed (`/auth/connect`)
- [ ] Static files loading (check `/admin/` — should have styles)
