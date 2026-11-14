# GOALS_DONE.md -- backdeezup completed-phase archive
# Full detail for finished phases, moved out of GOALS.md to keep it under the
# 1000-line limit. No line limit here. Dispatcher: GOALS.md. Runbooks: GOALS_TODOS.md.

================================================================

PHASE 55 -- Fix broken CI (lint, sast-bandit, test jobs all failing) (DONE -- via PHASES 57 + 63)
  Surfaced when the CI badge was added to README; confirmed still failing on
  current HEAD (commit 7a9a275, run 36363155626, inspected via `gh run view
  --log-failed`) -- not a flake, three independent root causes:
    1. lint -- 25 real `F401` unused-import violations across the codebase
       (e.g. `core.setup.views` in tests_setup_wizard2.py:15, `django.utils.timezone`
       in google_gmail_backup/admin.py:94, several unused model imports in
       tests_smoke.py). Auto-fixable: `ruff check backend_django/ --select E,F,W
       --ignore E501,E701,E702 --fix`.
    2. sast-bandit -- FIXED (confirmed root cause, 2026-09-27). `bandit.sarif`
       came out malformed/truncated ("Invalid SARIF. JSON syntax error:
       Unexpected end of JSON input") at the upload-sarif step. Confirmed via
       the "Run Bandit SAST" step's own output (not the upload step): bandit
       itself errors out ("unrecognized arguments: backend_django/core/migrations
       ..."), because `-x backend_django/**/migrations` is unquoted in the
       workflow -- the runner's `sh` glob-expands `**` into 4 separate paths
       before bandit sees them, only the first is consumed by `-x`, the rest
       become invalid positional args, bandit exits nonzero, `|| true` hides it,
       and `bandit.sarif` never gets written. Not the suspected zero-findings
       SARIF-formatter bug -- disproven; quoting alone fixes it and findings
       are non-zero (22 at `--severity-level medium`). Fix: quote the value --
       `-x "backend_django/**/migrations"` -- verified locally with
       `uv tool run --with 'bandit[sarif]' bandit ...` against this exact repo
       (valid JSON, 22 results, zero touching migrations).
    3. test -- exit 137 (OOM-killed) on the `test` job's container, AND 6 test
       modules fail to even import as `_FailedTest`: google_media_backup's
       tests_resumable_download + tests_unit, google_gmail_backup's
       tests_cleanup_safeguards + tests_notify_wiring + tests_schemas +
       tests_undo_protect. Partially diagnosed 2026-09-27: the `_FailedTest`
       placeholders are emitted at discovery time, but their real tracebacks
       only print in unittest's end-of-run summary, which this run never
       reaches because the OOM kill happens first -- so the traceback text is
       unobtainable from any existing CI log. A scoped local run of exactly
       those 6 modules together passes cleanly (exit 0), so the failure isn't
       intrinsic to those files alone -- it only shows up as part of the full
       two-app suite. The raw log also shows a second, unexplained
       `wagtailusers.0015` migration-apply appearing mid-suite (only one test
       DB is ever created), right before the kill -- a lead pointing at
       something re-triggering DB setup mid-run, not a confirmed cause.
       Getting the real evidence needs a run that survives to print the
       summary (i.e., more memory / a run on PDX-CL1) -- this repo's local dev
       box cannot safely run the full two-app suite (WSL) and can't reach
       Google Drive/Gmail anyway, so this step's remaining diagnosis and fix
       happen on PDX-CL1, not here.
       MAJOR FINDING 2026-09-28 (confirmed live on PDX-CL1): with `DATABASE_URL=`
       cleared to force the SQLite path, the run got past everything CI ever
       showed and hung indefinitely (not crashed) at `ProtectedSenderReconcileTest
       .test_protected_sender_still_soft_deleted_on_404` -- a genuine infinite
       loop, verified by reproducing `MagicMock()` pagination behavior in an
       isolated shell: `task_gmail_reconcile()` paginates on `res.get("nextPageToken")`,
       but this test (and 3 siblings in the same file) mock `svc` without
       configuring `.list()`, so that call returns a permanently-truthy `MagicMock`
       and the loop never breaks -- a very plausible match for the OOM (no sleep,
       unbounded `mock_calls` growth per iteration). Not a production bug. Fixed: PHASE 57.
       ROOT CAUSE CONFIRMED 2026-09-28 (after Phase 57 deployed): a full local run
       on PDX-CL1 (`DATABASE_URL=` cleared) now completes cleanly in 5s -- "Ran 74
       tests ... OK (skipped=2)" -- confirming Phase 57's infinite loop was the
       entire OOM story. But CI's own run on this same commit still fails the
       `test` job (`gh run 36452103678`), now FAST (45s, no OOM) with real
       tracebacks finally visible (the OOM used to prevent them from ever
       printing): all 6 modules fail with the identical `ModuleNotFoundError: No
       module named 'pytest'`. Confirmed by reading each file: all 6 are genuine
       pytest-native tests (`@pytest.mark.django_db`, `@pytest.fixture`,
       `@pytest.mark.unit`, `tmp_path`/`monkeypatch` fixtures) -- not
       unittest.TestCase-based like the rest of the codebase. `pyproject.toml`
       already has a fully-configured `[tool.pytest.ini_options]` section and a
       declared `test` optional-dependency group (`pytest`, `pytest-django`,
       `pytest-cov`, `pytest-mock`) -- but CI's `test` job's `uv sync` (no
       `--extra test`) never installs it, and CI never runs `pytest` at all.
       These 6 files have likely never actually executed in CI, ever. Verified
       locally: `uv sync --extra test` + `uv run pytest <the 6 files> -v` --
       65 passed, 0 failed, 7.69s. Fix: PHASE 63.
  Full detail + required diagnostic steps before each fix: GOALS_TODOS.md.

PHASE 56 -- Fix `make gmail-loop` ignoring WORKERS= (XS) (DONE)
  Confirmed live: user set a bigger `WORKERS=` value (12-vCPU/36GB VM, Phase 53
  follow-up) and `gmail-loop` kept using 10. Root cause confirmed by reading the
  code, not guessed: `make gmail-download` correctly passes `--workers $(WORKERS)`
  to `gmail_pipeline download` (Makefile:407), but `gmail-loop`'s own download
  call (Makefile:424) never forwards `--workers` at all, so it silently falls
  back to the management command's own hardcoded `default=10`
  (`gmail_pipeline.py:23`) no matter what `WORKERS=` is set to on the command
  line. `gmail-loop`'s `verify` call has no `--workers` flag to begin with (not
  a bug -- `verify` doesn't take one, confirmed by reading its `add_arguments`).
  Fix: add `--workers $(WORKERS)` to `gmail-loop`'s download line, matching
  `gmail-download` exactly. One line, no behavior change for anyone who doesn't
  override `WORKERS=` (still defaults to 10). Full detail: GOALS_TODOS.md.

PHASE 57 -- Fix infinite loop in 4 task_gmail_reconcile tests (under-mocked `.list()`) (XS-S) (DONE)
  Found live on PDX-CL1 while diagnosing Phase 55 Step 3's OOM: with
  `DATABASE_URL=` cleared (SQLite, matching CI), the full test run hung
  indefinitely at `ProtectedSenderReconcileTest
  .test_protected_sender_still_soft_deleted_on_404`. Confirmed root cause:
  `task_gmail_reconcile()` (`tasks.py:283-293`) paginates via
  `page_token = res.get("nextPageToken"); if not page_token: break`, but 4
  tests in `tests_reconciliation.py` (`Reconcile404Test`, `ReconcileTrashLabelTest`,
  `ReconcileMessageAliveTest`, `ProtectedSenderReconcileTest`) mock `svc` as a
  bare `MagicMock()` without configuring `.list()` -- verified empirically that
  `MagicMock().get("nextPageToken")` returns a permanently-truthy `MagicMock`,
  so the loop never terminates. No production bug (real API responses are real
  dicts). Fix: configure `.list()`'s return value (`{"messages": [],
  "nextPageToken": None}`) in each of the 4 tests before calling
  `task_gmail_reconcile()`. Test-only change. Full detail: GOALS_TODOS.md.

PHASE 58 -- Fix nginx's HTTP->HTTPS redirect hardcoding port 8445 (S) (DONE)
  Found live on PDX-CL1: its `docker ps` shows nginx published on
  `127.0.0.1:18844->80/tcp, 127.0.0.1:18445->443/tcp` (customized via
  `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT` in its `.env`), but `nginx/nginx.conf:13`'s
  redirect is `return 301 https://$host:8445$request_uri;` -- a literal `8445`,
  not driven by any variable. `docker-compose.yml:122` bind-mounts
  `nginx.conf` as a static, unmodified file (`./nginx/nginx.conf:/etc/nginx/nginx.conf:ro`)
  -- no substitution happens on it at all, even though `docker-compose.yml:127-128`
  DOES correctly read `NGINX_HTTPS_PORT` for the port mapping itself. Confirmed
  impact: anyone hitting PDX-CL1's `http://<host>:18844/` gets redirected to
  `https://<host>:8445/...`, a port nginx isn't even listening on for this
  deployment (not in its published ports at all) -- the request just fails.
  Docker's port remapping is transparent to the container, so nginx has no way
  to know the externally-published HTTPS port without being told explicitly --
  no nginx-variable trick (`$server_port`, `$http_host`, etc.) can substitute
  for this, since HTTP and HTTPS use *different* custom host ports here.
  Fix: make `nginx.conf` a template that reads `NGINX_HTTPS_PORT` at container
  start, since the official nginx image's built-in template auto-processing
  (`/etc/nginx/templates/*.template` -> `/etc/nginx/conf.d/*.conf`) doesn't fit
  our case -- we replace the *entire* nginx.conf (worker_processes/events/http
  wrapper), not a conf.d fragment. Instead: rename `nginx/nginx.conf` ->
  `nginx/nginx.conf.template` (hardcoded `8445` -> `${NGINX_HTTPS_PORT}`), mount
  the template instead of the static file, pass `NGINX_HTTPS_PORT` as an env var
  to the nginx service, and override its `command` to run `envsubst` before
  starting nginx:
      command: ["/bin/sh", "-c", "envsubst '$$NGINX_HTTPS_PORT' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"]
  (the `$$` escapes docker-compose's own interpolation so the shell/envsubst
  sees a literal `$NGINX_HTTPS_PORT`). Default unchanged (`8445`) for anyone
  not overriding it. Verify: `docker compose config` shows the new command/env,
  then start the stack and confirm `curl -I http://localhost:$NGINX_HTTP_PORT/`
  redirects to the *actual* published `NGINX_HTTPS_PORT`, not 8445 -- test both
  the default and a custom-port override. Full detail: GOALS_TODOS.md.

PHASE 59 -- Fix Makefile ops commands hardcoding port 8844/8845 (ignoring custom ports) (S) (DONE)
  Found live on PDX-CL1 (same deployment, right after Phase 58's port fix):
  `make gmail-progress` failed with `python3 -m json.tool`'s confusing
  "Expecting value: line 1 column 1 (char 0)" -- traced to `curl -s` silently
  returning zero bytes because it hit the WRONG, unbound port.

  Facts confirmed by reading the Makefile (not guessed):
    - `HOST ?= http://localhost:8844` (Makefile:292) -- hardcoded, doesn't read
      `.env`'s `NGINX_HTTP_PORT`/`NGINX_HTTPS_PORT`. 9 targets use `$(HOST)` in
      a curl call: `progress`, `sync-download`, `sync-run` (3 calls inline),
      `sync-import`, `sync-verify`, `sync-mark-delete`, `sync-commit-delete`,
      `gmail-incremental`, `gmail-progress`.
    - None of those curl calls pass `-S` (only `-s`), so a real connection
      failure produces zero output with NO error message -- confirmed this is
      exactly what happened on PDX-CL1 (port 8844 isn't published on this
      deployment at all; nothing in its `docker ps` output listens there).
    - `check-services` (Makefile:204,212) hardcodes literal ports `8845`/`8844`
      directly (not even via a variable) for its own port-bound/HTTP-response
      diagnostic checks -- same gap, worse (no override possible at all today).
    - This is the THIRD recurrence of the same pattern this session: Phase 56
      (`gmail-loop` ignoring `WORKERS=`), Phase 58 (nginx hardcoding the
      redirect port), now the ops-command layer.
    - `HOST`'s default is plain `http://`, matching `make run`'s bare dev
      server (no nginx, no TLS) -- but the actual docker-compose deployment
      fronts everything through nginx with a self-signed cert (Phase 58's
      redirect goes exactly there), so hitting the HTTP port on a real
      deployment costs an extra redirect hop `curl` won't follow without `-L`,
      and the HTTPS endpoint needs `-k` for the self-signed cert (already the
      documented convention elsewhere -- `docs/api.md`/`URL_INDEX.md` both
      say `curl -k https://localhost:8445/...`).

  Fix:
    1. Compute `HOST` once, at Makefile-parse time, from `.env` if present,
       falling back to today's defaults if not (so a plain git checkout with
       no `.env` yet, or the standard un-customized install, behaves exactly
       as today):
         NGINX_HTTPS_PORT := $(shell grep -E '^NGINX_HTTPS_PORT=' .env 2>/dev/null | tail -1 | cut -d= -f2)
         NGINX_HTTPS_PORT := $(if $(NGINX_HTTPS_PORT),$(NGINX_HTTPS_PORT),8445)
         HOST ?= https://localhost:$(NGINX_HTTPS_PORT)
       (Switches the default scheme from `http` to `https` -- going straight
       to the real endpoint instead of relying on an unfollowed redirect.
       `WORKERS=`/`LIMIT=`-style override still works: `make gmail-progress
       HOST=...` continues to take precedence via `?=`.)
    2. Add `-k` to every one of the 9 `$(HOST)`-using curl calls (matches the
       project's own documented convention for hitting this self-signed-cert
       endpoint elsewhere), and change `-s` to `-sS` on all of them so a real
       failure prints curl's actual error instead of silently feeding
       `json.tool` zero bytes.
    3. `check-services`: replace the hardcoded `8845`/`8844` literals with the
       same `.env`-read pattern (`WEB_PORT`/`NGINX_HTTP_PORT`, defaults
       unchanged), so its own diagnostic actually checks the ports this
       deployment is really using.
    4. `docs/operations.md`: add a short note that these ops commands
       auto-detect `.env`'s ports, so a customized deployment doesn't need
       manual `HOST=` overrides for routine use.

  Verify: `make -n gmail-progress` (dry-run) with no `.env` present shows the
  unchanged default `https://localhost:8445` (behavior-preserving check, since
  `.env` doesn't exist in this git checkout); construct a throwaway `.env`
  with `NGINX_HTTPS_PORT=18445` and confirm the same dry-run now shows
  `https://localhost:18445` -- delete the throwaway `.env` after. Full
  end-to-end proof (an actual working `make gmail-progress` against a real
  custom-port deployment) needs to happen on PDX-CL1, same as Phase 58.
  Full detail: GOALS_TODOS.md.

PHASE 60 -- Fix tqdm crash breaking cleanup-dry, cleanup-run, and real empty-trash (S) (DONE)
  Found live: `make cleanup-dry` crashed immediately with `TypeError: string
  indices must be integers, not 'str'`. Confirmed root cause by reproducing
  the exact error in an isolated Python shell (not guessed) and empirically
  verifying the fix before writing any code.

  Facts confirmed:
    - `run_cleanup.py` and `empty_gmail_trash.py` both build a custom tqdm
      `bar_format` referencing `{postfix[msgs]}` / `{postfix[d]}` -- treating
      `postfix` as if it stays a subscriptable dict inside the format string.
      It doesn't: tqdm converts `postfix` to a plain string (e.g. `"msgs=42"`)
      the moment it's used for display -- confirmed via `pbar.format_dict['postfix']`
      returning a str, not a dict. `"msgs=42"["msgs"]` -> exactly the observed
      `TypeError`. This crashes on the VERY FIRST `tqdm(...)` construction
      (inside its own initial `refresh()`), before the loop body ever runs.
    - There's a SECOND, latent bug the obvious one-line fix would walk
      straight into: both files also do `pbar.postfix["msgs"] = value` /
      `pbar.postfix["d"] = value` mid-loop, mutating `pbar.postfix` as if it
      stays a dict -- but it's already been converted to a string by the
      first `refresh()`, so this ALSO raises (`'str' object does not support
      item assignment`), confirmed by reproducing this second error too,
      separately, before finalizing the fix.
    - Impact, confirmed live: `make cleanup-dry` and `make cleanup-run` (both
      go through `run_cleanup.py`) are completely, unconditionally broken --
      100% reproducible, not intermittent. `make gmail-empty-trash-dry` is
      NOT affected (it returns early, before ever reaching the tqdm block,
      confirmed by reading `empty_gmail_trash.py`'s control flow) -- but the
      REAL execution path (`make gmail-empty-trash`, once `--confirm`'d) goes
      straight through the same broken tqdm block and would crash too,
      confirmed by reading the code (not yet triggered live, since the user
      hasn't run the real delete yet).
    - This blocks the exact next thing the user is trying to do: dry-run then
      execute the newly-seeded 20 cleanup rules, and eventually empty the
      already-8976-message Gmail trash for real.

  Fix (verified empirically in an isolated shell before writing the code):
    - `bar_format`: replace `{postfix[msgs]}` / `{postfix[d]}` with plain
      `{postfix}` (drop the redundant literal `msgs=`/`deleted=` text --
      tqdm's own postfix string already includes the key name, e.g. `"msgs=42"`).
    - Mid-loop update: replace `pbar.postfix["msgs"] = value; pbar.set_postfix(pbar.postfix)`
      with the correct keyword-argument API, `pbar.set_postfix(msgs=value)`
      (same for `empty_gmail_trash.py`'s `d` key). Verified this exact
      corrected pattern runs a full loop with no exception.
    - Also drop the now-redundant `postfix={"msgs": 0}` / `postfix={"d": 0}`
      constructor kwarg (no longer needed once `bar_format` doesn't reference
      it before the first `set_postfix()` call).

  Verify: `make cleanup-dry` completes without a traceback and prints real
  per-rule affected counts (confirms both `run_cleanup.py`'s tqdm bugs are
  actually fixed, not just the constructor-time one). Since the real delete
  path in `empty_gmail_trash.py` can't be safely tested here (irreversible,
  real Gmail data, no live stack on this dev box), verify that one by reading
  the corrected code against the same pattern already proven fixed in
  `run_cleanup.py`, and let the user confirm on PDX-CL1 when they actually
  run `make gmail-empty-trash` for real. Full detail: GOALS_TODOS.md.

PHASE 61 -- Fix ops console Output panel: not collapsible, grows unbounded and drags the page (XS-S) (DONE)
  Found live on `/admin/gmail/ops/`: the "▶ Output" header is a static
  unicode glyph inside a plain `<b>` tag -- no `onclick`, no `<details>`/
  `<summary>`, confirmed by grepping the whole file (zero matches for
  "details"/"summary"). Looks clickable, does nothing. Separately, `<pre
  id="out">` has no `max-height`/`overflow`, and its container is
  `position:sticky` -- so as output grows (e.g. a 20-rule dry-run's JSON),
  the box's own height grows unbounded and, being sticky, visibly drags the
  page around. Fix: replace the static `<b>` with a real `<details open>`/
  `<summary>` (native, accessible, free expand/collapse triangle, no JS
  needed) and add `max-height:320px;overflow-y:auto;` to `<pre id="out">` so
  long output scrolls within its own fixed box instead of growing the
  sticky container. Template-only, no backend change. Full detail: GOALS_TODOS.md.

PHASE 62 -- Fix django_ratelimit's Ratelimited returning raw Django 403 instead of clean JSON (XS-S) (DONE)
  Found live: clicking "Execute" on a cleanup rule returned a raw, unstyled
  "403 Forbidden" page with no explanation. Confirmed byte-for-byte this is
  Django's own generic `permission_denied` fallback page (rendered locally
  and compared character-for-character) -- meaning `django_ratelimit`'s
  `Ratelimited` exception (a `PermissionDenied` subclass, raised by the 4
  `@ratelimit(...)`-decorated endpoints in `api.py`, all on `gmail_api`) is
  unhandled by Ninja and falls through to Django's default error handling
  instead of a clean JSON response. Very likely the user genuinely hit the
  `10/h` execute limit (or `3/h` run-all limit) from extensive testing this
  session -- the rate limit itself is a reasonable safety feature; the bug
  is purely the broken error presentation. Fix: register one
  `@gmail_api.exception_handler(Ratelimited)` returning a clean `429` JSON
  body (`{"error": "Rate limit exceeded. Please wait before trying again."}`)
  -- covers all 4 rate-limited endpoints at once. Verified working end-to-end
  with `ninja.testing.TestClient` against a throwaway API instance before
  writing the real code. Full detail: GOALS_TODOS.md.

PHASE 63 -- Wire pytest into CI so it actually runs the 6 pytest-native test files (S) (DONE)
  Completes Phase 55: the `test` job's real remaining failure
  (`ModuleNotFoundError: No module named 'pytest'` on 6 files) is fully
  diagnosed -- these are genuine pytest-native tests (fixtures, `django_db`/
  `unit` markers) that `pyproject.toml` already declares a `test` optional-
  dependency group for (`pytest`, `pytest-django`, `pytest-cov`,
  `pytest-mock`) and a full `[tool.pytest.ini_options]` config for -- but
  CI's `test` job's `uv sync` never installs that group, and CI never
  invokes `pytest` at all. These 6 files have likely never actually run in
  CI. Verified locally: `uv sync --extra test` + `uv run pytest <the 6
  files> -v` -> 65 passed, 0 failed, 7.69s.
  Fix: in `.github/workflows/ci.yml`'s `test` job, change `uv sync` ->
  `uv sync --extra test`, and add one more step after the existing
  `manage.py test` step, running `pytest` scoped to exactly the 6 files
  (not a bare `pytest` across `backend_django/` -- that would also
  re-collect and re-run every unittest.TestCase-based file `manage.py test`
  already covers, doubling CI time for no benefit):
      - name: Run tests (pytest-native)
        run: |
          uv run pytest \
            backend_django/google_media_backup/tests_resumable_download.py \
            backend_django/google_media_backup/tests_unit.py \
            backend_django/google_gmail_backup/tests_cleanup_safeguards.py \
            backend_django/google_gmail_backup/tests_notify_wiring.py \
            backend_django/google_gmail_backup/tests_schemas.py \
            backend_django/google_gmail_backup/tests_undo_protect.py \
            -v
  The workflow-level `env:` block (DJANGO_SECRET_KEY, DATABASE_URL: "", etc.,
  lines 9-13) already applies to every step in every job -- no new env vars
  needed for this step.
  Verify: `gh run list --workflow=ci.yml --limit 1` shows a fully green run
  (lint, sast-bandit, AND test all passing) on the commit carrying this fix
  -- this is Phase 55's own original verify step, finally achievable. Full
  detail: GOALS_TODOS.md.

PHASE 64 -- Fix core/storage.py crashing when MEDIA_ROOT doesn't exist yet (XS) (DONE)
  Found live: pushing Phase 63 triggered a real CI run of the new pytest
  step -- 64/65 passed, 1 failed:
  `google_media_backup/tests_resumable_download.py::test_task_photos_download_batch_passes_db_size_bytes_as_size_hint`
  -- `FileNotFoundError: [Errno 2] No such file or directory:
  '/__w/backdeezup/backdeezup/backend_django/media'`. This is a real bug the
  new CI step immediately caught, not a flaw in Phase 63's wiring -- passed
  locally only because this dev box happens to already have a stray
  `backend_django/media/` directory sitting around from earlier session
  activity, masking it.
  Root cause, confirmed by reading the code: `core/storage.py:24`'s
  `usage()` calls `shutil.disk_usage(settings.MEDIA_ROOT)` with no check
  that the directory exists first. `MEDIA_ROOT` defaults to `BASE_DIR /
  'media'` (`config/settings.py:158`). In the real Docker deployment this
  is masked -- `docker-compose.yml`'s `media:` named volume auto-creates
  its mount point directory the first time it's attached, even before any
  file is ever downloaded -- but a bare `manage.py`/`pytest` run with no
  Docker volume involved (exactly what CI does, and what a local dev
  environment would do before Docker is ever brought up) has no such
  guarantee. This task is called from
  `google_media_backup/tasks.py:58`'s `task_photos_download_batch`, which
  the storage guard (Phase 32) checks before every download batch --
  meaning the very first download task on a sufficiently fresh install
  (outside the lucky Docker-volume side effect) could crash before
  downloading anything.
  Fix: in `core/storage.py`'s `usage()`, ensure `MEDIA_ROOT` exists before
  calling `shutil.disk_usage()` on it (`os.makedirs(settings.MEDIA_ROOT,
  exist_ok=True)`) -- matches Django's own convention elsewhere in this
  codebase of creating storage directories defensively rather than
  assuming they exist. No test-file change needed; this is a real
  production-code gap, not a test-environment workaround.
  Verify: delete/rename `backend_django/media/` locally (or just test in a
  scratch checkout that never had one), re-run the exact failing test --
  confirm `usage()` no longer crashes and the test passes. Then confirm the
  scoped full pytest run (all 6 files, same as Phase 63's verification)
  passes cleanly. Full detail: GOALS_TODOS.md.

PHASE 65 -- Fix compose-smoke CI job: missing external "backdeezup_media" volume (XS) (DONE)
  Found live: after Phase 64 shipped, `lint`/`sast-bandit`/`test` all went
  green (Phase 55's original goal, confirmed via `gh run view --json
  status,conclusion,jobs`) -- but the overall run still showed `failure`
  because `compose-smoke` failed. Confirmed unrelated to anything from this
  session: `git log -S "external: true" -- docker-compose.yml` shows the
  `media:` volume was marked `external: true` in commit `3f83107` ("fix:
  mark backdeezup_media as external volume to suppress WARN on docker
  compose up"), which predates every phase from this session (50-64).
  `compose-smoke` has likely been broken since that commit.

  Facts confirmed by reading the actual CI log (`gh run view --log-failed`)
  and the workflow file:
    - The exact failure: `external volume "backdeezup_media" not found` on
      `docker compose up -d --build`, then `##[error]Process completed with
      exit code 1`.
    - `docker-compose.yml`'s `volumes:` section (bottom of file) declares
      `media: external: true` -- Compose will never create this volume
      itself; something has to run `docker volume create backdeezup_media`
      first.
    - `Makefile`'s `up:` target already does this correctly:
        up:
            @docker volume create backdeezup_media >/dev/null   # external volume -- Compose never creates it for you; safe to re-run
            docker compose up -d
    - `.github/workflows/ci.yml`'s `compose-smoke` job (line 204) replicates
      most of `make up`'s setup manually (writes `.env`, generates a
      self-signed cert, creates dummy Google client secrets) but its "Start
      full Docker Compose stack" step (line 271-272) is a bare
      `docker compose up -d --build` -- it never runs the volume-create
      step at all.

  Fix: add `docker volume create backdeezup_media` (matching the Makefile's
  own comment: "external volume -- Compose never creates it for you; safe
  to re-run") as its own step, or prepended to the existing "Start full
  Docker Compose stack" step, right before `docker compose up -d --build`
  in `.github/workflows/ci.yml`'s `compose-smoke` job.

  Verify: `gh run list --workflow=ci.yml --limit 1` shows `compose-smoke`
  passing (or at least progressing past the volume-creation step -- the
  job has several further smoke-test steps after it that were never
  reached and have not been verified independently; if one of those fails
  next, diagnose it separately with real log evidence rather than assuming
  this one fix closes the whole job). This dev box has no live compose
  stack to test the fix against directly -- CI itself is the verification
  environment for this one. Full detail: GOALS_TODOS.md.
  RESULT confirmed 2026-09-28 (run 36463420169): Phase 65's fix genuinely
  worked -- `compose-smoke` got past volume creation and the healthy-wait
  step this time (new progress, not seen before). It hit a DIFFERENT,
  previously-unseen failure further along. See PHASE 66.

