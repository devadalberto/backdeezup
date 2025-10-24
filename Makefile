SHELL := /bin/bash
DJ := backend_django/manage.py
.PHONY: up down logs build migrate superuser run docs
build: ; docker compose build
up: ; docker compose up -d
down: ; docker compose down
logs: ; docker compose logs -f --tail=100
migrate: ; python $(DJ) migrate
superuser: ; python $(DJ) createsuperuser
run: ; python $(DJ) runserver 0.0.0.0:8844
docs: ; mkdocs serve -a 0.0.0.0:8001
