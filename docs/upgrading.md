# Upgrading

Pulling new code into an existing install. For losing data and getting it back, see
`docs/disaster-recovery.md`. For the DB backup/restore commands this page depends on,
see `docs/operations.md`. This page assumes a self-built image (`make build`); if
you're running a published `ghcr.io/devadalberto/backdeezup` image instead
(`BACKDEEZUP_IMAGE` in `.env`), upgrading means `docker compose pull` to a newer tag
instead of `git pull` + `make build` — see `docs/releases.md`.

---

## The easy way: `scripts/upgrade.sh` (Phase 49)

```bash
make upgrade
```
Runs the whole sequence below as one script: backs up the database, pulls
(`git pull` for a self-built checkout, `docker compose pull` if `BACKDEEZUP_IMAGE`
is set), migrates, starts the stack, and polls `/health/` until it responds —
printing exact rollback instructions (the backup file, the previous commit or
image tag) if it doesn't, rather than rolling back automatically. Confirms
before pulling/restarting (`-y`/`--yes` to skip, for automation); `--dry-run`
prints the plan and runs nothing. Refuses to run over uncommitted local changes
in a git checkout. Works the same way against an `scripts/install.sh`-created
directory (`docs/deployment.md`) — pass `--dir PATH` for either.

## The steps by hand, every time

```bash
make db-backup                                          # 1. back up first — see below
git pull origin main                                    # 2. pull
make build                                               # 3. rebuild the image
docker compose run --rm web python manage.py migrate   # 4. migrate BEFORE starting --
                                                          #    celery/celerybeat only wait
                                                          #    on db/redis being healthy,
                                                          #    not on migrations, so
                                                          #    starting first can
                                                          #    crash-loop celerybeat
                                                          #    against a stale schema
make up                                                  # 5. start the stack
```

Or all at once, minus the backup: `make redeploy` runs steps 2-5 in that same,
migrate-before-up order. It does **not** run `make db-backup` first — take the
backup yourself before running it (or just use `make upgrade` above, which does).

### Why back up first

Migrations in this repo are ordinary Django migrations — most are additive (new
column, new table) and reversible, but nothing enforces that a future one won't
transform or drop data. `make db-backup` takes seconds and costs nothing; skipping it
before `make migrate` risks losing everything if a migration goes wrong. See
`docs/operations.md` → "Database Backup / Restore" for `make db-restore` if it does.

### After `make up`, check the health page

`https://localhost:8445/health/` should be all green. If it isn't, check
`make celery-status` and `make logs` before assuming the upgrade broke something —
containers can take a few seconds to report healthy after `docker compose up -d`.

---

## One-time step: upgrading onto the non-root image (Phase 41)

If your install predates Phase 41, the container's `media`/`staticfiles` Docker
volumes are still owned by `root` from the old image. The new image runs as
`appuser` (uid/gid `10001`) and can't write to them until you re-own them **once**:

```bash
make fix-perms   # chowns media/ + staticfiles/ volumes to uid:gid 10001
make up
```

Skipping this is safe to *attempt* — the entrypoint refuses to start with a clear
permission-denied message instead of a confusing crash, so nothing is destroyed if
you forget. Just run `make fix-perms` and `make up` again. See `docs/deployment.md`
for the `--build-arg NONROOT=0` escape hatch back to a root image, if you need it.

---

## New `.env` variables after an upgrade

Every phase that added a setting also added it to `.env.sample` with a default that
preserves the previous behavior — an upgrade should never silently change behavior.
Compare your `.env` against the current `.env.sample` after a `git pull` that touched
`.env.sample`:

```bash
git diff HEAD@{1} HEAD -- .env.sample
```

Or check the full, generated list of every variable the code reads at
`docs/configuration.md` (regenerate it yourself with `make config-ref` if you're
checking out a specific commit rather than trusting the committed copy).

---

## Rolling back

There is no `make rollback`. If `make upgrade` failed its health check, it already
printed the exact commands for your situation (previous commit or image tag, and
the backup file it took right before pulling). By hand, to go back to a previous
version:

```bash
git checkout <previous-tag-or-commit>
make build && make down && make up
make db-restore FILE=backups/<the dump you took before upgrading>
```

Only restore the DB dump if the new version's migrations actually changed the schema
in a way the old code can't read — check `git log -- backend_django/*/migrations/`
between the two versions first. If nothing migrated, `git checkout` + rebuild is
enough on its own.

---

## Upgrade checklist

Covered automatically by `make upgrade` except the `fix-perms` one-timer:

- [ ] `make db-backup` run and the dump verified present in `./backups/`
- [ ] `git pull origin main` (or `make redeploy`/`make upgrade`, which include this)
- [ ] `make fix-perms` if this install predates Phase 41 and hasn't run it before
- [ ] `make build`
- [ ] Migrate **before** starting: `docker compose run --rm web python manage.py migrate`
- [ ] `make up`
- [ ] `/health/` all green
- [ ] `.env` diffed against `.env.sample` for any new variables (see above)
- [ ] `make celery-status` shows workers active
