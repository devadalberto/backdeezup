# Authentication

BackDeezUp uses Google OAuth 2.0. One authentication flow covers all services — **Drive, Photos, and Gmail** — using a single encrypted token.

---

## Prerequisites

- `secrets/google_client.json` must be in place (see [Installation](installation.md))
- `GOOGLE_ENCRYPTION_KEY` must be set in `.env`
- Containers must be running (`make up`)

---

## How it works

The OAuth token is stored as a Fernet-encrypted JSON file at `secrets/google_token.json`. Every API call reads this token automatically. You authenticate once and all services work.

The token includes these Google scopes:

| Scope | Purpose |
|---|---|
| `drive.readonly` | Read Drive files |
| `drive` | Move Drive files to trash |
| `photoslibrary.readonly` | Read Google Photos |
| `gmail.readonly` | Read Gmail messages |
| `gmail.modify` | Add/remove labels, move to trash |

---

## Authenticate (headless server — no browser on server)

The OAuth flow starts a temporary local server on port `18444` inside the container. Your browser hits that port directly, Google redirects back to it, and the token is saved automatically.

### Step 0 — Add redirect URI in Google Cloud Console

Do this once. Go to **Google Cloud Console → APIs & Services → Credentials → your OAuth client → Edit**.

Add this to **Authorized redirect URIs**:
```
http://localhost:18444/
```

Save.

### Step 1 — Expose port 18444 from WSL to Windows (if on WSL2)

Run in PowerShell (as Administrator):
```powershell
$wslIp = wsl -d Debian -- hostname -I | ForEach-Object { $_.Trim().Split(" ")[0] }
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=18444 connectaddress=$wslIp connectport=18444
```

### Step 2 — Run the auth command

```bash
make auth
```

The container prints a URL like:
```
Starting local OAuth server on port 18444...
Open this URL in your browser:
https://accounts.google.com/o/oauth2/auth?...
```

### Step 3 — Open the URL in your browser

Copy the URL and open it in your Windows browser (or any browser that can reach `localhost:18444`). Log in with the Google account you want to back up and click Allow.

### Step 4 — Done

Google redirects to `http://localhost:18444/` automatically. The container catches the callback, saves the encrypted token, and prints:

```
OAuth completed and token saved.
```

The token is saved to `secrets/google_token.json` (Fernet-encrypted).

---

## Verify authentication

```bash
# Check which account is authenticated
curl -s http://localhost:8844/api/gmail/profile | python3 -m json.tool

# Should return:
# {
#   "email": "yourname@gmail.com",
#   "last_history_id": null,
#   "last_full_sync_at": null,
#   ...
# }
```

Or via the Swagger UI at **http://localhost:8844/api/gmail/docs** → `GET /profile`

---

## Re-authentication

The token auto-refreshes using the refresh token. You only need to re-authenticate if:

- `secrets/google_token.json` is deleted
- `GOOGLE_ENCRYPTION_KEY` changes
- You revoke access in your Google account settings
- You want to switch to a different Google account

To re-authenticate, just run `make auth` again.

---

## Token security

- The token is encrypted with Fernet (`GOOGLE_ENCRYPTION_KEY`) before being written to disk
- `secrets/` is mounted read-only into the container (`./secrets:/app/backend_django/secrets:ro`)
- `secrets/` is git-ignored — never committed to version control
- Never share `google_token.json` or `GOOGLE_ENCRYPTION_KEY`

---

## Multiple accounts

Multi-account support is planned for a future release. Currently, one token file covers one Google account. To switch accounts, re-run `make auth` with the new account — this overwrites the existing token.
