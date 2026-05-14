SHELL := /bin/bash
DJ := backend_django/manage.py
.PHONY: up down logs build migrate superuser run docs shell

# Docker targets (prod)
build:     ; docker compose build
up:        ; docker compose up -d
down:      ; docker compose down
logs:      ; docker compose logs -f --tail=100
migrate:   ; docker compose exec web python manage.py migrate
superuser: ; docker compose exec web python manage.