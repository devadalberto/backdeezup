# BackDeezUp — Prompts & Playbook (2026-05-19)

Two sections in one file:
- **Part 1** — Raw session prompts (what was asked, in order)
- **Part 2** — Reusable playbook (step-by-step operations + copy-paste prompts)

---

## Part 1 — Session Prompts (2026-05-19)

What was asked during the full development session. Numbers preserved for reference.
Useful ones to reuse are marked **★**.

1. *(session resumed from prior context — see shared_context.md)*
2. Gmail progress stuck at 18.8% — why is it not moving forward?
3. What else is missing? Does it depend on the download?
4. **★** Take care of all priorities listed. Ensure all this can be done from the webpage too.
5. Where can I see the backup progress in the dashboard?
6. Still at 78% with no way to delete anything.
7. Clicked the button and confirmed — how do I see the execution status?
8. Fix the dry-run button — not showing any result.
9. Dry-run does not show any result after clicking.
10. Clicked dry-run, then Force Empty — nothing happening.
11. Fix the broken button again.
12. **★** Analyze as a team in a parallel task — ensure you learn what is making you not as efficient as you could be.
13. De-scope Google Photos — it keeps getting 403.
14. How to handle the blocked Photos scope?
15. Output is taking a while — how do I see what is going on? (logs)
16. Shit is breaking left and right — Photos 403 again.
17. **★** How does this start cataloging, reviewing, and cleaning up my inbox?
18. **★** Here is a screenshot of my inbox — most of it should be moved to a folder or trash. How is that happening now?
19. Options A and B for fixing the download are both failing.
20. **★** Chop the rule age thresholds — from 60 to 15 and from 30 to 5. Why wait 30 days for forums and spam?
21. **★** Research curated lists for Gmail cleanup rules — like awesome-docker but for inbox zero. Check agentic forums and the web.
22. **★** Consider methods like Pi-hole that use maintenance block lists. Next big chunk: attachments from me and family.
23. **★** Multiple email addresses I can't remember — farfer, farferkugel, farmaikamx and combinations. Catalog as 'farferkugel'. Get me the list first for confirmation. Want thumbnails in Wagtail and video streaming.
24. Also check category tag pelos, .Far-, far.maika.mx, farmaikamx.
25. Separate Monica and Maika — everything Maika goes to farferkugel tag.
26. Update tags: farferkugel → 'adalberto', juliet → 'julieta'.
27. Think about edge cases — what will happen when each hits?
28. **★** Investigate https://github.com/stashapp/stash — implement something similar for media management in Wagtail. Basics only: thumbnails and tags.
29. Option B — new Wagtail page type (Stash-style).
30. **★** Always follow best practices and track everything on a new branch.
31. **★** Add a theme configurator — amber/orange fonts preferred, include the blue from the logo, 4 themes, HUD-style switcher. Looks from the future. Separate branch.
32. **★** Media metadata needs to be wiped before storage, but saved somewhere first.
33. **★** Needless to say, always follow best practices: security, SDLC branch management, update graphify, update shared context and memory.
34. **★** Bring 3 pairs of eyes — Python master, Django jedi, and a god-mode programmer — to review the models. Make any Linux geek cry blood tears reading the most optimized and secure code. Iterate with test updates.
35. Have the tests updated.
36. Continue with the agent loop and previous tasks.
37. **★** In parallel, have agents acting as white-hat hackers auditing the whole application in a loop. Break when done.
38. Next big chunk: attachments specifically from me and family.
39. Also check category or tag pelos.
40. Merge order question — older to newer?
41. **★** Fix 3 issues: Gmail Dashboard duplicate title, DOWNLOADED fluctuating confusingly, loop keeps re-discovering.
42. **★** Bring the design expert — menus and pages should match the logo (3 colors, green dominant). What else is missing to run and leave it running?
43. Still at 78% with no delete path.
44. Logging is a basic security feature — why is nothing being logged?
45. **★** Analyze efficiency failures as a team.
46. Photos still getting 403.
47. De-scope Photos for now.
48. Output taking a while — dry-run showed 7293, then Force Empty deleted them all.
49. Want this running a few times a day filtering spam.
50. Inbox screenshot — rules confirmation.
51. Options A and B both failing.
52. Chop the thresholds again.
53. **★** Need to set up git config for multiple accounts.
54. Just want to know my SSH config.
55. Apply SSH config changes.
56. Why does DOWNLOADED go up and down?
57. **★** Can't reconcile the numbers. Also need disk usage percentage for Gmail.
58. How does cataloging, reviewing, and cleaning up work?
59. Inbox screenshot for rules.
60. Options A/B failing.
61. Chop thresholds.
62. **★** Research curated lists (second pass).
63. Next big chunk: attachments from family.
64. Git config setup.
65. SSH keys sorting.
66. Want all keys on all profiles.
67. Apply config changes.
68. Use vertex automation key, not devadalberto.
69. Explain the freelance-launch repo structure.
70. With git information on top.
71. Why is the git remote not under the org?
72. Handle freelance-launch repo creation.
73. **★** Give me a prompt to tell another Claude session to follow the same shared_context and AI conventions.
74. Update the prompt — wrong directory path.
75. Convert the prompt to freelance-launch.
76. Current working path question.
77. Explain git accounts to another Claude chat.
78. How does cataloging and cleanup work?
79. **★** Bring 3 pairs of eyes — models review with graphify. (Second pass.)
80. Think about edge cases creatively.
81. Have tests updated.
82. Continue agent loop.
83. **★** Recommend CI/CD pipeline with Docker Compose including first-class security scans — all containerized.
84. **★** Full loop audit — architecture to implementation. Re-think and re-implement if needed. New branch. Best practices.
85. WSL config needs to be updated — 2 procs, 8GB max. Update all files.
86. Efficiency retrospective.
87. Photos 403 again.
88. **★** If a respected authority checked the stack, what would they criticize and why?
89. **★** Replace APScheduler with Celery, add TLS, move to secrets manager, add Sentry. TLS is localhost for now.
90. Must pull first before make gen-certs exists.
91. Took option B — certs generated. Now what?
92. Should I proceed with the PR now?
93. **★** How to install/trust a self-signed cert.
94. **★** Copy certs to Windows and install them everywhere they need to be. Document the path and type.
95. **★** Why are there still 60d and 30d rules? Did you not apply the changes? Action column should use blue.
96. README still talks about APScheduler — update all documents.
97. Registered 2FA.
98. **★** Start CI/CD pipeline with security scanning, 100% containerized. Configure autostart on WINWEB01 VM boot.
99. **★** How do I verify I'm in the right state?
100. **★** Update all documents, shared context, memory, and graphify. Full ops manual README.
101. **★** Create a file with all prompts from this session.

---

## Part 2 — Reusable Playbook

---

## 1. Start a new AI session

Before giving any task to Claude/Gemini/Codex, paste this as your first message:

```
You are working on backdeezup — a self-hosted Django backup platform for Google
Drive/Gmail/Photos with a Wagtail media vault.

Before doing anything:
1. Read shared_context.md in the repo root — single source of truth for the
   entire project (stack, conventions, SSH, pipeline status, all URLs, AI rules)
2. Read graphify-out/GRAPH_REPORT.md for the codebase map

Repo: C:\Users\Administrator\repos\github\devadalberto\backdeezup (Windows)
      /home/saitama/repos/github/devadalberto/backdeezup (Debian WSL)
Remote: git@github-dev:devadalberto/backdeezup.git
Git identity: devadalberto / devadalberto@gmail.com
Current version: v0.11.0
```

---

## 2. First deploy on a new machine

```bash
# Clone
git clone git@github-dev:devadalberto/backdeezup.git
cd backdeezup

# Configure environment
cp .env.sample .env
# Edit .env — fill every CHANGE_ME value

# Generate Django secret key
python3 -c "import secrets; print(secrets.token_urlsafe(50))"

# Generate Fernet key (exactly 44 chars)
python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# Copy Google OAuth credentials (Desktop app / installed type)
cp '/mnt/c/Users/Administrator/Downloads/client_secret_*_(1).json' \
   secrets/google_client.json

# Verify client type — must print 'installed'
python3 -c "import json; d=json.load(open('secrets/google_client.json')); print(list(d.keys())[0])"

# Generate TLS certs
make gen-certs

# Trust cert on Windows (PowerShell as Administrator)
certutil -addstore -f "ROOT" nginx/certs/server.crt

# Pre-flight check
make preflight

# Build and start
make build && make up && make migrate && make superuser

# Authenticate with Google
make auth
# Opens URL → browser → page fails to load (expected) → copy full URL → paste back

# Seed rules and vault
make seed-rules
make seed-inbox-rules
make vault-setup
```

---

## 3. Standard upgrade (after merging a PR)

```bash
# On Debian
git pull origin main
make redeploy

# If rules changed
make seed-rules
make seed-inbox-rules
```

---

## 4. Gmail backup pipeline

### Initial full backup

```bash
# Step 1 — discover all message IDs
make gmail-discover

# Step 2 — download + verify in a loop until done
make gmail-loop LIMIT=500 WORKERS=10

# Check progress
make gmail-progress
# or visit: https://localhost:8445/admin/gmail/dashboard/
```

### Monitor progress

Prompt to use:
```
Show me the current Gmail backup progress. Query the DB and tell me:
- How many messages per state (DISCOVERED/DOWNLOADED/VERIFIED/TRASHED/DELETED)
- What percentage is complete
- How many are still pending download
- Any errors in recent messages
```

### When download stalls (DISCOVERED = 0 but progress stuck)

```bash
# Check what's in each state
docker compose exec web python manage.py shell --verbosity 0 -c "
from google_gmail_backup.models import GmailMessage
from django.db.models import Count
for r in GmailMessage.objects.values('state').annotate(n=Count('id')).order_by('-n'):
    print(r['state'], r['n'])
"
```

---

## 5. Empty Gmail trash

1. Go to `https://localhost:8445/admin/gmail/ops/`
2. Scroll to **Empty Gmail Trash**
3. Click **Dry-run** — see count in Output panel
4. Click **Force Empty Trash (skip guard)** → confirm → done

Or via API:
```bash
# Dry-run first
curl -sk -X POST "https://localhost:8445/api/gmail/ops/empty-trash?dry_run=true&skip_backup_check=true" \
  -H "X-CSRFToken: $(cat /tmp/csrf_token)" \
  -b "sessionid=$(cat /tmp/session_id)"
```

---

## 6. Gmail cleanup rules

### Seed / update rules

```bash
make seed-rules          # 15 core rules (5d/15d thresholds)
make seed-inbox-rules    # 12 inbox-specific rules
```

### Execute rules

1. Go to `https://localhost:8445/admin/gmail/ops/`
2. Click **Dry-run All Enabled Rules** — review counts in Output
3. If counts look right: **Execute All Enabled Rules**

### Add a new rule (prompt)

```
Add a new cleanup rule to seed_inbox_rules.py that:
- Name: [descriptive name]
- Matches: [gmail query]
- Action: trash / label / archive
- Min age: [N] days
- Enabled by default

Then run make seed-inbox-rules to apply it.
```

### Current rule thresholds

| Category | Min age | Action |
|---|---|---|
| Promotions, Social, Updates | 5 days | trash |
| Forums, No-reply, Mailing lists | 15 days | trash |
| Spam folder | 0 days | trash |
| E-commerce confirmations | 90 days | archive |
| Banking/financial | 0 days | archive |

---

## 7. Extract family media attachments

```bash
# Count what would be extracted (safe — no files written)
make gmail-extract-attachments-dry

# Extract images and videos from family .eml files
make gmail-extract-attachments

# Push extracted attachments to Wagtail vault
make import-media ARGS="--source gmail"

# Browse the vault
# https://localhost:8445/vault/gallery/
```

### Import Drive media to vault

```bash
make import-media ARGS="--source drive"

# Or all sources
make import-media
```

---

## 8. Identity groups (family media tagging)

| Tag | Who | Email |
|---|---|---|
| `adalberto` | Jose (you) | jose.valdes@gmail.com + 10 variants |
| `monica` | Monica | mony.bello@gmail.com |
| `little-owls` | Little Owls School | monica_littleowls@outlook.com |
| `emiliano` | Emiliano | virlochov@gmail.com |
| `julieta` | Julieta | julietvlhr@gmail.com |

Filter gallery by person: `https://localhost:8445/vault/gallery/?person=adalberto`

---

## 9. Celery (background jobs)

```bash
# Monitor workers
make celery-logs

# Check active tasks
make celery-status

# Clear queue (careful)
make celery-purge
```

Periodic schedule (edit at `/admin/django_celery_beat/periodictask/`):
- Gmail incremental sync: every 6 hours
- Protected sender rules: every 6h + 30min
- Cleanup rules: 06:00, 12:00, 18:00 daily

---

## 10. Re-authenticate with Google

```bash
# Delete stale token
rm secrets/google_token.json

# Re-run OAuth
make auth
# Opens URL → browser → copy full redirect URL → paste back
```

Required when:
- Token is missing or corrupted
- New scopes need to be added
- `403 insufficient authentication scopes` error

Current required scopes: `drive`, `drive.readonly`, `gmail.readonly`, `gmail.modify`, `https://mail.google.com/`

---

## 11. Unblock Google Photos

Photos are currently blocked by an old web OAuth client in the project.

1. Go to [Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients)
2. Find and delete the client ending in `1ql0o9aj`
3. Add `photoslibrary.readonly` back to `SCOPES` in `services_google.py`
4. Delete token: `rm secrets/google_token.json`
5. `make auth`
6. `make discover-photos`

---

## 12. TLS certificate management

### Generate (first time or renewal)

```bash
make gen-certs
# Creates nginx/certs/server.crt and server.key
# Valid 10 years for localhost, WINWEB01, 192.168.88.60
```

### Trust on Windows (run PowerShell as Administrator)

```powershell
certutil -addstore -f "ROOT" "C:\Users\Administrator\repos\github\devadalberto\backdeezup\nginx\certs\server.crt"
```

### Trust on Firefox

Go to `https://localhost:8445` → Advanced → Accept the Risk and Continue

---

## 13. Autostart after VM reboot

Everything is already configured. On WINWEB01 reboot:

```
Windows boots → login → Startup folder bat runs
→ wsl -d Debian starts
→ systemd starts backdeezup.service
→ docker compose up -d
→ all 6 containers running
```

Check status after reboot:
```bash
# On Debian
systemctl status backdeezup.service
make ps
```

Reinstall autostart if needed:
```bash
# Debian service
sudo bash scripts/autostart.sh

# Windows bat (copy to startup folder)
cp scripts/windows-autostart.bat \
   "$APPDATA/Microsoft/Windows/Start Menu/Programs/Startup/backdeezup-autostart.bat"
```

---

## 14. Monitoring and diagnostics

```bash
make logs              # all container logs
make celery-logs       # celery worker + beat only
make ps                # container status

# Gmail progress
make gmail-progress

# Drive progress
make progress

# Django shell
make shell

# Full system check
make check
```

### Useful shell queries

```bash
docker compose exec web python manage.py shell --verbosity 0 -c "
from google_gmail_backup.models import GmailMessage, CleanupAuditLog
from django.db.models import Count

# Pipeline state breakdown
for r in GmailMessage.objects.values('state').annotate(n=Count('id')).order_by('-n'):
    print(r['state'], r['n'])

# Last 5 cleanup actions
for a in CleanupAuditLog.objects.order_by('-started_at')[:5]:
    prefix = '[DRY]' if a.dry_run else '[LIVE]'
    print(prefix, a.rule_name, '->', a.affected_count, 'affected', '|', a.status)
"
```

---

## 15. Running tests

```bash
make test-full        # ruff lint + all 59 unit tests

# Tests only (no lint)
DATABASE_URL="" DJANGO_SECRET_KEY=ci-test-key \
  uv run python backend_django/manage.py test \
  google_media_backup google_gmail_backup media_vault --verbosity=2

# Single test class
DATABASE_URL="" DJANGO_SECRET_KEY=ci-test-key \
  uv run python backend_django/manage.py test \
  google_gmail_backup.tests_regression.OnclikAmpersandTest --verbosity=2
```

---

## 16. Git workflow

```bash
# Start a feature
git checkout main && git pull origin main
git checkout -b feat/my-feature

# Before committing
DATABASE_URL="" DJANGO_SECRET_KEY=ci-test-key \
  uv run python backend_django/manage.py check

# Before opening PR
make test-full

# After merging to main — update graphify
wsl -d Debian bash -c "
  cd ~/repos/github/devadalberto/backdeezup
  git pull origin main
  ~/.local/bin/graphify update .
  git add graphify-out/
  git commit -m 'chore: graphify update'
  git push origin main
"
```

---

## 17. Sentry setup

1. Create account at [sentry.io](https://sentry.io)
2. New Project → Django → copy DSN
3. Edit `.env`:
   ```
   SENTRY_DSN=https://your-dsn@sentry.io/project-id
   SENTRY_ENVIRONMENT=production
   ```
4. `make redeploy`

Errors and Celery task failures will appear in your Sentry dashboard automatically.

---

## 18. Add a second Google account

When ready to add farmaikamx / farferkugel accounts:

```
Add a second Google account to backdeezup.
The new account email is [EMAIL].
It should be configured as a second sync account alongside jose.valdes@gmail.com.
The identity tag for this account should be 'adalberto' (same as the primary).
Add its addresses to IDENTITY_GROUPS in extract_attachments.py.
```

---

## 19. Security audit prompt (reusable)

```
Act as a white-hat security auditor. Review the backdeezup Django application
for vulnerabilities. Read these files:
- backend_django/config/settings.py
- backend_django/google_gmail_backup/api.py
- backend_django/media_vault/api.py
- backend_django/media_vault/views.py
- nginx/nginx.conf
- docker-compose.yml

Look for: path traversal, IDOR, CSRF gaps, secret leakage, rate limiting gaps,
missing auth on endpoints, unsafe file handling, Docker misconfigurations.

Return findings grouped CRITICAL / HIGH / MEDIUM / LOW with file:line,
description, proof of concept, and exact fix.
```

---

## 20. Model review prompt (reusable)

```
Review all Django models in this project as a Python expert + Django DBA.
Read graphify-out/GRAPH_REPORT.md first, then:
- backend_django/google_gmail_backup/models.py
- backend_django/google_media_backup/models.py
- backend_django/media_vault/models.py

Check: TextChoices usage, null=True on CharFields, missing __str__,
missing indexes, N+1 risks, missing DB constraints, JSONField validators,
abstract mixins to DRY up repeated patterns, custom managers.

Return specific file:line findings with before/after code. Prioritize by
performance impact on 32k-message dataset.
```

---

## 21. End-of-session housekeeping prompt

```
Before we finish this session:
1. Run make test-full and confirm all tests pass
2. Run graphify update . on Debian and commit graphify-out/
3. Update shared_context.md with any pipeline status changes, new conventions,
   or architecture decisions made this session
4. Update memory files in the memory/ directory if new patterns were discovered
5. Push all branches and open PRs for any completed features
6. Tell me: what's the state of the app, what's pending, and what to run next
```

---

## Key URLs reference

| URL | Purpose |
|---|---|
| `https://localhost:8445/admin/` | Django Admin |
| `https://localhost:8445/admin/gmail/dashboard/` | Gmail progress |
| `https://localhost:8445/admin/gmail/ops/` | Gmail ops + empty trash |
| `https://localhost:8445/admin/gmail/rule-builder/` | Rule builder |
| `https://localhost:8445/admin/ops/` | Drive ops |
| `https://localhost:8445/admin/vault/ops/` | Vault ops |
| `https://localhost:8445/vault/gallery/` | Gallery |
| `https://localhost:8445/vault/review/` | Media triage |
| `https://localhost:8445/cms/` | Wagtail CMS |
| `https://localhost:8445/admin/django_celery_beat/` | Celery schedule |
| `https://localhost:8445/admin/django_celery_results/` | Task history |
| `https://localhost:8445/api/gmail/progress` | Progress JSON |
| `https://localhost:8445/api/docs` | Drive API Swagger |
| `https://localhost:8445/api/gmail/docs` | Gmail API Swagger |

---

## Common errors and fixes

| Error | Cause | Fix |
|---|---|---|
| `403 Insufficient Permission on batchDelete` | Token missing `mail.google.com` scope | Delete token + `make auth` |
| `CSRF check Failed` on API | Using curl against session-auth endpoint | Use management commands instead |
| `redis.connection` error in tests | Tests trying to hit real Redis | Add `@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})` |
| `Fernet key must be 44 chars` | Bad `GOOGLE_ENCRYPTION_KEY` | Generate: `python3 -c "import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` |
| `error: cannot pull with rebase: unstaged changes` | Graphify-out modified | `git add graphify-out/ && git stash && git pull --rebase && git stash pop` |
| `docker compose ps` shows no containers | Containers not started | `make redeploy` |
| Gmail rules still showing 30d/60d | Old rule names not updated | `make seed-rules` (now matches by gmail_query not name) |
| `OAUTHLIB_INSECURE_TRANSPORT` error | Running OAuth without TLS | Expected for localhost dev — handled in code |
