# Installation

---

## Option A — uv (recommended)

[uv](https://docs.astral.sh/uv/) is a Rust-based Python package manager — 10-100x faster than pip with automatic virtual environment management.

### Install uv

=== "Linux / macOS"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows (PowerShell)"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

### Clone and sync

```bash
git clone https://github.com/devadalberto/backdeezup.git
cd backdeezup
uv sync
```

Verify:

```bash
uv run python backend_django/manage.py --version
# 6.x.x
```

---

## Option B — Docker

Requires [Docker Desktop](https://docs.docker.com/get-docker/).

```bash
git clone https://github.com/devadalberto/backdeezup.git
cd backdeezup
docker compose build
docker compose up -d
docker compose exec web python backend_django/manage.py migrate
docker compose exec web python backend_django/manage.py createsuperuser
```

See [Deployment](deployment.md) for full production setup.

---

## Option C — pip

```bash
git clone https://github.com/devadalberto/backdeezup.git
cd backdeezup
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python backend_django/manage.py migrate
```

---

## Google Cloud setup

### Enable APIs

In your Google Cloud project enable:

- Google Drive API
- Google Photos Library API

### Create OAuth credentials

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > OAuth client ID**
3. Application type: **Desktop app**
4. Download JSON and save as `secrets/google_client.json`

### OAuth consent screen scopes

Add these scopes to your consent screen:

| Scope | Purpose |
|---|---|
| `https://www.googleapis.com/auth/drive.readonly` | Read Drive files |
| `https://www.googleapis.com/auth/drive` | Move files to trash |
| `https://www.googleapis.com/auth/photoslibrary.readonly` | Read Photos items |

!!! note "Test users"
    While in testing mode, add your Google account under **OAuth consent screen > Test users**.

---

## Secrets directory

```bash
mkdir -p secrets
echo "secrets/" >> .gitignore
cp ~/Downloads/client_secret_*.json secrets/google_client.json
```

The encrypted token will be written to `secrets/google_token.json` automatically after `/auth/connect`.
