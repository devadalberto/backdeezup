# Deployment

---

## Docker Compose (recommended)

The included `docker-compose.yml` runs the full stack:

- **web** — Gunicorn serving the Django application
- **nginx** — Reverse proxy on port 8844
- **postgres** — PostgreSQL 16 database
- **redis** — Reserved for future async task support

### 1. Configure environment

```bash
cp .env.sample .env
```

Set at minimum:

```env
DJANGO_SECRET_KEY=<long-random-string>
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,localhost
DATABASE_URL=postgres://backdeezup:password@postgres:5432/backdeezup
GOOGLE_ENCRYPTION_KEY=<44-char-fernet-key>
DRIVE_DELETE_MODE=trash
```

### 2. Build and start

```bash
docker compose build
docker compose up -d
```

### 3. Initialise the database

```bash
docker compose exec web python backend_django/manage.py migrate
docker compose exec web python backend_django/manage.py createsuperuser
```

### 4. Collect static files

```bash
docker compose exec web python backend_django/manage.py collectstatic --no-input
```

### 5. Verify

Visit **http://localhost:8844/api/docs** — you should see the Swagger UI.

---

## Docker Compose topology

```mermaid
flowchart TD
    Browser -->|port 8844| Nginx
    Nginx -->|proxy_pass 8000| Gunicorn
    Gunicorn --> Django
    Django --> Postgres
    Django --> FS2[media/ volume]
    Django -->|OAuth| Google

    subgraph Docker Compose
        Nginx
        Gunicorn
        Django
        Postgres
        Redis[(Redis)]
    end
```

---

## Useful commands

```bash
# Tail logs
docker compose logs -f --tail=100

# Stop all containers
docker compose down

# Rebuild after code changes
docker compose build web && docker compose up -d web

# Django shell inside container
docker compose exec web python backend_django/manage.py shell
```

---

## Volumes

| Volume | Purpose |
|---|---|
| `postgres_data` | PostgreSQL data directory — persisted across restarts |
| `media_data` | Imported media files (`MEDIA_ROOT`) |
| `secrets/` | OAuth credentials — mount as a bind volume, not committed to git |

---

## Production checklist

- [ ] `DEBUG=False` in `.env`
- [ ] `DJANGO_SECRET_KEY` set to a long random string
- [ ] `ALLOWED_HOSTS` set to your domain(s)
- [ ] `DATABASE_URL` pointing to a real Postgres instance
- [ ] `GOOGLE_ENCRYPTION_KEY` backed up securely (loss = re-auth required)
- [ ] `DRIVE_DELETE_MODE=trash` unless you intentionally want hard deletes
- [ ] `secrets/` directory not committed to version control
- [ ] Static files collected (`collectstatic`)
- [ ] Nginx configured with TLS for public-facing deployments

---

## Local development with uv

For day-to-day development without Docker:

```bash
uv sync
./dev.sh migrate
./dev.sh dev     # starts on http://localhost:8844
```

See [Quick Start](quickstart.md) for the full walkthrough.
