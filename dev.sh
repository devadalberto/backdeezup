#!/bin/bash
# Development helper script for backdeezup

MANAGE_PY="backend_django/manage.py"

case "${1:-help}" in
    dev)
        echo "Starting Django dev server on 0.0.0.0:8844..."
        uv run python $MANAGE_PY runserver 0.0.0.0:8844
        ;;
    migrate)
        echo "Running migrations..."
        uv run python $MANAGE_PY migrate
        ;;
    makemigrations)
        echo "Creating migrations..."
        uv run python $MANAGE_PY makemigrations
        ;;
    superuser)
        echo "Creating superuser..."
        uv run python $MANAGE_PY createsuperuser
        ;;
    shell)
        echo "Starting Django shell..."
        uv run python $MANAGE_PY shell
        ;;
    test)
        echo "Running tests..."
        uv run python $MANAGE_PY test
        ;;
    docs)
        echo "Starting documentation server on 0.0.0.0:8001..."
        uv run mkdocs serve -a 0.0.0.0:8001
        ;;
    sync)
        echo "Syncing dependencies with uv..."
        uv sync
        ;;
    add)
        shift
        if [ $# -eq 0 ]; then
            echo "Usage: ./dev.sh add <package-name>"
            exit 1
        fi
        echo "Adding package: $*"
        uv add "$@"
        ;;
    help)
        cat <<EOF
Backdeezup Development Helper

Usage: ./dev.sh <command>

Commands:
  dev              - Run Django dev server (0.0.0.0:8844)
  migrate          - Run database migrations
  makemigrations   - Create new migrations
  superuser        - Create Django superuser
  shell            - Start Django shell
  test             - Run tests
  docs             - Start documentation server (0.0.0.0:8001)
  sync             - Sync dependencies with uv
  add <package>    - Add a new package with uv
  help             - Show this help message

Examples:
  ./dev.sh dev
  ./dev.sh migrate
  ./dev.sh add django-extensions
EOF
        ;;
    *)
        echo "Unknown command: $1"
        echo "Run './dev.sh help' for available commands"
        exit 1
        ;;
esac
