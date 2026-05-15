SHELL := /bin/bash
DJ    := backend_django/manage.py

.PHONY: help \
        preflight \
        build up down restart logs ps \
        migrate superuser shell check \
        auth \
        deploy redeploy \
        run docs \
        discover discover-files discover-photos \
        gmail-discover gmail-incremental gmail-download gmail-verify \
        sync-download sync-import sync-verify sync-mark-delete sync-commit-delete sync-run \
        lint test test-full \
        wsl-proxy

# ── Pre-flight checks ─────────────────────────────────────────────────────────
preflight:
	@echo "Running pre-flight checks..."
	@command -v docker >/dev/null 2>&1 || { echo "FAIL: docker not found"; exit 1; }
	@docker info >/dev/null 2>&1 || { echo "FAIL: docker daemon not running — run: sudo service docker start"; exit 1; }
	@test -f .env || { echo "FAIL: .env not found — run: cp .env.sample .env and fill in values"; exit 1; }
	@test -f secrets/google_client.json || { echo "FAIL: secrets/google_client.json missing"; exit 1; }
	@python3 -c "import json; d=json.load(open('secrets/google_client.json')); t=list(d.keys())[0]; exit(0 if t=='installed' else 1)" 2>/dev/null || { echo "FAIL: google_client.json is type 'web' — must be Desktop app (installed). Download Desktop app credentials from Google Cloud Console."; exit 1; }
	@grep -q "CHANGE_ME" .env 2>/dev/null && { echo "FAIL: .env still has CHANGE_ME placeholders — fill in all values"; exit 1; } || true
	@grep -q "GOOGLE_ENCRYPTION_KEY=" .env || { echo "FAIL: GOOGLE_ENCRYPTION_KEY not set in .env"; exit 1; }
	@echo "OK: docker running"
	@echo "OK: .env present"
	@echo "OK: google_client.json is Desktop app (installed) type"
	@echo "OK: no CHANGE_ME placeholders"
	@echo "All pre-flight checks passed. Run: make build && make up && make migrate && make auth"

# ── Default ───────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "BackDeezUp — Makefile reference"
	@echo ""
	@echo "  Pre-flight"
	@echo "    make preflight          Check all prerequisites before deploying"
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
	@echo "    make auth               Google OAuth — prints URL, paste code back (headless)"
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
	@echo "    make sync-run           Loop download→import→verify until done (LIMIT=100)"
	@echo "    make sync-mark-delete   Queue VERIFIED for deletion (LIMIT=100)"
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
auth:
	@echo "Starting OAuth on port 18444..."
	@echo "Add http://localhost:18444/ to your Google OAuth client redirect URIs first."
	@echo "Then open the printed URL in your browser."
	docker compose exec -it web python manage.py shell -c "from google_media_backup.services_google import start_oauth_local; start_oauth_local()"

migrate:
	docker compose exec web python manage.py migrate

superuser:
	docker compose exec web python manage.py createsuperuser

shell:
	docker compose exec web python manage.py shell

check:
	docker compose exec web python manage.py check

# ── Drive / Photos pipeline ───────────────────────────────────────────────────
HOST  ?= http://localhost:8844
LIMIT ?= 100

discover:
	curl -s -X POST "$(HOST)/api/sync/discover?page_size=200&max_pages=10" | python3 -m json.tool || true

discover-files:
	curl -s -X POST "$(HOST)/api/sync/discover-files?page_size=200&max_pages=10" | python3 -m json.tool || true

discover-photos:
	curl -s -X POST "$(HOST)/api/sync/discover-photos?page_size=200&max_pages=20" | python3 -m json.tool || true

sync-download:
	curl -s -X POST "$(HOST)/api/sync/download?limit=$(LIMIT)" | python3 -m json.tool || true

sync-run:
	@echo "Running full pipeline: download → import → verify (loops until done)"
	@while true; do \
		result=$$(curl -s -X POST "$(HOST)/api/sync/download?limit=$(LIMIT)"); \
		echo "download: $$result"; \
		echo "$$result" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('downloaded',0)>0 else 1)" || break; \
	done
	@while true; do \
		result=$$(curl -s -X POST "$(HOST)/api/sync/import?limit=$(LIMIT)"); \
		echo "import: $$result"; \
		echo "$$result" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('imported',0)>0 else 1)" || break; \
	done
	@while true; do \
		result=$$(curl -s -X POST "$(HOST)/api/sync/verify?limit=$(LIMIT)"); \
		echo "verify: $$result"; \
		echo "$$result" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('verified',0)>0 else 1)" || break; \
	done
	@echo "Pipeline complete."

sync-import:
	curl -s -X POST "$(HOST)/api/sync/import?limit=$(LIMIT)" | python3 -m json.tool || true

sync-verify:
	curl -s -X POST "$(HOST)/api/sync/verify?limit=$(LIMIT)" | python3 -m json.tool || true

sync-mark-delete:
	curl -s -X POST "$(HOST)/api/sync/mark-delete?limit=$(LIMIT)" | python3 -m json.tool || true

sync-commit-delete:
	curl -s -X POST "$(HOST)/api/sync/commit-delete?limit=$(LIMIT)" | python3 -m json.tool || true

# ── Gmail pipeline ────────────────────────────────────────────────────────────
gmail-discover:
	curl -s -X POST "$(HOST)/api/gmail/sync/discover?max_pages=10&page_size=50" | python3 -m json.tool || true

gmail-incremental:
	curl -s -X POST "$(HOST)/api/gmail/sync/incremental" | python3 -m json.tool || true

gmail-download:
	curl -s -X POST "$(HOST)/api/gmail/sync/download?limit=$(LIMIT)" | python3 -m json.tool || true

gmail-verify:
	curl -s -X POST "$(HOST)/api/gmail/sync/verify?limit=$(LIMIT)" | python3 -m json.tool || true

# ── Local dev ─────────────────────────────────────────────────────────────────
run:
	python $(DJ) runserver 0.0.0.0:8844

docs:
	mkdocs serve -a 0.0.0.0:8001

lint:
	uv run ruff check backend_django/ --select E,F,W --ignore E501,E701,E702

test:
	DATABASE_URL="" uv run python $(DJ) test google_media_backup google_gmail_backup --verbosity=2

test-full: lint test

# ── WSL2 / Windows (run in PowerShell as admin) ───────────────────────────────
wsl-proxy:
	@WSL_IP=$$(wsl hostname -I | awk '{print $$1}'); \
	echo "WSL IP: $$WSL_IP"; \
	powershell.exe -Command "netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8844 connectaddress=$$WSL_IP connectport=8844"
