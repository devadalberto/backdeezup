# Contributing

Contributions are welcome. This project is worked on by Claude, Gemini CLI, and Codex in parallel alongside human contributors.

---

## Getting started

```bash
git clone https://github.com/devadalberto/backdeezup.git
cd backdeezup
uv sync
cp .env.sample .env
./dev.sh migrate
```

---

## Development workflow

```bash
# Start the dev server
./dev.sh dev

# Run tests
./dev.sh test

# Add a dependency
./dev.sh add <package-name>

# Django shell
./dev.sh shell
```

PowerShell equivalents: `.\dev.ps1 <command>`

---

## Code conventions

- **No unnecessary comments.** Only add one when the *why* is non-obvious.
- **No premature abstractions.** Three similar lines beats a helper that has one caller.
- **No backward-compatibility shims.** If something is unused, delete it.
- **Settings via env only.** All config via `python-decouple` / `.env`. Never hardcode.
- **State machine is append-only.** Each endpoint only processes its expected input state. Never skip a state.
- **Safety first.** The two-proof guard and retention guard must never be weakened without explicit operator intent.

---

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **PATCH** `0.0.x` — bug fixes, no API changes
- **MINOR** `0.x.0` — new features, backward-compatible
- **MAJOR** `x.0.0` — breaking changes

### Release process

```bash
# 1. Update CHANGELOG.md — move [Unreleased] items to a new version section
# 2. Bump VERSION file and pyproject.toml
# 3. Commit
git add CHANGELOG.md VERSION pyproject.toml
git commit -m "chore: release vX.Y.Z"

# 4. Tag
git tag -a vX.Y.Z -m "Release vX.Y.Z"

# 5. Push
git push origin main --tags

# 6. GitHub Release
gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."
```

---

## Knowledge graph

After structural code changes, update the graphify knowledge graph so all AI agents stay in sync:

```bash
graphify update .
```

---

## AI agent coordination

The `shared_context.md` file is the canonical ground truth shared between Claude, Gemini CLI, and Codex. Update it whenever:

- Architecture changes
- New models are added
- API endpoints change
- Tech stack changes

---

## Pull requests

- Keep PRs focused on a single concern
- Update `CHANGELOG.md` under `[Unreleased]`
- Run `./dev.sh test` before submitting
- Reference the relevant issue or context
