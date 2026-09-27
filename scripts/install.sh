#!/usr/bin/env bash
# BackDeezUp one-line installer (Phase 49).
#
#   curl -fsSL https://raw.githubusercontent.com/devadalberto/backdeezup/main/scripts/install.sh | bash
#
# Sets up a fresh install using the published container image (docs/releases.md) --
# no git clone, no local build. Downloads only what docker-compose needs
# (docker-compose.yml, .env.sample, Makefile, nginx/nginx.conf, Caddyfile),
# generates secrets locally, starts the stack, and prints the setup-wizard URL.
#
# Every action is printed before it happens. Every write to disk, and every step
# that could disrupt an existing install, is confirmed first -- pass -y/--yes to
# skip confirmations non-interactively. --dry-run prints the plan and makes zero
# writes and zero docker/network changes.
#
# Options:
#   --dir PATH        Target directory (default: ./backdeezup)
#   --image IMAGE     Image to pull (default: ghcr.io/devadalberto/backdeezup:latest)
#   --base-url URL    Where to fetch the compose/config files from
#                      (default: https://raw.githubusercontent.com/devadalberto/backdeezup/main)
#   -y, --yes         Assume "yes" to every confirmation (for automation/CI)
#   --dry-run         Print what would happen; write nothing, run nothing
#   -h, --help        Show this help

set -euo pipefail

DIR="./backdeezup"
IMAGE="ghcr.io/devadalberto/backdeezup:latest"
BASE_URL="https://raw.githubusercontent.com/devadalberto/backdeezup/main"
ASSUME_YES=0
DRY_RUN=0

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --image) IMAGE="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    -y|--yes) ASSUME_YES=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

log()  { echo ">> $*"; }
note() { echo "   $*"; }

confirm() {
  # confirm "question" -- returns 0 (proceed) if --yes, if not a tty, or on 'y'/'Y'.
  local question="$1"
  if [ "$ASSUME_YES" -eq 1 ]; then
    return 0
  fi
  if [ ! -t 0 ]; then
    echo "Refusing to guess on '$question' with no terminal attached and no --yes. Aborting." >&2
    exit 1
  fi
  read -r -p "$question [y/N] " reply
  case "$reply" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

run() {
  # run <description> -- <command...>  : prints, then executes unless --dry-run.
  local desc="$1"; shift
  log "$desc"
  if [ "$DRY_RUN" -eq 1 ]; then
    note "[dry-run] would run: $*"
    return 0
  fi
  "$@"
}

fetch() {
  # fetch <relative-path> <dest> : downloads BASE_URL/<relative-path> to <dest>.
  local rel="$1" dest="$2"
  log "Fetching $rel"
  if [ "$DRY_RUN" -eq 1 ]; then
    note "[dry-run] would fetch $BASE_URL/$rel -> $dest"
    return 0
  fi
  curl -fsSL "$BASE_URL/$rel" -o "$dest"
}

redact() {
  # redact <value> : first 4 chars + *** -- never print a secret in full.
  local v="$1"
  echo "${v:0:4}***"
}

gen_secret_hex() { openssl rand -hex 24; }       # safe in a postgres:// URL, no % @ / :
gen_secret_fernet() { openssl rand -base64 32; }  # 44 chars, valid Fernet key (verified)

# ── 1. Preflight ───────────────────────────────────────────────────────────────
log "Checking prerequisites"
for cmd in docker curl openssl; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "FAIL: '$cmd' not found. Install it and re-run." >&2
    exit 1
  fi
done
if ! docker info >/dev/null 2>&1; then
  echo "FAIL: docker daemon not reachable. Is Docker running?" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "FAIL: 'docker compose' (v2 plugin) not found." >&2
  exit 1
fi
note "OK: docker, docker compose, curl, openssl all present; daemon reachable"

if [ -e "$DIR" ] && [ -n "$(ls -A "$DIR" 2>/dev/null || true)" ]; then
  if [ -f "$DIR/.env" ]; then
    echo "FAIL: $DIR already has a .env -- this looks like an existing install." >&2
    echo "      Use scripts/upgrade.sh instead, or pass --dir to install somewhere new." >&2
    exit 1
  fi
  confirm "$DIR exists and isn't empty. Continue and write into it?" || { echo "Aborted."; exit 1; }
fi

# ── 2. Fetch the files docker compose needs (no git clone, no local build) ─────
log "Creating $DIR"
if [ "$DRY_RUN" -eq 0 ]; then
  mkdir -p "$DIR/nginx" "$DIR/nginx/certs" "$DIR/secrets" "$DIR/backups"
fi

fetch "docker-compose.yml" "$DIR/docker-compose.yml"
fetch ".env.sample"        "$DIR/.env.sample"
fetch "Makefile"           "$DIR/Makefile"
fetch "nginx/nginx.conf"   "$DIR/nginx/nginx.conf"
fetch "Caddyfile"          "$DIR/Caddyfile"

# ── 3. Generate secrets locally -- never printed in full ───────────────────────
log "Generating secrets locally"
if [ "$DRY_RUN" -eq 1 ]; then
  note "[dry-run] would generate DJANGO_SECRET_KEY, GOOGLE_ENCRYPTION_KEY,"
  note "[dry-run] POSTGRES_PASSWORD, REDIS_PASSWORD and write $DIR/.env"
else
  DJANGO_SECRET_KEY="$(openssl rand -hex 32)"
  GOOGLE_ENCRYPTION_KEY="$(gen_secret_fernet)"
  POSTGRES_PASSWORD="$(gen_secret_hex)"
  REDIS_PASSWORD="$(gen_secret_hex)"

  note "DJANGO_SECRET_KEY:     $(redact "$DJANGO_SECRET_KEY")"
  note "GOOGLE_ENCRYPTION_KEY: $(redact "$GOOGLE_ENCRYPTION_KEY")"
  note "POSTGRES_PASSWORD:     $(redact "$POSTGRES_PASSWORD")"
  note "REDIS_PASSWORD:        $(redact "$REDIS_PASSWORD")"

  cp "$DIR/.env.sample" "$DIR/.env"
  # Replace only the placeholder lines this script owns; every other line
  # (Google MIME allowlist, cleanup/storage/export defaults, etc.) is left
  # exactly as .env.sample ships it.
  python3 - "$DIR/.env" "$DJANGO_SECRET_KEY" "$GOOGLE_ENCRYPTION_KEY" "$POSTGRES_PASSWORD" "$REDIS_PASSWORD" "$IMAGE" <<'PYEOF'
import re, sys
path, secret_key, enc_key, pg_pw, redis_pw, image = sys.argv[1:7]
with open(path) as f:
    text = f.read()

def set_var(text, name, value):
    pattern = re.compile(rf"^#?\s*{name}=.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(f"{name}={value}", text, count=1)
    return text + f"\n{name}={value}\n"

text = set_var(text, "DJANGO_SECRET_KEY", secret_key)
text = set_var(text, "DEBUG", "False")
text = set_var(text, "GOOGLE_ENCRYPTION_KEY", enc_key)
text = set_var(text, "POSTGRES_PASSWORD", pg_pw)
text = set_var(text, "DATABASE_URL", f"postgres://backdeezup:{pg_pw}@db:5432/backdeezup")
text = set_var(text, "REDIS_PASSWORD", redis_pw)
text = set_var(text, "BACKDEEZUP_IMAGE", image)

with open(path, "w") as f:
    f.write(text)
PYEOF
  chmod 600 "$DIR/.env"
fi

# ── 4. Self-signed TLS cert for nginx (same as `make gen-certs`) ───────────────
# Generated inline rather than fetching scripts/gen-dev-certs.sh -- that script
# locates nginx/certs/ relative to its OWN path ($0), which breaks once it's not
# sitting in a real scripts/ subdirectory one level below the project root.
if [ "$DRY_RUN" -eq 1 ]; then
  log "Would generate a self-signed TLS cert into $DIR/nginx/certs/"
else
  log "Generating a self-signed TLS cert (nginx/certs/)"
  openssl req -x509 -newkey rsa:4096 -sha256 -days 3650 -nodes \
    -keyout "$DIR/nginx/certs/server.key" \
    -out    "$DIR/nginx/certs/server.crt" \
    -subj "/CN=backdeezup" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
    2>/dev/null
  chmod 600 "$DIR/nginx/certs/server.key"
  chmod 644 "$DIR/nginx/certs/server.crt"
fi

# ── 5. Pull the published image (fall back to source build if unavailable) ─────
log "Pulling $IMAGE"
if [ "$DRY_RUN" -eq 1 ]; then
  note "[dry-run] would run: docker compose pull in $DIR"
elif ! ( cd "$DIR" && docker compose pull 2>&1 | tee /tmp/backdeezup-install-pull.log ); then
  echo ""
  echo "Could not pull $IMAGE. Common reasons:"
  echo "  - No release has been published yet (docs/releases.md)"
  echo "  - The GHCR package exists but is still private (one-time manual fix by the maintainer)"
  echo ""
  if command -v git >/dev/null 2>&1 && confirm "Fall back to cloning the source and building locally instead?"; then
    log "Cloning devadalberto/backdeezup into $DIR/src and building"
    git clone --depth 1 https://github.com/devadalberto/backdeezup.git "$DIR/src"
    cp "$DIR/.env" "$DIR/src/.env"
    rm -rf "$DIR/src/nginx/certs"; ln -s "../../nginx/certs" "$DIR/src/nginx/certs" 2>/dev/null || cp -r "$DIR/nginx/certs" "$DIR/src/nginx/certs"
    ( cd "$DIR/src" && docker compose build )
    DIR="$DIR/src"
  else
    echo "Aborted: no usable image and no fallback chosen. See docs/releases.md." >&2
    exit 1
  fi
fi

# ── 6. Migrate, then start the stack ────────────────────────────────────────────
# docker-compose.yml declares `media` as an external volume -- Compose never
# creates one of those for you, only non-external named volumes. Safe to re-run.
run "Ensuring the external 'backdeezup_media' volume exists" docker volume create backdeezup_media

# Migrate via a one-off container BEFORE starting the persistent stack. celery/
# celerybeat have no dependency on migrations being applied before they start
# (only on db/redis being healthy), so `up -d` alone races them against a bare
# database on a truly fresh install -- celerybeat crash-loops on missing tables
# until it happens to retry after migrate finishes. `run` pulls in the same
# db/redis dependencies (depends_on) without racing anything else.
run "Running database migrations" bash -c "cd '$DIR' && docker compose run --rm web python manage.py migrate"
run "Starting the stack" bash -c "cd '$DIR' && docker compose up -d"

if [ "$DRY_RUN" -eq 1 ]; then
  log "Dry run complete -- nothing was written, nothing was started."
  exit 0
fi

echo ""
echo "======================================================================"
echo "Install complete: $DIR"
echo ""
echo "Next steps:"
echo "  1. Get a Google OAuth Desktop-app client secret JSON from Google Cloud"
echo "     Console and save it as: $DIR/secrets/google_client.json"
echo "  2. Open the setup wizard: https://localhost:8445/setup/"
echo "     (self-signed cert -- your browser will warn, that's expected)"
echo ""
echo "This directory has its own .env and docker-compose.yml but is NOT a git"
echo "checkout -- 'make build'/'make redeploy' won't work here. Upgrade with"
echo "scripts/upgrade.sh (pulls a newer image tag) instead. See docs/releases.md"
echo "and docs/upgrading.md."
echo "======================================================================"
