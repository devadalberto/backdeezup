SHELL := /bin/bash
DJ    := backend_django/manage.py

.PHONY: help \
        build up down restart logs ps \
        migrate superuser shell check \
        deploy redeploy \
        run docs \
        discover discover-files discover-photos \
        gmail-discover gmail-incremental gmail-download gmail-verify \
        sync-download sync-import sync-verify sync-mark-delete sync-commit-delete \
        wsl-proxy

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "BackDeezUp — Makefile reference"
	@echo ""
	@echo "  Docker (production)"
	@echo "    make build              Build Docker image"
	@echo "    make up                 Start all containers (detached)"
	@echo "    make down               Stop all containers"
	@echo "    make restart            down + up"
	@echo "    make redeploy           pull + build + down + up + migrate"
	@echo "    make logs               Tail all logs"
	@echo "    make ps                 Show container status"
	@echo ""
	@echo "  Django"
	@echo "    make migrate            Run database migrations"
	@echo "    make superuser          Create Django superuser"
	@echo "    make shell              Django shell inside container"
	@echo "    make check              Django system check"
	@echo ""
	@echo "  Drive / Photos pipeline"
	@echo "    make discover           Discover Drive media (images/videos)"
	@echo "    make discover-files     Discover Drive documents (PDF, Office, etc.)"
	@echo "    make discover-photos    Discover Google Photos"
	@echo "    make sync-download      Download DISCOVERED assets (limit=20)"
	@echo "    make sync-import        Import + SHA-256 hash (limit=20)"
	@echo "    make sync-verify        Verify both proofs (limit=50)"
	@echo "    make sync-mark-delete   Queue VERIFIED for deletion (limit=100)"
	@echo "    make sync-commit-delete Execute Drive deletion (trash mode)"
	@echo ""
	@echo "  Gmail pipeline"
	@echo "    make gmail-discover     Full Gmail snapshot discovery"
	@echo "    make gmail-incremental  Incremental sync via historyId"
	@echo "    make gmail-download     Download .eml files (limit=20)"
	@echo "    make gmail-verify       Verify .eml files on disk (limit=50)"
	@echo ""
	@echo "  Local dev (uv)"
	@echo "    make run                Django dev server on :8844"
	@echo "    make docs               MkDocs dev server on :8001"
	@echo ""
	@echo "  WSL2 / Windows"
	@echo "    make wsl-proxy          Forward port 8844 from Windows to WSL2"
	@echo ""

# ── Docker ────────────────────────────────────────────────────────────────────
build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart: down up

redeploy:
	git pull origin main
	docker compose build
	docker compose down
	docker compose up -d
	docker compose exec web python manage.py migrate

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

# ── Django ────────────────────────────────────────────────────────────────────
migrate:
	docker compose exec web python manage.py migrate

superuser:
	docker compose exec web python manage.py createsuperuser

shell:
	docker compose exec web python manage.py shell

check:
	docker compose exec web python manage.py check

# ── Drive / Photos pipeline ───────────────────────────────────────────────────
HOST ?= http://localhost:8844

discover:
	curl -s -X POST "$(HOST)/api/sync/discover?page_size=200&max_pages=10" | python3 -m json.tool

discover-files:
	curl -s -X POST "$(HOST)/api/sync/discover-files?page_size=200&max_pages=10" | python3 -m json.tool

discover-photos:
	curl -s -X POST "$(HOST)/api/sync/discover-photos?page_size=200&max_pages=20" | python3 -m json.tool

sync-download:
	curl -s -X POST "$(HOST)/api/sync/download?limit=20" | python3 -m json.tool

sync-import:
	curl -s -X POST "$(HOST)/api/sync/import?limit=20" | python3 -m json.tool

sync-verify:
	curl -s -X POST "$(HOST)/api/sync/verify?limit=50" | python3 -m json.tool

sync-mark-delete:
	curl -s -X POST "$(HOST)/api/sync/mark-delete?limit=100" | python3 -m json.tool

sync-commit-delete:
	curl -s -X POST "$(HOST)/api/sync/commit-delete?limit=50" | python3 -m json.tool

# ── Gmail pipeline ────────────────────────────────────────────────────────────
gmail-discover:
	curl -s -X POST "$(HOST)/api/gmail/sync/discover?max_pages=10&page_size=500" | python3 -m json.tool

gmail-incremental:
	curl -s -X POST "$(HOST)/api/gmail/sync/incremental" | python3 -m json.tool

gmail-download:
	curl -s -X POST "$(HOST)/api/gmail/sync/download?limit=20" | python3 -m json.tool

gmail-verify:
	curl -s -X POST "$(HOST)/api/gmail/sync/verify?limit=50" | python3 -m json.tool

# ── Local dev ─────────────────────────────────────────────────────────────────
run:
	python $(DJ) runserver 0.0.0.0:8844

docs:
	mkdocs serve -a 0.0.0.0:8001

# ── WSL2 / Windows (run in PowerShell as admin) ───────────────────────────────
wsl-proxy:
	@WSL_IP=$$(wsl hostname -I | awk '{print $$1}'); \
	echo "WSL IP: $$WSL_IP"; \
	powershell.exe -Command "netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8844 connectaddress=$$WSL_IP connectport=8844"
