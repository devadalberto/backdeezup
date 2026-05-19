SHELL := /bin/bash
DJ    := backend_django/manage.py

.PHONY: help \
        preflight \
        build up down restart logs ps \
        migrate superuser shell check fix-user-migration gmail-empty-trash gmail-empty-trash-dry \
        gen-certs \
        auth \
        deploy redeploy celery-logs celery-status celery-purge \
        run docs \
        discover discover-files discover-photos \
        gmail-discover gmail-incremental gmail-download gmail-verify gmail-run gmail-loop gmail-progress \
        pipeline pipeline-gmail pipeline-all \
        progress \
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
	@echo "    make fix-user-migration Apply accounts 0002 migration"
	@echo "    make gmail-empty-trash-dry  Show Gmail trash count (dry run)"
	@echo "    make gmail-empty-trash      Permanently delete Gmail trash"
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
	@echo "  Gmail pipeline (uses management command, no HTTP auth needed)"
	@echo "    make gmail-discover     Full Gmail snapshot discovery (max 50 pages)"
	@echo "    make gmail-download     Download .eml files (LIMIT=$(LIMIT))"
	@echo "    make gmail-verify       Verify .eml files on disk (LIMIT=$(LIMIT))"
	@echo "    make gmail-run          Full pass: discover+download+verify (LIMIT=$(LIMIT))"
	@echo "    make gmail-loop         Loop download+verify until queue empty (LIMIT=$(LIMIT))"
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

gen-certs:
	bash scripts/gen-dev-certs.sh

redeploy:
	git pull origin main
	docker compose build
	docker compose down
	docker compose up -d
	docker compose exec web python manage.py migrate

celery-logs:
	docker compose logs -f --tail=100 celery celerybeat

celery-status:
	docker compose exec celery celery -A celery_app inspect active

celery-purge:
	docker compose exec celery celery -A celery_app purge -f

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

seed-rules:
	docker compose exec web python manage.py seed_rules

seed-inbox-rules:
	docker compose exec web python manage.py seed_inbox_rules

vault-setup:
	docker compose exec web python manage.py vault_setup

import-media:
	docker compose exec web python manage.py import_media $(ARGS)

import-media-dry:
	docker compose exec web python manage.py import_media --dry-run

cleanup-dry:
	docker compose exec web python manage.py run_cleanup --dry-run $(ARGS)

cleanup-run:
	docker compose exec web python manage.py run_cleanup --execute --confirm $(ARGS)

gmail-empty-trash-dry:
	docker compose exec web python manage.py empty_gmail_trash

gmail-empty-trash:
	docker compose exec web python manage.py empty_gmail_trash --confirm

seed-smart-rules:
	docker compose exec web python manage.py seed_smart_rules

superuser:
	docker compose exec web python manage.py createsuperuser

shell:
	docker compose exec web python manage.py shell

check:
	docker compose exec web python manage.py check

fix-user-migration:
	docker compose exec web python manage.py migrate accounts

# ── Drive / Photos pipeline ───────────────────────────────────────────────────
HOST  ?= http://localhost:8844
LIMIT ?= 100

discover:
	docker compose exec web python manage.py drive_pipeline discover --max-pages 20 --page-size 200

discover-files:
	docker compose exec web python manage.py drive_pipeline discover-files --max-pages 20 --page-size 200

discover-photos:
	docker compose exec web python manage.py drive_pipeline discover-photos --max-pages 20 --page-size 200 || true

pipeline:
	uv run python run_pipeline.py drive --limit $(LIMIT)

pipeline-gmail:
	uv run python run_pipeline.py gmail --limit $(LIMIT)

pipeline-all:
	uv run python run_pipeline.py all --limit $(LIMIT)

progress:
	curl -s "$(HOST)/api/progress" | python3 -m json.tool || true

sync-download:
	curl -s -X POST "$(HOST)/api/sync/download?limit=$(LIMIT)" | python3 -m json.tool || true

sync-run:
	@bash -c '\
	HOST=$(HOST); LIMIT=$(LIMIT); \
	show_progress() { \
		p=$$(curl -s "$$HOST/api/progress" 2>/dev/null); \
		pct=$$(echo "$$p" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[\"pct\"])" 2>/dev/null || echo 0); \
		done_n=$$(echo "$$p" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[\"done\"])" 2>/dev/null || echo 0); \
		total=$$(echo "$$p" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[\"total\"])" 2>/dev/null || echo 0); \
		filled=$$(python3 -c "print(int(float(\"$$pct\") / 5))" 2>/dev/null || echo 0); \
		bar=$$(python3 -c "f=$$filled; print(\"=\"*f + \"-\"*(20-f))" 2>/dev/null); \
		echo "  [$$bar] $$pct% ($$done_n/$$total verified)"; \
	}; \
	echo "Running full pipeline: download -> import -> verify (single pass)"; \
	dl=0; imp=0; ver=0; \
	result=$$(curl -s -X POST "$$HOST/api/sync/download?limit=$$LIMIT"); \
	dl=$$(echo "$$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get(\"downloaded\",0))" 2>/dev/null || echo 0); \
	echo "  download: $$dl"; show_progress; \
	result=$$(curl -s -X POST "$$HOST/api/sync/import?limit=$$LIMIT"); \
	imp=$$(echo "$$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get(\"imported\",0))" 2>/dev/null || echo 0); \
	echo "  import: $$imp"; show_progress; \
	result=$$(curl -s -X POST "$$HOST/api/sync/verify?limit=$$LIMIT"); \
	ver=$$(echo "$$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get(\"verified\",0))" 2>/dev/null || echo 0); \
	echo "  verify: $$ver"; show_progress; \
	echo "Pass done (dl=$$dl imp=$$imp ver=$$ver). Run again or use: while make sync-run | grep -q \"dl=0 imp=0 ver=0\"; do break; done"; \
	[ "$$dl" -gt 0 ] || [ "$$imp" -gt 0 ] || [ "$$ver" -gt 0 ]'

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
	docker compose exec web python manage.py gmail_pipeline discover --max-pages 50 --page-size 500

gmail-incremental:
	curl -s -X POST "$(HOST)/api/gmail/sync/incremental" | python3 -m json.tool || true

WORKERS ?= 10

gmail-download:
	docker compose exec web python manage.py gmail_pipeline download --limit $(LIMIT) --workers $(WORKERS)

gmail-verify:
	docker compose exec web python manage.py gmail_pipeline verify --limit $(LIMIT)

gmail-extract-attachments:
	docker compose exec web python manage.py extract_attachments --workers 8

gmail-extract-attachments-dry:
	docker compose exec web python manage.py extract_attachments --dry-run

gmail-extract-all:
	docker compose exec web python manage.py extract_attachments --all --workers 8

gmail-loop:
	@echo "Looping download+verify until DISCOVERED queue is empty (Ctrl+C to stop)..."
	@while true; do \
		docker compose exec web python manage.py gmail_pipeline download --limit $(LIMIT); \
		docker compose exec web python manage.py gmail_pipeline verify --limit $(LIMIT); \
		remaining=$$(docker compose exec -T web python manage.py shell --verbosity 0 -c \
			"from google_gmail_backup.models import GmailMessage; print(GmailMessage.objects.filter(state='DISCOVERED').count())" 2>/dev/null | tail -1 | tr -d '\r'); \
		echo "=== DISCOVERED remaining: $$remaining ==="; \
		[ "$$remaining" = "0" ] && { echo "Queue empty — done."; break; }; \
	done

gmail-progress:
	curl -s "$(HOST)/api/gmail/progress" | python3 -m json.tool || true

gmail-run:
	docker compose exec web python manage.py gmail_pipeline all --limit $(LIMIT)

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
