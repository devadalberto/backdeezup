/goal implement phase N  <-- type this to execute a phase

================================================================
GOAL: Complete Gmail backup, fix sync/reconciliation, run cleanup,
      unblock Photos, merge CI/CD, populate vault, release FOSS.
================================================================

PHASE 0 -- Orient
  Preflight + stack health check. Read shared_context + graph.
  Confirm all 6 containers healthy before touching anything.

PHASE 1 -- Resume Gmail backup
  Run gmail-loop until all ~32,463 messages are DOWNLOADED+VERIFIED.
  Monitor progress at /admin/gmail/dashboard/.

PHASE 2 -- Gmail sync & reconciliation (CRITICAL FIX)
  Fix incremental sync to detect trash/delete from Gmail side.
  Add SOFT_DELETED state + deleted_at + retention (90d keep, then purge).
  Build full reconciliation task: compare local DB vs live Gmail, update states.
  Preserve all metadata forever in audit log before any purge.
  After this phase: if you delete in Gmail, the DB knows within 6 hours.

PHASE 3 -- Gmail cleanup
  Enable targeted rules, dry-run each, execute. Check audit log.
  Run protected-senders apply first (family emails always safe).

PHASE 4 -- Unblock Photos
  Delete old OAuth client 1ql0o9aj from Google Auth Platform.
  Re-auth (make auth). Run Photos discovery + download pipeline.

PHASE 5 -- Merge CI/CD branch
  Merge feat/ci-cd-autostart into main after test-full passes.
  Confirm autostart service still enabled post-merge.

PHASE 6 -- Populate vault
  Extract Gmail attachments (family images/video from .eml).
  Import Drive + Gmail media into Wagtail vault.
  Triage at /vault/review/ (K/D/S/Z).

PHASE 7 -- Wrap-up
  Update shared_context.md + memory files.
  Run graphify update. Commit everything.

PHASE 8 -- Human-operable FOSS release
  The project must run forever without Claude. A stranger on GitHub
  should be able to clone, configure, and operate it from the README alone.
  Claude exits. Cron and the human take over.

================================================================
TOOLS
  make preflight          -- ALWAYS run first
  make test-full          -- lint + 59 tests (before every PR/merge)
  /security-review        -- Phase 4 before merge
  /verify                 -- live stack spot-check
  graphify update .       -- after code changes
================================================================
