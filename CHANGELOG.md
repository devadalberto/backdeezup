# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Phase 53** — celery worker concurrency (`-c 2`) and the per-service CPU/memory
  limits in `docker-compose.yml` (`web` 1.0/512M, `celery` 2.0/1G, `celerybeat`
  0.25/192M) were hardcoded, with no way to raise them on bigger hardware short of
  hand-editing the compose file. Made all six values env-driven
  (`CELERY_CONCURRENCY`, `WEB_CPUS`/`WEB_MEMORY`, `CELERY_CPUS`/`CELERY_MEMORY`,
  `CELERYBEAT_CPUS`/`CELERYBEAT_MEMORY`, documented in `.env.sample`) with
  defaults matching the original hardcoded values exactly — verified via
  `docker compose config` byte-for-byte against the pre-change output (`cpus: 2`
  / `memory: "1073741824"` etc., and `-c "2"` in the celery command), and again
  with overrides applied, before and after. Zero behavior change for anyone who
  doesn't set the new vars. Added a "Sizing for Bigger Hardware" table to
  `docs/operations.md` (and a pointer from README's hardware section) mapping
  vCPU/RAM tiers to recommended values — Gmail downloads are I/O-bound, so the
  real ceiling on `make gmail-loop WORKERS=N` is Gmail's own per-user API quota,
  not CPU count; the table also flags `GOOGLE_API_MAX_RPS` as a backstop to use
  only if 429s actually appear, not preemptively. Triggered by a real question
  about sizing a 12-vCPU/36GB deployment. No application code changes.

### Fixed
- **Phase 64** — `core/storage.py`'s `usage()` called
  `shutil.disk_usage(settings.MEDIA_ROOT)` with no check that the directory
  exists first. Found live: pushing Phase 63 triggered a real CI run of the
  new pytest step, which came back 64/65 passed — a genuine bug the new
  step immediately caught, not a flaw in Phase 63's wiring. `MEDIA_ROOT`
  defaults to `backend_django/media` (`config/settings.py:158`); in the real
  Docker deployment this is masked because `docker-compose.yml`'s `media:`
  named volume auto-creates its mount point the moment it's first attached,
  before any file is ever downloaded — but a bare `manage.py`/`pytest` run
  (exactly what CI does) has no such guarantee, and a genuinely fresh
  non-Docker install would hit the same crash on its very first download
  task. Fixed: `os.makedirs(settings.MEDIA_ROOT, exist_ok=True)` before
  measuring disk usage. Verified by moving the real `media/` directory
  aside locally (reproducing CI's exact missing-directory condition) —
  the previously-failing test now passes (14/14), and the full 6-file
  scoped suite from Phase 63 passes cleanly (65/65) — then restored the
  original directory content afterward.
- **Phase 63** — closes out Phase 55: CI's `test` job's last remaining
  failure was `ModuleNotFoundError: No module named 'pytest'` on 6 modules
  (`google_media_backup/tests_resumable_download.py`, `.../tests_unit.py`,
  `google_gmail_backup/tests_cleanup_safeguards.py`, `.../tests_notify_wiring.py`,
  `.../tests_schemas.py`, `.../tests_undo_protect.py`). Confirmed by reading
  every file: all 6 are genuine pytest-native tests (`@pytest.mark.django_db`,
  `@pytest.fixture`, `@pytest.mark.unit`, `tmp_path`/`monkeypatch` fixtures),
  not `unittest.TestCase`-based like the rest of the codebase.
  `pyproject.toml` already declared a `test` optional-dependency group
  (`pytest`, `pytest-django`, `pytest-cov`, `pytest-mock`) and a fully
  configured `[tool.pytest.ini_options]` section matching exactly how these
  files use markers — but CI's `test` job's `uv sync` never installed that
  group, and CI never ran `pytest` at all. These 6 files had likely never
  actually executed in CI, ever — this was only fully diagnosable once
  Phase 57 fixed the OOM that had been hiding the real tracebacks. Fixed:
  `uv sync` → `uv sync --extra test`, plus a new CI step running `pytest`
  scoped to exactly these 6 files. Verified locally with CI-matching env
  vars: 65 passed, 0 failed, twice.
- **Phase 62** — clicking "Execute" on a cleanup rule returned a raw,
  unstyled "403 Forbidden" page with no explanation. Confirmed byte-for-byte
  this is Django's own generic `permission_denied` fallback page (rendered
  locally and compared character-for-character to the reported output) —
  meaning `django_ratelimit`'s `Ratelimited` exception (a `PermissionDenied`
  subclass, raised by the 4 `@ratelimit(...)`-decorated endpoints in
  `api.py`, all on `gmail_api`) was unhandled by Ninja and fell through to
  Django's default error handling instead of a clean JSON response. Very
  likely a genuine hit of the `10/h` execute limit (or `3/h` run-all limit)
  from extensive testing this session — the rate limit itself is a
  reasonable safety feature; the bug was purely the broken error
  presentation. Fixed: registered one
  `@gmail_api.exception_handler(Ratelimited)` returning a clean `429` JSON
  body — covers all 4 rate-limited endpoints at once. Verified against the
  real module: `gmail_api._exception_handlers` includes `Ratelimited`
  alongside Ninja's built-ins, `gmail_api.urls` still builds with no
  conflicts, and calling the handler directly with a real request returns
  `429` with the expected JSON body.
- **Phase 61** — the ops console's ("`/admin/gmail/ops/`") Output panel had two
  bugs: the "▶ Output" header was a static unicode glyph inside a plain `<b>`
  tag — no `onclick`, no `<details>`/`<summary>`, confirmed by grepping the
  whole template (zero matches for "details"/"summary") — so it looked
  clickable but did nothing. Separately, `<pre id="out">` had no
  `max-height`/`overflow`, and its container is `position:sticky`, so as
  output grew (e.g. a 20-rule dry-run's JSON), the box's own height grew
  unbounded and, being sticky, visibly dragged the page around. Fixed:
  replaced the static header with a real `<details open>`/`<summary>`
  (native, accessible, free expand/collapse triangle, no JS needed) and
  added `max-height:320px;overflow-y:auto;` to `<pre id="out">` so long
  output scrolls within its own fixed box instead of growing the sticky
  container. Template-only change; verified the template still parses
  correctly via Django's template engine.
- **Phase 60** — `make cleanup-dry`/`make cleanup-run` (both via
  `run_cleanup.py`) crashed unconditionally with `TypeError: string indices
  must be integers, not 'str'`, and the real (non-dry) path of `make
  gmail-empty-trash` (`empty_gmail_trash.py`) had the identical bug, ready to
  crash the moment it was tried. Found live right after seeding 20 cleanup
  rules and confirming the backup at 100% — this was the exact next step
  needed to actually clean up the inbox. Root cause, confirmed by
  reproducing the exact error in an isolated shell: both files built a
  custom `tqdm` `bar_format` referencing `{postfix[msgs]}`/`{postfix[d]}` as
  if `postfix` stayed a subscriptable dict — it doesn't, tqdm converts it to
  a plain string (e.g. `"msgs=42"`) for display, so `"msgs=42"["msgs"]`
  raised exactly the observed error, on the very first `tqdm(...)`
  construction. A second, latent bug (`pbar.postfix["msgs"] = value`
  mid-loop) would have surfaced the moment the first was naively patched —
  caught and fixed together, confirmed separately in isolation before
  either file was touched. Fixed: `bar_format` now uses plain `{postfix}`,
  and postfix updates use the correct `pbar.set_postfix(msgs=value)`
  keyword form throughout. Verified by running the real `run_cleanup
  --dry-run` command end-to-end against a throwaway local SQLite DB with a
  real rule and message (not just the isolated repro) — completed cleanly,
  no traceback, correct output.
- **Phase 59** — 9 `make` ops commands (`gmail-progress`, `gmail-incremental`,
  the `sync-*` targets, etc.) hardcoded `HOST ?= http://localhost:8844`, and
  `check-services` hardcoded literal ports `8845`/`8844` directly — neither
  read a customized `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT`/`WEB_PORT`. Found
  live right after Phase 58: `make gmail-progress` failed with a confusing
  `python3 -m json.tool` error ("Expecting value: line 1 column 1 (char 0)"),
  traced to `curl -s` (no `-S`) silently returning zero bytes because it hit
  a port this deployment doesn't have bound at all. Third recurrence of the
  same "hardcoded default ignores `.env` override" pattern this session
  (Phases 56, 58). Fixed: `HOST` and `check-services`'s port checks now read
  `.env`'s actual values at Makefile-parse time, falling back to today's
  defaults if `.env` isn't found; `HOST`'s default scheme also switched from
  `http` to `https` (going straight to the real endpoint instead of relying
  on an unfollowed redirect), and all 9 `$(HOST)`-using curl calls gained
  `-k` (self-signed cert, matching the project's existing documented
  convention elsewhere) and `-S` (so a real failure shows a real error
  instead of silently feeding `json.tool` zero bytes). Verified via `make -n`
  dry-runs, both with no `.env` (unchanged defaults) and with a throwaway
  `.env` matching a real custom-port deployment.
- **Phase 58** — nginx's HTTP→HTTPS redirect (`nginx/nginx.conf:13`,
  `return 301 https://$host:8445$request_uri;`) hardcoded port `8445` as a
  literal, but `nginx.conf` was bind-mounted as a static, unmodified file —
  so a customized `NGINX_HTTPS_PORT` never reached it, even though
  `docker-compose.yml`'s own port mapping correctly read that same variable.
  Found live on a real deployment running on custom ports (18844/18445):
  hitting the HTTP port redirected to `https://<host>:8445/...`, a port that
  deployment wasn't even listening on — the request failed outright. Docker's
  port remapping is transparent to the container, so nginx has no built-in way
  to know the externally-published HTTPS port without being told explicitly.
  Fixed by turning `nginx.conf` into `nginx.conf.template`
  (`${NGINX_HTTPS_PORT}` in place of the hardcoded value), mounting the
  template instead of a static file, passing `NGINX_HTTPS_PORT` to the nginx
  container via `environment:`, and running `envsubst` in a `command:`
  override before nginx starts. Default behavior unchanged — verified
  byte-identical output at the default port. Verified end-to-end with a real
  standalone `nginx:stable-alpine` container (not just config inspection):
  `curl -I http://localhost/` returns `Location: https://localhost:8445/` at
  the default port, and `Location: https://localhost:18445/` with
  `NGINX_HTTPS_PORT=18445` — the actual bug, actually fixed.
- **Phase 57** — 4 tests in `google_gmail_backup/tests_reconciliation.py`
  (`Reconcile404Test`, `ReconcileTrashLabelTest`, `ReconcileMessageAliveTest`,
  `ProtectedSenderReconcileTest`) mocked `svc` as a bare `MagicMock()` without
  configuring `.list()`, so `task_gmail_reconcile()`'s pagination loop
  (`page_token = res.get("nextPageToken"); if not page_token: break`) never
  terminated — `MagicMock().get("nextPageToken")` returns a permanently-truthy
  `MagicMock`, the same object every call. Found live on PDX-CL1 while
  diagnosing Phase 55's CI OOM: with `DATABASE_URL=` cleared (forcing the same
  SQLite path CI uses), the full test run got past everything any CI log had
  ever shown and then hung indefinitely — not crashed — at
  `ProtectedSenderReconcileTest.test_protected_sender_still_soft_deleted_on_404`.
  Root cause confirmed by reproducing the `MagicMock()` behavior in an isolated
  shell. A very plausible explanation for CI's exit-137 OOM too: the loop has no
  `sleep` and every iteration grows the mock's `mock_calls` history unbounded.
  Not a production bug — real Gmail API responses correctly omit/`None`
  `nextPageToken` on the last page. Fixed by configuring `.list()`'s return
  value (`{"messages": [], "nextPageToken": None}`) in all 4 tests. Verified:
  all 9 tests in the file now pass in 0.328s (previously: hangs forever once
  reached).
- **Phase 56** — `make gmail-loop` ignored `WORKERS=` entirely: its download call
  never forwarded `--workers $(WORKERS)` (unlike `make gmail-download`, which does),
  so it silently fell back to the management command's hardcoded `default=10` no
  matter what `WORKERS=` was set to. Surfaced by a user bumping the concurrency on a
  bigger VM (Phase 53) and seeing it stay at 10. Fixed: forward `--workers $(WORKERS)`
  in `gmail-loop`'s download line, matching `gmail-download` exactly. Verified with
  `make -n gmail-loop WORKERS=40` — now expands to `--workers 40`; unset still
  defaults to `--workers 10`, unchanged.
- **Phase 55 (partial: lint + sast-bandit)** — CI's `lint`, `sast-bandit`, and `test`
  jobs had all been failing since ~2026-07-30; confirmed live via `gh run view
  --log-failed`, not assumed. Two of the three independent root causes fixed here:
  - `lint`: 25 real `F401` unused-import violations across 9 files (e.g.
    `core.setup.views` in `tests_setup_wizard2.py`, `django.utils.timezone` in
    `google_gmail_backup/admin.py`, several unused model imports in
    `tests_smoke.py`) plus one stray `F541` f-string with no placeholders in a
    Phase 54 test. Fixed with `ruff check --fix`; `ruff check` now passes clean.
  - `sast-bandit`: the `upload-sarif` step failed with "Invalid SARIF. JSON
    syntax error: Unexpected end of JSON input". Root cause confirmed from the
    Bandit step's own log (not the upload step): `-x backend_django/**/migrations`
    was unquoted in `ci.yml`, so the runner's shell glob-expanded it into 4
    separate paths before Bandit ever saw them — Bandit rejected the extras as
    unrecognized arguments and exited before writing `bandit.sarif`, which the
    workflow's `|| true` silently swallowed. Fixed by quoting the value; verified
    locally with a real Bandit run against this repo (valid SARIF JSON, 22
    findings at `--severity-level medium`, all 4 migrations dirs still excluded).
  `test`'s exit-137 OOM and 6 `_FailedTest` import failures remain open — the
  OOM kill happens before unittest ever prints its traceback summary, so the
  real cause isn't visible in any existing CI log; needs a run on hardware that
  can survive long enough to produce it. Full detail: `docs/ai-dev/GOALS_TODOS.md`.
- **Phase 54** — `google_gmail_backup/api.py`'s `/sync/download` endpoint (a separate,
  HTTP-triggered duplicate of `gmail_pipeline.py`'s download logic) never got Phase
  51's fix: its `except Exception as e:` block unconditionally recorded the error
  with no state transition, so a message Gmail confirms is gone (404 on
  `messages.get`) would stay `DISCOVERED` forever via this endpoint too — same
  failure shape as Phase 51, just a different code path. Flagged as a known gap
  when Phase 52 was written, now fixed: mirrors Phase 51 exactly — a confirmed
  404 (`HttpError.resp.status == 404`, or `"404"`/`"notFound"` string fallback)
  now calls the same `_mark_soft_deleted` helper instead of leaving the message
  stuck; every other exception keeps today's behavior unchanged. New
  `GmailApiDownload404Test` (2 tests) confirmed to actually catch the bug by
  reverting the fix and watching the 404 test fail before restoring it.
- **Phase 52** — every successful Gmail download/verify crashed on save, on both
  Postgres and SQLite: `GmailMessage.error = models.TextField(blank=True, default="")`
  has no `null=True` — `blank=True` only affects form validation, the real DB column
  is `NOT NULL` — but 4 call sites set `msg.error = None` on success instead of `""`
  (`gmail_pipeline.py`'s download and verify success paths, and their duplicate
  HTTP-API equivalents in `api.py`). Confirmed live on a real account, right after
  Phase 51 was confirmed working (152 messages correctly cleared): 348 *other*
  messages stuck in `DISCOVERED` with `django.db.utils.IntegrityError: null value in
  column "error" ... violates not-null constraint` — the file had already downloaded
  to disk, but the state-advancing save crashed, so the row never left `DISCOVERED`
  and got retried forever. Fixed: `None` → `""` at all 4 sites, matching the field's
  own declared default — no schema/migration change. New regression tests
  (`GmailErrorFieldNotNullTest`) — confirmed each one catches the bug by reverting
  the fix and watching it fail (an `IntegrityError`, identically on SQLite) before
  restoring it. That last part corrects an assumption from Phase 51's own notes:
  this was never a SQLite-vs-Postgres permissiveness gap — no existing test had ever
  actually run the success path with real data, because the one test that exercised
  this code always used an empty queue to dodge an unrelated `ThreadPoolExecutor`/
  `TestCase` deadlock. Flagged, not fixed (separate, narrower issue, noticed while
  reading the surrounding code): `api.py`'s `/sync/download` endpoint still has the
  Phase-51-shaped gap (no 404/permanent-gone handling) — out of scope for this phase.
- **Phase 51** — `make gmail-loop` could get permanently stuck making zero progress:
  `gmail_pipeline.py`'s `_download()` never changed a message's state on failure, only
  recorded the error — so a message Gmail itself confirms is gone (404 `notFound` on
  `messages.get`) stayed `DISCOVERED` forever, and since the download query always
  re-selects the *oldest* `DISCOVERED` rows first, one permanently-dead message blocked
  every message behind it from ever being attempted. Reproduced live on a real account
  (57,895 discovered messages): a 500-message batch was 100% 404, loop made zero forward
  progress. `task_gmail_reconcile` already had the right handling for this exact
  signal — reused its `_mark_soft_deleted` helper here instead of inventing new logic;
  a confirmed 404 now marks the message `SOFT_DELETED` (`deletion_source =
  "gmail_404_on_download"`) so the loop moves past it. Any other error keeps today's
  behavior unchanged (recorded, retried next pass) — deliberately narrow, not a general
  retry-limit system. New regression tests
  (`google_gmail_backup/tests_regression.py::GmailDownload404Test`) — confirmed one
  actually catches the bug by reverting the fix and watching it fail before restoring
  it. `docs/operations.md`'s Troubleshooting table gained a row for this symptom.
- **Phase 50** — the Phase 28 browser OAuth flow (`/dashboard/connect/start/`) was
  broken behind nginx **at any host or port**, including the documented default
  (`localhost:8445`) — not specific to any one install. `core/oauth.py` builds its
  Google redirect_uri from `request.build_absolute_uri()`, but `nginx.conf` forwarded
  `Host: $host` (nginx's `$host` strips the port) and `settings.py` never set
  `SECURE_PROXY_SSL_HEADER`/`USE_X_FORWARDED_HOST` despite nginx already sending
  `X-Forwarded-Proto: https`. Result: the redirect_uri Google received came out
  `http://<host>/...` — wrong scheme, no port — which it silently rejects after the
  user approves scopes (Google's generic "Something went wrong" page, no useful
  detail). Fixed: `nginx.conf` now sends `Host: $http_host` (preserves the port);
  `settings.py` now trusts nginx's `X-Forwarded-Proto`. Caddy (Phase 48) needed no
  change — its `reverse_proxy` already preserves the original `Host` header and sets
  `X-Forwarded-Proto`/`X-Forwarded-Host` by default. The CLI `make auth` flow was
  never affected (separate code path, no request-based redirect_uri) and was the
  working fallback while this was open. New regression test
  (`core/tests_oauth.py::test_connect_start_redirect_uri_respects_forwarded_proto_and_port`)
  — confirmed it actually catches the bug by reverting the settings.py fix and
  watching it fail (`http://` instead of `https://`) before restoring it.

### Changed
- Removed `docs/backdeezup-prompts-2026-05-19.md` (an old raw session-prompt dump,
  never referenced from anywhere) and added `*prompt*`/`*propmt*` patterns to
  `.gitignore`/`.dockerignore` so files like it don't get committed or shipped
  in the image again.
- **Phase 39** — `web` and `nginx` compose ports now bind `127.0.0.1` by default (was
  `0.0.0.0`); override with `BIND_ADDR=0.0.0.0` in `.env` to restore LAN access.
  `WEB_PORT`/`NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT` env vars added (same 8845/8844/8445
  defaults). Added `web` healthcheck (TCP probe on the gunicorn port) and `celerybeat`
  healthcheck (`pgrep` for the beat process); both were previously unmonitored.
  New `make compose-check` target (`docker compose config -q`). See `docs/deployment.md`.
- **Phase 40** — pinned the `uv` build stage from `ghcr.io/astral-sh/uv:latest` to
  `:0.12.19` (the version `:latest` resolved to as of 2026-09-27, confirmed via the
  GHCR manifest API). Added `graphify-out` and `backups` to `.dockerignore`. Verified
  with a full `docker build`: image size unchanged (1.99GB).
- **Phase 41** — the image now runs as a fixed non-root user (`appuser`, uid/gid
  `10001`) by default. `--build-arg NONROOT=0` restores the old root image. New
  `make fix-perms` target chowns the `media`/`staticfiles` volumes for existing
  installs upgrading in place (never done silently). Entrypoint now checks
  `MEDIA_ROOT` is writable before doing anything else and fails with a clear,
  `humanize_error`-derived message if not. See `docs/deployment.md`.
- **Phase 42** — Drive downloads of files >= `RESUME_MIN_MB` (default 50MB) now
  resume via HTTP Range instead of restarting from byte 0 after a dropped
  connection or a killed worker; the existing `.part`-then-atomic-rename convention
  is unchanged, so this needed no changes to any caller's error handling. Smaller
  files, and Google Docs/Sheets/Slides exports, keep the exact previous whole-file
  retry path. The weekly integrity task (Phase 31) now also removes `.part` files
  older than 7 days (never a fresh one — that's the safety margin, not a lock).
- **Phase 43** — two new soft, Redis-backed throttles on Drive downloads:
  `MAX_CONCURRENT_DOWNLOADS` (default 2, matching today's effective worker
  concurrency: `celery -c 2`) caps how many downloads run at once; `GOOGLE_API_MAX_RPS`
  (default 0, disabled) caps download calls per second. Both fail open if Redis is
  unreachable, and neither touches the existing 429/5xx exponential backoff
  (Phases 10-11). New `core/ratelimit.py`; wired into `services_google.py`'s three
  download entry points, the single choke point since Phase 42.
- **Phase 44** — CI: new `trivy-fs` job (filesystem/dependency vulnerability scan,
  SARIF, report-only) and a new SBOM step in the existing `trivy` job (`syft` via
  `anchore/sbom-action`, SPDX JSON, uploaded as the `sbom-spdx` build artifact).
  Both the new `trivy-fs` scan and the existing `trivy` image scan stay report-only
  (`exit-code: "0"`) until each has one clean run in this repo's own Actions
  history — do not flip either to fail-on-CRITICAL pre-emptively.
- **Phase 45** — rewrote `README.md` around user tasks (Install through Troubleshoot),
  with a platform matrix, an honest "no benchmarked hardware minimum" note (cites the
  compose file's actual resource limits instead), the storage-estimate formula (real
  field names from `core/storage.py`, no invented numbers), and an explicit
  backup-vs-sync-vs-archive-vs-cleanup distinction. Old terse README preserved as
  `docs/dev-quickstart.md` (now in the MkDocs nav). Fixed two stale Celery Beat
  tables in `docs/operations.md` that listed Drive/Photos/reconcile/purge tasks as
  scheduled — they aren't; only 3 tasks are ever automatic
  (`backend_django/celery_app.py` is the source of truth).
- **Phase 46** — new `docs/disaster-recovery.md` (what's recoverable, and how, for
  each of: lost server, lost `MEDIA_ROOT` only, lost database only, revoked token,
  compromised Google account) and `docs/upgrading.md` (backup-first upgrade steps,
  the non-root `fix-perms` one-timer, rolling back, diffing new `.env` vars). Both
  added to the MkDocs nav under a new "Operations" section, alongside
  `docs/operations.md` (previously missing from the nav entirely). New
  `scripts/gen_config_ref.py` walks every `config(...)` call in `backend_django/`
  and every `${VAR}` in `docker-compose.yml` via `ast`/regex and writes a generated,
  self-updating reference table into `docs/configuration.md` (`make config-ref` to
  regenerate, `make config-ref-check` to verify it isn't stale); the rest of
  `docs/configuration.md` was rewritten to match current defaults (several were
  stale — e.g. `DEBUG` defaults to `False`, not `True`) and gained a "Common
  mistakes" table. Fixed a real fresh-install bug found while writing the generated
  reference: `REDIS_PASSWORD` (required, no default in `docker-compose.yml`) was
  never added to `.env.sample`.
- **Phase 47** — new `.github/workflows/release.yml`: pushing a `vX.Y.Z` tag builds
  and pushes `ghcr.io/devadalberto/backdeezup:<tag>` (and `:latest`, for a real
  release only — never for a `-rcN` pre-release tag), gated on the repo-root
  `VERSION` file matching the tag, and creates a GitHub Release with that version's
  `CHANGELOG.md` section as its body. Release builds pin `python:3.12-slim` to a
  resolved digest via a new `PYTHON_BASE_IMAGE` Dockerfile `ARG`; `make build` is
  unaffected (unchanged floating-tag default). `docker-compose.yml`'s `web`,
  `celery`, and `celerybeat` services gained `image: ${BACKDEEZUP_IMAGE:-backdeezup:local}`
  alongside their existing `build: .` — set `BACKDEEZUP_IMAGE` in `.env` and
  `docker compose pull` to run a published image instead of building locally; unset,
  behavior is identical to before. New `docs/releases.md` documents cutting a
  release, testing the workflow with a pre-release tag, using a prebuilt image, and
  the GHCR package-visibility gotcha (a new package defaults to private). Flagged
  (not fixed — no release has actually been cut): `VERSION` (`0.10.1`),
  `pyproject.toml`'s `version` (`0.10.0`), and the newest `CHANGELOG.md` entry
  (`[0.10.0]`) don't agree with each other today.
- **Phase 48** — optional Caddy reverse-proxy profile: `docker compose --profile
  caddy up -d` (new `make caddy-up`/`make caddy-down`) starts a `caddy:2-alpine`
  service alongside nginx (which stays the default, unaffected — verified `docker
  compose config --services` lists the same 6 containers as before with no
  profile, and adds `caddy` as a 7th with `--profile caddy`). New `Caddyfile`
  mirrors nginx's two direct-serve locations (`/static/`, `/media/images/`) and
  reverse-proxies everything else to `web:8000`; defaults to `DOMAIN=localhost` +
  `CADDY_TLS_MODE=internal` (Caddy's own internal CA, same trust model as nginx's
  self-signed dev cert) so the profile works with zero config, or set a real
  `DOMAIN` + `CADDY_TLS_MODE=you@example.com` for automatic Let's Encrypt HTTPS.
  Verified live: `caddy validate` against both env combinations, and a real
  standalone run that obtained an internal-CA certificate and served HTTPS.
  `docs/deployment.md` gained a "nginx vs Caddy vs external reverse proxy"
  comparison section covering when to pick which.
- **Phase 49** — one-line installer and upgrade script, the final phase of the
  roadmap. `scripts/install.sh`: `curl -fsSL .../install.sh | bash` sets up a
  fresh install from the published image (Phase 47) with no git clone and no
  local build — fetches only what `docker compose` needs, generates
  `DJANGO_SECRET_KEY`/`GOOGLE_ENCRYPTION_KEY`/`POSTGRES_PASSWORD`/`REDIS_PASSWORD`
  locally (never printed in full), generates a self-signed cert, starts the
  stack, prints the setup-wizard URL. Prints every action; confirms before
  writing into a non-empty target or falling back to a source build if the
  image pull fails; `--dry-run` makes zero writes (verified). `scripts/upgrade.sh`
  (`make upgrade`): backup -> pull -> migrate -> up -> health-check-with-retry,
  printing exact rollback instructions (never rolling back automatically) if
  health fails; refuses to run over uncommitted changes in a git checkout.
  Both `shellcheck`-clean and verified with real `docker` runs, not just read
  for correctness.
  Two real, previously-unnoticed bugs found and fixed by that live testing,
  affecting every fresh install, not just this script: (1) `docker-compose.yml`
  declares `media` as an *external* volume that nothing in this repo ever
  created — `make up`/`make redeploy` now run `docker volume create
  backdeezup_media` first (safe to re-run); (2) `make up`/`make redeploy`
  started celery/celerybeat before running migrations, since those containers
  only wait on db/redis being healthy, not on migrations being applied —
  celerybeat crash-looped against a not-yet-migrated schema until it happened
  to retry successfully (self-healing, but confusing on first boot); fixed by
  migrating via `docker compose run --rm web ...` *before* `docker compose up
  -d` everywhere (`make up`, `make redeploy`, both new scripts, and
  `docs/upgrading.md`'s manual steps). Also fixed the Phase 41-flagged
  `accounts.0002_create_table_from_auth_user` migration, which unconditionally
  assumed a legacy `auth_user` table exists and broke `migrate` outright on any
  genuinely fresh database — now wrapped in a `to_regclass('auth_user') IS NOT
  NULL` guard so it's a no-op on a fresh install and unchanged for an upgrade
  from the legacy schema. `docs/deployment.md` gained a "One-line install"
  section; `docs/upgrading.md` gained the `make upgrade` path and the corrected
  migrate-before-up order.

## [0.10.0] - 2026-05-16

### Added
- **media_vault** Django app — Wagtail 7.4 LTS + wagtailmedia 0.17.2
  - Custom models: VaultImage, VaultDocument, VaultMedia (video/audio), VaultRendition, MediaDecision
  - All models link back to source (Drive asset or Gmail attachment)
  - `keep` field (True/False/None) on all media models for keep/delete decisions
  - Wagtail CMS admin at `/cms/`, document serve at `/documents/`, pages at `/vault/`
  - Media Vault section in top nav bar (Images, Documents, Videos & Audio)
- **Assumptions:** Django 5.2 (stable LTS) over 6.0; self-hosted video via wagtailmedia; Discord streaming deferred

## [0.9.0] - 2026-05-16

### Added
- **Smart Rule Builder** — `/admin/gmail/rule-builder/` visual compound rule editor
  - Conditions table: field, operator, value, AND/OR join per row
  - Real-time Gmail query preview (calls `/api/gmail/rule-builder/preview`)
  - Dry-run count before saving (DB-only, no Gmail API call)
  - Save as new CleanupRule with RuleCondition rows
  - 9 built-in templates: LinkedIn jobs, LinkedIn spam, job boards, recruiters, marketing tools, newsletters, no-reply, social old, promotions
- **RuleCondition model** — FK to CleanupRule, fields: field/operator/value/logic/order
  - Supports: sender, recipient, subject, body, label, category, has_attachment, age_days
  - Operators: contains, not_contains, equals, not_equals, starts_with, older_than, newer_than, is_true
- **query_compiler.py** — translates RuleCondition rows to Gmail `q=` syntax with AND/OR grouping
- **Global Matrix theme** — `backend_django/templates/admin/base_site.html` overrides Django Admin with phosphor green on black, applies to ALL admin pages
- **Top navigation bar** — sticky dropdown menus: Gmail, Drive, Pipeline, Admin
- **Export engine** — `/api/gmail/export/messages`, `/api/gmail/export/audit-log`, `/api/export/assets` supporting CSV, XLSX, JSON, XML, PDF
- **KPI dashboard** in Gmail ops console: Total messages, Verified %, Trashed, Rules active, Cleanup actions (auto-refreshes every 60s)
- **RuleCondition inline** in CleanupRule admin page

## [0.8.0] - 2026-05-15

### Added
- `ProtectedSender` model — emails from these addresses are always starred, labeled, and kept in inbox
- `CleanupRule` model — DB-backed cleanup rules with Gmail query, min_age_days, action, enabled flag
- `CleanupAuditLog` model — immutable append-only log of every cleanup action (dry-run or real)
- `services_rules.py` — rules engine: `apply_rule()`, `apply_protected_sender_rules()`, `run_all_enabled_rules()`
- `seed_rules` management command — seeds 4 protected family senders + 8 default cleanup rules (all disabled by default)
- APScheduler integration — incremental sync every 6h, protected senders every 6h, cleanup rules 3x/day at 06/12/18
- Scheduler toggle: `BACKDEEZUP_SCHEDULER=1` in `.env` (default off)
- API endpoints: `/api/gmail/rules`, `/api/gmail/rules/{id}/dry-run`, `/api/gmail/rules/{id}/execute`, `/api/gmail/rules/run-all`, `/api/gmail/protected-senders/apply`, `/api/gmail/audit-log`
- Admin: CleanupRule, ProtectedSender, CleanupAuditLog with dry-run and execute actions
- `make seed-rules` — run seed command inside container

### Protected senders seeded
- mony.bello@gmail.com, mony_littleowls@outlook.com, virlochov@gmail.com, julietvlhr@gmail.com — all starred + labeled "family"

### Default cleanup rules seeded (all disabled — review before enabling)
- Trash Promotions older than 30 days
- Trash Social notifications older than 30 days
- Trash Forums older than 60 days
- Trash Updates older than 30 days
- Trash newsletters (unsubscribe) older than 30 days
- Trash no-reply senders older than 60 days
- Trash mailing lists older than 60 days
- Trash spam folder older than 7 days

## [0.7.0] - 2026-05-15

### Added
- `GET /api/progress` endpoint — pipeline counts and percentage verified across all states
- `make sync-run` — full pipeline loop (download→import→verify) with ASCII progress bar
- `make preflight` — pre-flight checks: Docker, .env, no CHANGE_ME, google_client.json type `installed`
- `LIMIT` variable for all pipeline Makefile targets (default 100)
- graphify installed in Debian: `uv tool install graphifyy`, graph: 591 nodes, 657 edges
- `google_gmail_backup` Django app with full Gmail backup pipeline

### Fixed
- sync-run progress bar using `bash -c` to maintain function scope
- Drive query simplified (removed shortcut clause causing Google 500)
- Photos API pageSize capped at 100 (Google API limit)
- Gmail parse_date returns timezone-aware datetimes
- Gunicorn timeout increased to 300s
- OAuth: Desktop app client auto-detects redirect_uri from google_client.json
- OAuth callback URL registered in Django urls.py

### Known Issues
- Google Photos blocked project-wide — old web client has non-HTTPS redirect URIs

## [0.6.1] - 2026-05-15

### Fixed
- OAuth flow now works headless (no browser on server) — uses `urn:ietf:wg:oauth:2.0:oob` redirect, prints URL, prompts for code paste
- Gmail scopes (`gmail.readonly`, `gmail.modify`) merged into Drive/Photos SCOPES so one auth flow covers all services
- `services_gmail.py` now imports `_load_creds`, `_save_creds`, `SCOPES` from `services_google.py` (single source of truth)

### Added
- `make auth` — runs headless OAuth inside container with `-it` flag
- `docs/authentication.md` — full headless OAuth walkthrough with step-by-step instructions
- Authentication page added to MkDocs navigation

## [0.6.0] - 2026-05-15

### Added
- Comprehensive Makefile with targets for Docker, Django, Drive/Photos pipeline, Gmail pipeline, local dev, and WSL2 proxy
- `make help` shows all targets with descriptions
- `make redeploy` — one-command pull + build + restart + migrate
- `make wsl-proxy` — auto-detects WSL2 IP and sets Windows port proxy
- Pipeline targets support `HOST=` override (e.g. `make discover HOST=http://192.168.88.60:8844`)
- Updated deployment docs with full Makefile reference and Gmail pipeline steps

## [0.5.1] - 2026-05-14

### Changed
- `Dockerfile` — switched from pip + requirements.txt to uv for dependency installation; uses `ghcr.io/astral-sh/uv:latest` via COPY --from, `uv sync --frozen --no-dev`
- `requirements.txt` — regenerated from uv lockfile via `uv export`; now includes all pinned transitive deps and is always in sync with `pyproject.toml`

## [0.5.0] - 2026-05-14

### Added
- `admin_views.py` — `reports_view` (assets by state, top MIME types, totals, last 20 RunLog entries) and `ops_console` (one-click pipeline UI)
- `templates/admin/reports.html` — responsive grid dashboard with totals, state table, MIME types, recent runs
- `templates/admin/ops_console.html` — pipeline step buttons with shared limit input and live JSON output

### Fixed
- `admin.py` — removed `each_context` override that caused `RecursionError`; added `search_fields` and `readonly_fields` to all three admin classes; better action feedback messages
- `urls.py` — custom admin routes registered before `path("admin/")` (correct Django ordering); graceful `try/except` for optional `query_page` view

### Security
- Merged `dev/local-tests` branch discarding its `docker-compose.yml` (had hardcoded `app:app` credentials); main's env-var-driven version kept

## [0.4.2] - 2026-05-13

### Added
- `entrypoint.sh` — runs `collectstatic` then starts gunicorn at container start. Replaces build-time collectstatic so static files are always current.
- `secrets/.gitkeep` — ensures the secrets directory is tracked by git (contents git-ignored).
- Debian WSL2 environment: repo cloned at `/home/saitama/repos/github/devadalberto/backdeezup`.

### Changed
- `Dockerfile` — removed `COPY .env` and build-time `collectstatic`; now uses `entrypoint.sh` as CMD.
- `docker-compose.yml` — added `./secrets:/app/backend_django/secrets:ro` volume mount so OAuth credentials are injected at runtime, not baked into the image.
- `Makefile` — `migrate`, `superuser`, `shell` now run via `docker compose exec web`; `run` and `docs` remain local dev targets.
- `.env.sample` — fully updated with all current variables, inline generation commands, and `CHANGE_ME` placeholders.

## [0.4.1] - 2026-05-13

### Fixed
- `docker-compose.yml` — Postgres credentials now sourced from `.env` via `${POSTGRES_USER}`, `${POSTGRES_PASSWORD}`, `${POSTGRES_DB}`. Nothing hardcoded.
- `web` service `depends_on` upgraded to wait for db healthcheck before starting.

### Added
- README: full production deployment section with copy-paste `.env` scaffold (all secrets as `CHANGE_ME` placeholders), step-by-step deploy commands, static file notes, and ongoing ops reference.

## [0.4.0] - 2026-05-13

### Added
- **CI workflow** (`.github/workflows/ci.yml`) — runs on every push and PR to main:
  - Django system check + test suite (uv, Python 3.12, sqlite)
  - Playwright smoke test: confirms Swagger UI and Admin login load on localhost:8844
  - Uses `astral-sh/setup-uv` for fast dependency install
- **Playwright 1.59** added as a project dependency — headless Chromium installed and smoke-tested on WINWEB01

### Fixed
- All remaining broken Mermaid diagrams in `shared_context.md` — removed `\n` in node labels and Unicode arrows
- `gh-pages.yml` — added `enablement: true` to `configure-pages` step to auto-enable GitHub Pages (fixes all prior deploy failures)

### Changed
- `shared_context.md` — updated Playwright status to installed/working, added CI workflow reference, noted GitHub Pages manual activation requirement, corrected WSL status

## [0.3.0] - 2026-05-13

### Added
- Complete MkDocs Material documentation site with 10 pages: index, quickstart, configuration, installation, architecture, states, data model, API reference, deployment, contributing, changelog, acknowledgements
- Working Mermaid diagrams throughout docs and README (fixed for GitHub rendering)
- GitHub Actions workflow with separate build/deploy jobs and proper environment gating

### Changed
- All Mermaid diagrams: removed `\n` in node labels and transition text (broke GitHub renderer), removed non-ASCII arrows and checkmarks
- `mkdocs.yml`: renamed from `gmail_josevaldes_cleanup`, full Material theme config with dark/light mode, nav tabs, search, code copy
- `docs/handover.md`: fixed all Mermaid diagrams
- README: complete rewrite with working diagrams and modern quick start

## [0.2.0] - 2026-05-13

### Added
- **Modern Python tooling**: Migrated to `uv` (Rust-based package manager) for 10-100x faster dependency management
- **pyproject.toml**: Consolidated all dependencies and project metadata in PEP 621 format
- **Developer scripts**: Added `dev.sh` (Bash) and `dev.ps1` (PowerShell) helper scripts for common Django tasks
  - Commands: `dev`, `migrate`, `makemigrations`, `superuser`, `shell`, `test`, `docs`, `sync`, `add`
- **Project comparison document**: Comprehensive analysis comparing BackDeezUp with Gmail cleanup project (`docs/project-comparison.md`)
  - Feature matrix comparing 30+ dimensions
  - Detailed improvement roadmap to blend best features of both projects
  - Migration path for future enhancements (multi-account, cleanup rules, reporting, exports)
- **CHANGELOG.md**: This changelog following Keep a Changelog format with semantic versioning

### Changed
- **Django settings**: Fixed CORS and CSRF configuration to properly handle wildcard origins
  - `CORS_ALLOW_ALL_ORIGINS` now used instead of invalid `*` in origins list
  - `CSRF_TRUSTED_ORIGINS` properly filtered for non-wildcard values
  - `DEBUG` default changed to `True` for development
- **README.md**: Updated with modern uv-based workflow
  - Added uv quick start guide
  - Documented new development scripts
  - Highlighted modern tooling benefits (10-100x faster, automatic venv management, lock files)
  - Added note about legacy Makefile targets

### Fixed
- Django system check errors for CORS/CSRF configuration (4_0.E001, corsheaders.E013)
- Build backend configuration in pyproject.toml to recognize `backend_django` package

### Technical
- Dependencies locked in `uv.lock` for reproducible builds
- Virtual environment automatically managed by uv (`.venv/`)
- Build backend: Hatchling with proper package configuration

## [0.1.0] - 2026-05-12

### Added
- Initial Django project structure with `google_media_backup` app
- Google Drive and Photos API integration with OAuth authentication
- Core models: `MediaItem`, `DriveAsset`, `RunLog`
- Explicit 6-stage state machine: DISCOVERED → DOWNLOADED → IMPORTED → VERIFIED → DELETE_PENDING → DELETED
- Two-proof deletion safety: File exists on disk + DB record required before Drive deletion
- Django-Ninja REST API with Swagger/OpenAPI documentation at `/api/docs`
- SHA-256 hashing for media deduplication
- Fernet-encrypted token storage for OAuth credentials
- Docker Compose setup with PostgreSQL and Nginx
- MkDocs documentation site
- Makefile with common development tasks
- Knowledge graph via graphify (86 nodes, 104 edges, 24 communities)
- CLAUDE.md and GEMINI.md for AI agent collaboration

### Safety Features
- MIN_RETENTION_DAYS guard (default: 3 days) before Drive deletion
- Configurable deletion mode: trash (recoverable) or hard (permanent)
- State-based pipeline ensures no premature deletions
- Audit trail via RunLog model

[Unreleased]: https://github.com/devadalberto/backdeezup/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/devadalberto/backdeezup/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/devadalberto/backdeezup/releases/tag/v0.1.0
