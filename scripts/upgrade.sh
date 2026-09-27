#!/usr/bin/env bash
# BackDeezUp upgrade script (Phase 49).
#
#   scripts/upgrade.sh                 # from inside a git checkout or an
#                                       # install.sh-created directory
#   scripts/upgrade.sh --dir PATH      # operate on a different directory
#
# Steps: db-backup (Phase 38) -> pull (git pull for a source checkout, or
# `docker compose pull` for an install.sh-created directory / a source checkout
# with BACKDEEZUP_IMAGE set) -> up -> migrate -> health check -> on failure,
# prints exact rollback instructions (never rolls back automatically).
#
# Every action is printed before it happens. --dry-run makes zero writes and
# runs no docker/git commands. -y/--yes skips confirmations (for automation).
#
# Options:
#   --dir PATH        Directory to operate in (default: .)
#   --image IMAGE     Update BACKDEEZUP_IMAGE in .env to this tag before pulling
#   -y, --yes         Assume "yes" to every confirmation
#   --dry-run         Print the plan; write nothing, run nothing destructive
#   -h, --help        Show this help

set -euo pipefail

DIR="."
NEW_IMAGE=""
ASSUME_YES=0
DRY_RUN=0

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --image) NEW_IMAGE="$2"; shift 2 ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

log()  { echo ">> $*"; }
note() { echo "   $*"; }

confirm() {
  local question="$1"
  if [ "$ASSUME_YES" -eq 1 ]; then return 0; fi
  if [ ! -t 0 ]; then
    echo "Refusing to guess on '$question' with no terminal attached and no --yes. Aborting." >&2
    exit 1
  fi
  read -r -p "$question [y/N] " reply
  case "$reply" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

run() {
  local desc="$1"; shift
  log "$desc"
  if [ "$DRY_RUN" -eq 1 ]; then
    note "[dry-run] would run: $*"
    return 0
  fi
  "$@"
}

cd "$DIR"
DIR="$(pwd)"

if [ ! -f docker-compose.yml ] || [ ! -f .env ]; then
  echo "FAIL: $DIR doesn't look like a BackDeezUp install (no docker-compose.yml / .env)." >&2
  exit 1
fi

IS_GIT_CHECKOUT=0
if [ -d .git ]; then IS_GIT_CHECKOUT=1; fi

CURRENT_IMAGE="$(grep -E '^BACKDEEZUP_IMAGE=' .env | tail -1 | cut -d= -f2- || true)"
PREVIOUS_COMMIT=""
if [ "$IS_GIT_CHECKOUT" -eq 1 ]; then
  PREVIOUS_COMMIT="$(git rev-parse HEAD)"
  if [ -n "$(git status --porcelain)" ]; then
    echo "FAIL: this is a git checkout with uncommitted changes. Commit, stash, or" >&2
    echo "      discard them first -- upgrading over local changes risks losing them." >&2
    exit 1
  fi
fi

log "Target: $DIR"
note "git checkout: $([ "$IS_GIT_CHECKOUT" -eq 1 ] && echo "yes (HEAD=$PREVIOUS_COMMIT)" || echo "no (install.sh-style directory)")"
note "BACKDEEZUP_IMAGE: ${CURRENT_IMAGE:-<unset -- building from source>}"

# ── 1. Backup first (Phase 38) ──────────────────────────────────────────────────
BACKUP_FILE=""
log "Backing up the database (make db-backup, replicated inline)"
if [ "$DRY_RUN" -eq 1 ]; then
  note "[dry-run] would run: docker compose exec -T db pg_dump ... > backups/backdeezup-<timestamp>.dump"
else
  mkdir -p backups
  TS="$(date +%Y%m%d-%H%M%S)"
  BACKUP_FILE="backups/backdeezup-$TS.dump"
  docker compose exec -T db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$BACKUP_FILE"
  note "Backup written to $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
fi

if [ "$DRY_RUN" -eq 0 ]; then
  confirm "Backup done. Pull new code/image and restart the running stack now?" \
    || { echo "Aborted after backup -- nothing else was touched."; exit 1; }
fi

# ── 2. Pull ──────────────────────────────────────────────────────────────────────
if [ -n "$NEW_IMAGE" ]; then
  run "Setting BACKDEEZUP_IMAGE=$NEW_IMAGE in .env" python3 -c "
import re
with open('.env') as f: text = f.read()
pattern = re.compile(r'^#?\s*BACKDEEZUP_IMAGE=.*\$', re.MULTILINE)
text = pattern.sub('BACKDEEZUP_IMAGE=$NEW_IMAGE', text, count=1) if pattern.search(text) else text + '\nBACKDEEZUP_IMAGE=$NEW_IMAGE\n'
with open('.env', 'w') as f: f.write(text)
"
  CURRENT_IMAGE="$NEW_IMAGE"
fi

if [ "$IS_GIT_CHECKOUT" -eq 1 ] && [ -z "$CURRENT_IMAGE" ]; then
  run "Pulling latest code (git pull)" git pull
  run "Rebuilding the image" docker compose build
else
  run "Pulling image ($CURRENT_IMAGE)" docker compose pull
fi

# ── 3. Recreate + migrate ────────────────────────────────────────────────────────
run "Running database migrations" docker compose run --rm web python manage.py migrate
run "Starting the updated stack" docker compose up -d

if [ "$DRY_RUN" -eq 1 ]; then
  log "Dry run complete -- nothing was written, nothing was pulled or started."
  exit 0
fi

# ── 4. Health check ──────────────────────────────────────────────────────────────
HTTPS_PORT="$(grep -E '^NGINX_HTTPS_PORT=' .env | tail -1 | cut -d= -f2- || true)"
HTTPS_PORT="${HTTPS_PORT:-8445}"
log "Waiting for /health/ to come up on port $HTTPS_PORT"
HEALTHY=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -ksf "https://localhost:$HTTPS_PORT/health/" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  sleep 5
done

if [ "$HEALTHY" -eq 1 ]; then
  echo ""
  echo "Upgrade complete. /health/ is responding."
  exit 0
fi

echo ""
echo "======================================================================"
echo "HEALTH CHECK FAILED after the upgrade. Nothing was rolled back"
echo "automatically -- decide based on 'docker compose logs' first. To roll back:"
echo ""
if [ "$IS_GIT_CHECKOUT" -eq 1 ] && [ -z "$NEW_IMAGE" ]; then
  echo "  git checkout $PREVIOUS_COMMIT"
  echo "  docker compose build"
else
  echo "  # edit .env: set BACKDEEZUP_IMAGE back to its previous value"
  echo "  docker compose pull"
fi
echo "  docker compose up -d"
echo ""
if [ -n "$BACKUP_FILE" ]; then
  echo "If the new code is simply broken, the above is enough -- no data was"
  echo "touched. Only restore the database too if a migration corrupted data:"
  echo -n '  docker compose exec -T db sh -c '\''pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists'\'' < '
  echo "$BACKUP_FILE"
fi
echo "======================================================================"
exit 1
