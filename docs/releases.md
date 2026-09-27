# Releases

How a version of BackDeezUp gets built, published, and pulled — separate from
`docs/upgrading.md` (which is about moving an *existing* install forward, whether
it's running a self-built image or a published one).

---

## What happens when you push a tag

`.github/workflows/release.yml` runs on any pushed tag matching `v*` (Phase 47):

1. **Version gate.** The repo-root `VERSION` file must exactly equal the tag with its
   `v` prefix stripped (tag `v1.2.3` → `VERSION` must contain `1.2.3`). The job fails
   immediately if they don't match — bump `VERSION`, commit, delete the wrong tag,
   re-tag.
2. **Base image resolved to a digest.** `python:3.12-slim`'s current digest is
   resolved (`docker pull` + `docker inspect`) and passed as
   `--build-arg PYTHON_BASE_IMAGE=python:3.12-slim@sha256:...` — a release build is
   pinned to an exact base layer, unlike an everyday `make build`, which floats on
   the `3.12-slim` tag (unchanged, low-risk default).
3. **Build + push to GHCR.** Pushes `ghcr.io/devadalberto/backdeezup:<tag>` always;
   also tags and pushes `:latest`, but **only** for a real release tag (`vX.Y.Z`) —
   a pre-release tag (`vX.Y.Z-rcN`, detected by the presence of a `-`) never touches
   `:latest`.
4. **GitHub Release created.** Its body is the `CHANGELOG.md` section headed
   `## [X.Y.Z]` (the `v` and any `-rcN` suffix stripped first) — if no matching
   section exists yet (expected for an `-rc` tag cut ahead of the real entry), the
   release body says so explicitly instead of showing nothing. Marked `prerelease`
   automatically for any tag containing `-`.

---

## Cutting a release

1. Update `CHANGELOG.md`: turn `## [Unreleased]` into `## [X.Y.Z] - YYYY-MM-DD` (or
   add that heading above it for the next `[Unreleased]`).
2. `echo "X.Y.Z" > VERSION` — this **must** match the tag you're about to push, or the
   release job fails on purpose. `pyproject.toml`'s `version` field is not read by
   the release job today; keep it in sync by hand if you care about it matching (it
   is currently out of sync with `VERSION` in this repo — see "Known drift" below).
3. Commit those two files.
4. `git tag vX.Y.Z && git push origin vX.Y.Z`
5. Watch the **Release** workflow in GitHub Actions.

## Testing the workflow without cutting a real release

Push a pre-release tag on any branch, e.g. `git tag v1.2.3-rc1 && git push origin
v1.2.3-rc1` (still needs `VERSION` to contain `1.2.3-rc1` first). This exercises the
whole pipeline — version gate, digest resolution, build, push, release creation — and
marks the resulting GitHub Release as a pre-release, without touching `:latest`.
Delete the tag and the draft/pre-release afterward if it was only a workflow test:
```bash
git push --delete origin v1.2.3-rc1
git tag -d v1.2.3-rc1
gh release delete v1.2.3-rc1 --yes
```

---

## Using a prebuilt image instead of building

By default `make build` / `docker compose build` builds `web`, `celery`, and
`celerybeat` locally from this repo's `Dockerfile` and tags the result
`backdeezup:local` — nothing changes unless you opt in. To run a published image
instead:

```bash
# in .env
BACKDEEZUP_IMAGE=ghcr.io/devadalberto/backdeezup:v1.2.3
```
```bash
docker compose pull web celery celerybeat
docker compose run --rm web python manage.py migrate   # before up -- see docs/upgrading.md
docker compose up -d
```

`nginx`, `db`, and `redis` are unaffected — they already pull fixed public images
(`nginx:stable-alpine`, `postgres:16`, `redis:7-alpine`) and were never built locally.

A brand-new install using a published image, with no repo clone at all, is
`scripts/install.sh` (`docs/deployment.md` → "One-line install"); upgrading either
kind of install afterward is `scripts/upgrade.sh`/`make upgrade`
(`docs/upgrading.md`) — both Phase 49.

!!! note "GHCR package visibility"
    A newly-pushed `ghcr.io/devadalberto/backdeezup` package defaults to **private**
    on GitHub, even though the workflow that pushed it has `packages: write`. Pulling
    it without authenticating will fail until you make the package public once,
    manually, in the package's own Settings on GitHub (Actions tokens can push but
    can't change a package's visibility).

---

## Known drift

`VERSION` currently reads `0.10.1`; `pyproject.toml`'s `version` field reads `0.10.0`;
the newest dated `CHANGELOG.md` entry is `[0.10.0]`. None of the three has been kept
in lockstep so far. This isn't a problem for the release workflow itself — it only
ever checks `VERSION` against the tag you push — but it means today's `VERSION` file
doesn't correspond to anything actually released yet. Reconcile all three before
cutting the first real tag.
