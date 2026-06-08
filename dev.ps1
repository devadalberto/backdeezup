# Development helper script for backdeezup
param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

$ManagePy = "backend_django/manage.py"

switch ($Command) {
    "dev" {
        Write-Host "Starting Django dev server on 0.0.0.0:8844..."
        uv run python $ManagePy runserver 0.0.0.0:8844
    }
    "migrate" {
        Write-Host "Running migrations..."
        uv run python $ManagePy migrate
    }
    "makemigrations" {
        Write-Host "Creating migrations..."
        uv run python $ManagePy makemigrations
    }
    "superuser" {
        Write-Host "Creating superuser..."
        uv run python $ManagePy createsuperuser
    }
    "shell" {
        Write-Host "Starting Django shell..."
        uv run python $ManagePy shell
    }
    "test" {
        Write-Host "Running tests..."
        uv run python $ManagePy test
    }
    "docs" {
        Write-Host "Starting documentation server on 0.0.0.0:8001..."
        uv run mkdocs serve -a 0.0.0.0:8001
    }
    "sync" {
        Write-Host "Syncing dependencies with uv..."
        uv sync
    }
    "add" {
        if ($args.Count -eq 0) {
            Write-Host "Usage: .\dev.ps1 add <package-name>"
            exit 1
        }
        Write-Host "Adding package: $($args -join ' ')"
        uv add $args
    }
    "help" {
        Write-Host @"
Backdeezup Development Helper

Usage: .\dev.ps1 <command>

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
  .\dev.ps1 dev
  .\dev.ps1 migrate
  .\dev.ps1 add django-extensions
"@
    }
    default {
        Write-Host "Unknown command: $Command"
        Write-Host "Run '.\dev.ps1 help' for available commands"
        exit 1
    }
}
