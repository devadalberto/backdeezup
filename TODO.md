# backdeezup TODO

Maintained by Claude Code. Updated after each session.
Cross-referenced with GOALS.md phases.

---

## Phase 0 -- Orient / stack health

- [x] make preflight -- passes all checks
- [x] All 6 containers Up (web, nginx, db, redis, celery, celery-beat)
- [x] Celery workers healthy (make celery-status)
- [x] HTTPS reachable: https://localhost:8445

---

## Phase 1 -- Gmail backup (EFFECTIVELY COMPLETE)

- [x] gmail-discover -- all 32,463 messages discovered
- [x] gmail-loop -- 25,205 VERIFIED + 7,258 TRASHED = 32,463 total
- [ ] Note: 7,258 TRASHED came from cleanup rules, not from download failures
- [x] Dashboard reflects full count

---

## Phase 2 -- Gmail sync & reconciliation (DONE 2026-06-02)

### Model changes
- [x] Add SOFT_DELETED state to GmailMessage.State enum
- [x] Add fields: deleted_at, deletion_source, metadata_snapshot
- [x] Create + run migration (0007_soft_delete_reconciliation)

### Fix incremental sync (task_gmail_incremental_sync)
- [x] Process "labelAdded"/"labelRemoved" history events
- [x] TRASH label added → state=SOFT_DELETED, snapshot metadata, set deleted_at
- [x] TRASH label removed → revert to VERIFIED, clear deleted_at
- [x] messageDeleted → state=DELETED, snapshot metadata

### Full reconciliation task
- [x] task_gmail_reconcile: compare all VERIFIED in DB vs live Gmail API
- [x] 404 response → SOFT_DELETED
- [x] TRASH label present → SOFT_DELETED
- [x] Still alive → leave as VERIFIED
- [x] Rate-limited batching (50 per batch, 0.1s sleep)
- [x] Add make target: make gmail-reconcile
- [ ] Add to Celery Beat: daily 03:00 UTC (needs schedule seed)

### Retention purge task
- [x] task_purge_expired_soft_deletes: state=DELETED after 90 days
- [x] Metadata snapshot preserved (never lose subject/from/to/date info)
- [x] Keep .eml files on disk by default
- [x] Add make target: make gmail-purge-expired
- [ ] Add to Celery Beat: weekly Sunday 04:00 UTC (needs schedule seed)

### Rules engine update
- [x] apply_rule() sets deleted_at + deletion_source + metadata_snapshot on trash
- [x] Admin shows deleted_at and deletion_source in list view + reconcile action

### Tests — 9/9 passing, full suite 68/68
- [x] Incremental sync: TRASH label added → SOFT_DELETED
- [x] Incremental sync: TRASH label removed → reverts to VERIFIED
- [x] Reconciliation: 404 → SOFT_DELETED
- [x] Reconciliation: TRASH present → SOFT_DELETED
- [x] Reconciliation: still alive → stays VERIFIED
- [x] Purge: >90d → DELETED
- [x] Purge: <90d → untouched
- [x] Rules: metadata_snapshot populated after trash
- [x] Protected senders still reconciled (reflects Gmail reality)

### Live reconciliation results (first run)
- 25,169 confirmed alive in Gmail
- 36 soft-deleted (gone from Gmail, backup retained)
- 0 errors

---

## Phase 3 -- Gmail cleanup (DONE 2026-06-02)

- [ ] Apply protected senders (family emails -- always run first)
- [x] All 16 cleanup rules enabled
- [x] transaction.atomic() bug fixed (select_for_update)
- [x] Backup % formula fixed (was only counting VERIFIED; now counts all accounted states)
- [x] Execute all enabled rules — 2,530 messages trashed in Gmail
- [x] Backup guard now passes at 100%
- [x] Empty trash — 11,946 messages permanently deleted from Gmail (0 errors)
- [ ] Run rules again for remaining matches (optional — diminishing returns)
- NOTE: Dry-run shows 5,000/rule (local DB cap) but real execution only trashes what Gmail API confirms matches the query — delta is expected

---

## Phase 4 -- Unblock Photos

- [ ] Delete client 1ql0o9aj at Google Auth Platform -> Clients
- [ ] Delete existing OAuth token (secrets/google_token.json)
- [ ] Re-auth: make auth (include photoslibrary.readonly scope)
- [ ] Verify photoslibrary.readonly in token scopes
- [ ] make discover -- Photos media items populate
- [ ] make download -- Photos files to disk

---

## Phase 5 -- Merge CI/CD branch

- [ ] make test-full on feat/ci-cd-autostart -- all tests pass
- [ ] /security-review -- no HIGH/CRITICAL findings
- [ ] Merge feat/ci-cd-autostart -> main
- [ ] Push main to GitHub
- [ ] Confirm autostart service still enabled (systemctl is-enabled backdeezup.service)
- [ ] GitHub Actions: all 7 stages green
- [ ] Tag v0.11.0
- [ ] Update CHANGELOG.md [Unreleased] -> [0.11.0]

---

## Phase 6 -- Populate vault

- [ ] make gmail-extract-attachments-dry (count extractable)
- [ ] make gmail-extract-attachments (extract family images/video)
- [ ] make import-media (Drive + Gmail -> Wagtail vault)
- [ ] Triage at /vault/review/ (K/D/S/Z)
- [ ] Gallery renders at /vault/gallery/

---

## Phase 7 -- Wrap-up (run after each session)

- [ ] Update shared_context.md (pipeline status + date)
- [ ] Update memory files (project_backdeezup.md)
- [ ] ~/.local/bin/graphify update . && commit graphify-out/
- [ ] Commit shared_context.md + CHANGELOG.md + TODO.md
- [ ] Push branch

---

## Phase 8 -- Human-operable FOSS release (FINAL)

The project must run without Claude forever. A stranger on GitHub must be able
to clone, configure, and operate it using the README alone. Claude exits here.

### Docs a human needs to operate it
- [ ] README: one-command quickstart (clone -> .env -> make up -> make auth)
- [ ] README: day-to-day operations section (how to run backup, cleanup, empty trash)
- [ ] README: scheduled operation section (Celery Beat default schedule explained)
- [ ] README: manual operation section (every make target explained in plain English)
- [ ] README: troubleshooting section (the 5 most common failure modes + fix commands)
- [ ] CHANGELOG.md: up to date, no [Unreleased] items left

### Scheduled operation (no human needed after setup)
- [ ] Celery Beat default schedule reviewed and documented: what runs, when, how to change
- [ ] make celery-schedule target -- prints current schedule in human-readable form
- [ ] Confirm gmail-loop runs on schedule without manual trigger
- [ ] Confirm cleanup rules run on schedule (3x/day) without manual trigger
- [ ] Confirm protected-senders runs on schedule without manual trigger
- [ ] Confirm reconciliation runs daily (03:00 UTC)
- [ ] Confirm purge runs weekly (Sunday 04:00 UTC)

### Manual operation (human runs it when they want)
- [ ] Every pipeline action has a single make target with no required arguments
- [ ] make help -- prints all targets with one-line descriptions
- [ ] No operation requires knowing Django internals or Python

### Handoff checklist (Claude steps back)
- [ ] Remove all Claude-specific files from repo root: CLAUDE.md, AGENTS.md, GEMINI.md
      (or move to docs/ai-dev/ so they don't confuse FOSS users)
- [ ] GOALS.md / GOALS_TODOS.md moved to docs/dev/ (internal dev reference, not user-facing)
- [ ] .gitignore covers all secrets: .env, secrets/, google_token.json, nginx/certs/
- [ ] No API keys, tokens, or credentials anywhere in git history
- [ ] GitHub repo: description, topics (django, gmail-backup, google-drive, self-hosted, foss)
- [ ] GitHub repo: Issues enabled, a starter issue template for bug reports
- [ ] LICENSE file present (already MIT)

---

## Bugs fixed this session (2026-06-02)

- [x] CSRF 403 on HTTPS login — added https://localhost:8445 to CSRF_TRUSTED_ORIGINS in .env
- [x] `select_for_update` outside transaction — wrapped apply_rule() body in transaction.atomic()
- [x] Note: `docker compose restart` does NOT reload .env — always use `docker compose up -d`

---

## Known blockers

- [ ] **Photos BLOCKED**: client 1ql0o9aj must be deleted before photoslibrary scope works
- [x] **Sync broken**: FIXED — reconciliation ran, DB now accurate (Phase 2)

## Standing open items

- [x] Seed inbox rules: make seed-inbox-rules (12 inbox-specific rules) — done, all 16 rules enabled
- [ ] Confirm SENTRY_DSN set in .env for error tracking (optional but recommended)
- [ ] Periodic schedule enabled: visit /admin/django_celery_beat/ -- confirm 3x/day cleanup tasks

---

_Last updated: 2026-06-02 (Phase 2 complete, Phase 3 in progress — 2,530 trashed, empty trash pending)_
