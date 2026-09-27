# Deployment

Full production deployment runbook — tested on Debian 13 WSL2 on Windows Server 2025.

---

## Prerequisites

- Docker Engine installed (see [Installation](installation.md))
- `git` and `ssh` configured for GitHub access
- Google OAuth credentials (`google_client.json`)
- Repo cloned: `git clone git@github.com:devadalberto/backdeezup.git`

---

## One-line install (Phase 49)

An alternative to cloning the repo: `scripts/install.sh` sets up a fresh install
using the [published image](releases.md) instead — no git clone, no local build.
```bash
curl -fsSL https://raw.githubusercontent.com/devadalberto/backdeezup/main/scripts/install.sh | bash
```
It checks for `docker`/`docker compose`/`curl`/`openssl`, downloads just what
`docker compose` needs (`docker-compose.yml`, `.env.sample`, `Makefile`,
`nginx/nginx.conf`, `Caddyfile`), generates `DJANGO_SECRET_KEY`,
`GOOGLE_ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, and `REDIS_PASSWORD` locally
(never printed in full — first 4 characters only), generates a self-signed TLS
cert, starts the stack, and prints the setup-wizard URL.

Every action is printed before it happens; writing into an existing, non-empty
target directory asks for confirmation first (`-y`/`--yes` to skip, for
automation). `--dry-run` prints the full plan and makes zero writes and zero
docker/network changes — verified: a dry run creates nothing on disk.

If no release has been published yet (or the GHCR package is still private —
see `releases.md`), the pull fails and the script offers to fall back to
cloning the source and building locally instead, asking first.

The resulting directory has its own `.env`, `docker-compose.yml`, and `Makefile`
(so `make up`/`make db-backup`/etc. all work) but is **not** a git checkout —
`make build`/`make redeploy`'s `git pull` step won't work there. Upgrade it with
`scripts/upgrade.sh` (see `docs/upgrading.md`) instead.

---

## Makefile reference

All common operations are available via `make`. Run `make help` to see all targets.

### Docker / production

| Command | What it does |
|---|---|
| `make build` | Build the Docker image |
| `make up` | Start all containers (detached) |
| `make down` | Stop all containers |
| `make restart` | `down` + `up` |
| `make redeploy` | `git pull` + `build` + `down` + `up` + `migrate` — full update in one command |
| `make logs` | Tail all container logs |
| `make ps` | Show container status |

### Django

| Command | What it does |
|---|---|
| `make migrate` | Run database migrations |
| `make superuser` | Create Django superuser |
| `make shell` | Open Django shell inside container |
| `make check` | Run Django system check |

### Drive / Photos pipeline

| Command | What it does |
|---|---|
| `make discover` | Discover Drive media (images/videos) |
| `make discover-files` | Discover Drive documents (PDF, Office, etc.) |
| `make discover-photos` | Discover Google Photos |
| `make sync-download` | Download DISCOVERED assets (limit=20) |
| `make sync-import` | SHA-256 hash + copy to media/ (limit=20) |
| `make sync-verify` | Verify both proofs: disk + DB (limit=50) |
| `make sync-mark-delete` | Queue VERIFIED assets for deletion (limit=100) |
| `make sync-commit-delete` | Execute Drive deletion in trash mode (limit=50) |

### Gmail pipeline

| Command | What it does |
|---|---|
| `make gmail-discover` | Full Gmail snapshot — discovers all message metadata |
| `make gmail-incremental` | Incremental sync via historyId (fast, run after first discover) |
| `make gmail-download` | Download raw .eml files to disk (limit=20) |
| `make gmail-verify` | Verify .eml files exist on disk (limit=50) |

### Local dev

| Command | What it does |
|---|---|
| `make run` | Django dev server on port 8844 (no Docker) |
| `make docs` | MkDocs documentation server on port 8001 |

### WSL2 / Windows

| Command | What it does |
|---|---|
| `make wsl-proxy` | Forward port 8844 from Windows IP to WSL2 internal IP |

Override the API host with `HOST=`:
```bash
make discover HOST=http://192.168.88.60:8844
make gmail-discover HOST=http://192.168.88.60:8844
```

---

## First-time deployment

### 1. Clone and configure

```bash
git clone git@github.com:devadalberto/backdeezup.git
cd backdeezup
cp .env.sample .env
vim .env   # fill in all CHANGE_ME values
```

Generate required values:
```bash
# Django secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Fernet encryption key (stdlib only)
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

### 2. Place Google credentials

```bash
mkdir -p secrets
cp /path/to/client_secret_*.json secrets/google_client.json
```

### 3. Build and start

```bash
make build
make up
make ps      # verify all 6 containers are Up
```

### 4. Initialise database and create superuser

```bash
make migrate
make superuser
```

### 5. Authenticate with Google

Open **https://localhost:8445/api/docs** → `POST /auth/connect`

(Note: port 8844 HTTP redirects to 8445 HTTPS)

Complete the OAuth flow in your browser. The encrypted token is saved to `secrets/google_token.json`.

---

## Drive + Photos backup pipeline

Run each step in sequence:

```bash
make discover           # find images/videos in Drive
make discover-files     # find documents in Drive
make discover-photos    # find items in Google Photos
make sync-download      # download to local disk
make sync-import        # hash + copy to media/
make sync-verify        # confirm both proofs
make sync-mark-delete   # queue for deletion
make sync-commit-delete # trash in Drive (recoverable 30 days)
```

Run steps in a loop until each returns `0` new items:
```bash
# Example: keep downloading until done
while make sync-download | grep -q '"downloaded": [^0]'; do sleep 2; done
```

---

## Gmail backup pipeline

```bash
make gmail-discover     # full snapshot — run once to populate DB
make gmail-incremental  # run regularly to pick up new mail
make gmail-download     # save .eml files to disk
make gmail-verify       # confirm files on disk
```

!!! tip "Incremental sync"
    After the first `gmail-discover`, use `gmail-incremental` for all subsequent runs.
    It uses Gmail's `historyId` and is much faster. Falls back to full discover automatically if history expires (>7 days between runs).

!!! note "Gmail cleanup"
    Trash and label operations are available in the Gmail Ops Console at `/admin/gmail/ops/` or via the API at `/api/gmail/cleanup/*`. All cleanup actions are **dry-run by default**.

---

## Update deployment (subsequent releases)

One command handles pull + rebuild + restart + migrate:

```bash
make redeploy
```

Or step by step:
```bash
git pull origin main
make build
make down
make fix-perms   # only needed once, the first time you build a non-root image (Phase 41+)
make up
make migrate
```

Full guide, including why to back up the database first and how to roll back:
`docs/upgrading.md`.

---

## Ongoing operations

```bash
make logs               # tail all container logs
make ps                 # container status
make shell              # Django shell
make check              # Django system check
make down               # stop everything
```

---

## Non-root container (Phase 41)

The image runs as a fixed non-root user (`appuser`, uid/gid `10001`) by default —
this is the shipped default, not an opt-in. `--build-arg NONROOT=0` at `make build`
time is the escape hatch back to the old root image, for environments where the
volume-permission migration below is not possible.

**Upgrading an existing install:** the `media` and `staticfiles` Docker volumes were
created under the old root image and are root-owned. Run this **once**, before the
first `make up` with the new image:
```bash
make build
make fix-perms   # chowns media/ + staticfiles/ volumes to uid:gid 10001
make up
```
Skipping `fix-perms` on an existing install is safe to attempt — the entrypoint
checks that `MEDIA_ROOT` is writable before doing anything else and fails with a
clear message (rather than a confusing traceback partway through startup) if it
isn't. Nothing is auto-chowned silently.

**Fresh installs** need no extra step — brand-new named volumes are populated from
the image the first time they're mounted, so they come up already owned by
`appuser`.

**Host-mounted `secrets/` directory:** unlike `media`/`staticfiles` (Docker-managed
volumes, fixed by `fix-perms`), `./secrets` is a bind mount of a directory on the
Docker host, so its permissions come from the host filesystem, not the image. If
Google OAuth token refresh fails with a permission error after upgrading, `chown -R
10001:10001 secrets/` on the host (or `chmod` it group-writable) fixes it the same
way `fix-perms` does for the two named volumes.

## Bind address (Phase 39)

As of Phase 39, `web` and `nginx` publish their ports on `127.0.0.1` by default
(previously `0.0.0.0`) — localhost/loopback access only. This is a breaking
change for any deployment that relied on reaching the container ports directly
from another machine on the LAN (the `wsl-proxy` / `netsh portproxy` path below
still works, since that forwards *into* WSL first, but the compose-published
port itself is no longer reachable from outside the Docker host unless you
override it).

To restore the old LAN-reachable behavior, set in `.env`:
```bash
BIND_ADDR=0.0.0.0
```
`WEB_PORT` (8845), `NGINX_HTTP_PORT` (8844), `NGINX_HTTPS_PORT` (8445) are also
overridable but keep their existing defaults. Run `make up` (not `restart`)
after changing `.env` so the new bind takes effect. Validate the compose file
with `make compose-check` any time you edit these.

## Reverse proxy: nginx vs Caddy vs external (Phase 48)

Three ways to terminate TLS in front of `web`, in order of how much this repo
manages for you:

| | nginx (default) | Caddy (opt-in) | External reverse proxy |
|---|---|---|---|
| Enabled by | Nothing — always on | `docker compose --profile caddy up -d` | You run it outside this repo entirely |
| Certificate | Self-signed, `make gen-certs` | Automatic (Let's Encrypt) or its own internal CA | Your own (Traefik, Cloudflare Tunnel, a load balancer, etc.) |
| Needs a public domain? | No | Only for real Let's Encrypt certs | Depends on your setup |
| Best for | Local/LAN use, the default `docs/dev-quickstart.md` path | A real public hostname you want HTTPS for with no separate proxy to run | You already run a proxy in front of everything and just want `web`'s bare port |

**Use nginx (do nothing)** if you're running this at home or on a LAN — it's what
`make build && make up` gives you, self-signed cert included.

**Opt into Caddy** if you want to expose BackDeezUp on a real domain with a
browser-trusted certificate and don't want to run Certbot or a separate proxy
yourself:
```bash
# .env
DOMAIN=backdeezup.example.com
CADDY_TLS_MODE=you@example.com   # real email -> real Let's Encrypt cert
```
```bash
docker compose --profile caddy up -d
```
nginx keeps running alongside it on its own ports (8844/8445) unless you stop it —
`docker compose stop nginx` if you only want Caddy fronting things. Caddy needs
ports 80 and 443 actually reachable from the public internet for the Let's
Encrypt HTTP challenge to succeed; `BIND_ADDR=0.0.0.0` (see above) plus your
router/firewall/DNS pointing `DOMAIN` at this host. Leave `DOMAIN`/`CADDY_TLS_MODE`
unset and it defaults to `localhost` + Caddy's own internal CA — same self-signed
trust model as nginx's dev cert, works with zero config for local testing.
`Caddyfile` at the repo root mirrors nginx's two direct-serve locations
(`/static/`, `/media/images/`) and proxies everything else to `web:8000`.

**Run your own external proxy** (Traefik, Cloudflare Tunnel, an existing
load balancer) if you already have one — point it at `web:8000` directly (bypass
both nginx and Caddy) or at nginx's/Caddy's port if you want their static-file
serving too. Nothing in this repo needs to know about it.

## WSL2 external access (Windows Server only)

To expose the app on the Windows VM's external IP:

```bash
make wsl-proxy          # run from inside Debian WSL
```

Or manually in PowerShell (as Administrator):
```powershell
$wslIp = wsl -d Debian -- hostname -I | ForEach-Object { $_.Trim().Split(" ")[0] }
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8844 connectaddress=$wslIp connectport=8844
New-NetFirewallRule -DisplayName "BackDeezUp 8844" -Direction Inbound -Protocol TCP -LocalPort 8844 -Action Allow
```

!!! warning "WSL IP changes on restart"
    Re-run `make wsl-proxy` after each WSL restart.

---

## Production checklist

- [ ] `DEBUG=False` in `.env`
- [ ] `DJANGO_SECRET_KEY` is a long random string
- [ ] `ALLOWED_HOSTS` includes your server IP/hostname
- [ ] `CSRF_TRUSTED_ORIGINS` includes your server URL with port
- [ ] `BIND_ADDR=0.0.0.0` set in `.env` if the app must be reachable from outside the Docker host (default `127.0.0.1` is loopback-only)
- [ ] `make fix-perms` run once if upgrading an existing install to the non-root image (Phase 41)
- [ ] `POSTGRES_PASSWORD` is not the sample value
- [ ] `GOOGLE_ENCRYPTION_KEY` backed up securely
- [ ] `secrets/google_client.json` in place
- [ ] `make ps` — all 6 containers `Up`
- [ ] `make migrate` — all migrations applied
- [ ] Superuser created (`make superuser`)
- [ ] OAuth completed (`POST /auth/connect`)
- [ ] Static files loading (`/admin/` has styles)
- [ ] Drive pipeline tested (`make discover`)
- [ ] Gmail pipeline tested (`make gmail-discover`)
