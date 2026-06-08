# Quick Start

Get BackDeezUp running locally in five minutes.

---

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/#installation) installed
- A Google Cloud project with Drive and Photos APIs enabled
- OAuth 2.0 Desktop App credentials (JSON file)

---

## 1. Clone and install

```bash
git clone https://github.com/devadalberto/backdeezup.git
cd backdeezup
uv sync
```

---

## 2. Configure environment

```bash
cp .env.sample .env
```

Minimum required values in `.env`:

```env
GOOGLE_ENCRYPTION_KEY=<44-char Fernet key>
GOOGLE_CLIENT_SECRETS=secrets/google_client.json
```

Generate a Fernet key:

```bash
python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

!!! warning "Keep your encryption key"
    `GOOGLE_ENCRYPTION_KEY` encrypts your OAuth token. If you lose it, you will need to re-authenticate.

---

## 3. Place Google credentials

```bash
mkdir -p secrets
cp ~/Downloads/client_secret_*.json secrets/google_client.json
```

---

## 4. Migrate and start

=== "Bash"

    ```bash
    ./dev.sh migrate
    ./dev.sh dev
    ```

=== "PowerShell"

    ```powershell
    .\dev.ps1 migrate
    .\dev.ps1 dev
    ```

Server starts at **http://localhost:8844**.

---

## 5. Authenticate with Google

Open **http://localhost:8844/api/docs** and call `POST /auth/connect`. A browser window opens for the Google OAuth flow. After approving, the encrypted token is saved to `secrets/google_token.json`.

---

## 6. Run the pipeline

```bash
# Discover media
curl -X POST http://localhost:8844/api/sync/discover-photos

# Download
curl -X POST "http://localhost:8844/api/sync/download?limit=20"

# Import (hash + copy)
curl -X POST "http://localhost:8844/api/sync/import?limit=20"

# Verify both proofs
curl -X POST "http://localhost:8844/api/sync/verify?limit=50"

# Queue for deletion
curl -X POST "http://localhost:8844/api/sync/mark-delete?limit=100"

# Execute deletion (trash mode by default)
curl -X POST "http://localhost:8844/api/sync/commit-delete"
```

!!! tip
    All endpoints are available interactively at **http://localhost:8844/api/docs**.

---

## 7. Browse the admin

```bash
./dev.sh superuser   # create an admin account
```

Visit **http://localhost:8844/admin** to browse and manage assets.
