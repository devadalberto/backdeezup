# BackDeezUp — URL Index (PDX-CL1)

Base: `https://localhost:8445` (nginx TLS) or `http://localhost:8844` (nginx → redirects to HTTPS)
Direct web (WSL2 bug — avoid): `http://localhost:8845`

---

## UI / Admin

| URL | Description |
|-----|-------------|
| `http://localhost:8844/` | Landing page (redirects → HTTPS :8445) |
| `https://localhost:8445/` | Landing page |
| `https://localhost:8445/admin/` | Django admin |
| `https://localhost:8445/admin/reports/` | Drive/Photos reports dashboard |
| `https://localhost:8445/admin/ops/` | Drive/Photos ops console |
| `https://localhost:8445/admin/gmail/dashboard/` | Gmail dashboard |
| `https://localhost:8445/admin/gmail/ops/` | Gmail ops console |
| `https://localhost:8445/admin/gmail/rule-builder/` | Gmail rule builder |
| `https://localhost:8445/admin/vault/ops/` | Media vault ops |
| `https://localhost:8445/vault/review/` | Vault review UI |
| `https://localhost:8445/cms/` | Wagtail CMS admin |

---

## API Docs (Django Ninja interactive)

| URL | Description |
|-----|-------------|
| `https://localhost:8445/api/docs` | Drive/Photos API (Swagger UI) |
| `https://localhost:8445/api/gmail/docs` | Gmail API (Swagger UI) |
| `https://localhost:8445/api/vault/docs` | Media Vault API (Swagger UI) |

---

## Drive / Photos API (`/api/`)

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/assets` | List assets |
| GET | `/api/progress` | Pipeline progress |
| GET | `/api/export/assets` | Export asset list |
| POST | `/api/auth/connect` | Connect Google account |
| POST | `/api/sync/discover` | Discover Drive media |
| POST | `/api/sync/discover-files` | Discover Drive documents |
| POST | `/api/sync/discover-photos` | Discover Google Photos |
| POST | `/api/sync/download` | Download discovered assets |
| POST | `/api/sync/import` | Import + SHA-256 hash |
| POST | `/api/sync/verify` | Verify proofs |
| POST | `/api/sync/mark-delete` | Queue verified for deletion |
| POST | `/api/sync/commit-delete` | Execute Drive deletion |

---

## Gmail API (`/api/gmail/`)

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/gmail/profile` | Gmail account profile |
| GET | `/api/gmail/progress` | Gmail pipeline progress |
| GET | `/api/gmail/messages` | List messages |
| GET | `/api/gmail/rules` | List cleanup rules |
| GET | `/api/gmail/audit-log` | Audit log |
| GET | `/api/gmail/export/audit-log` | Export audit log |
| GET | `/api/gmail/export/messages` | Export messages |
| GET | `/api/gmail/rule-builder/fields` | Rule builder field list |
| POST | `/api/gmail/sync/discover` | Full Gmail snapshot discovery |
| POST | `/api/gmail/sync/incremental` | Incremental sync (historyId) |
| POST | `/api/gmail/sync/download` | Download .eml files |
| POST | `/api/gmail/sync/verify` | Verify .eml files |
| POST | `/api/gmail/cleanup/trash` | Cleanup by trash rules |
| POST | `/api/gmail/cleanup/label` | Cleanup by label rules |
| POST | `/api/gmail/rules/{id}/dry-run` | Dry-run a rule |
| POST | `/api/gmail/rules/{id}/execute` | Execute a rule |
| POST | `/api/gmail/rules/run-all` | Run all rules |
| POST | `/api/gmail/protected-senders/apply` | Apply protected-sender rules |
| POST | `/api/gmail/rule-builder/preview` | Preview rule builder query |
| POST | `/api/gmail/rule-builder/dry-run` | Dry-run rule builder |
| POST | `/api/gmail/rule-builder/save` | Save rule builder rule |
| POST | `/api/gmail/ops/empty-trash` | Empty Gmail trash |
| POST | `/api/gmail/push` | Gmail push notification webhook (no auth) |

---

## Media Vault API (`/api/vault/`)

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/vault/status` | Vault import status |
| GET | `/api/vault/next-undecided` | Next asset awaiting review decision |
| POST | `/api/vault/decide` | Record keep/delete decision |
| POST | `/api/vault/import` | Import verified assets into vault |

---

## OAuth

| Method | URL | Description |
|--------|-----|-------------|
| GET/POST | `/api/oauth/callback` | Google OAuth callback (no CSRF) |

---

## HTMX fragments (internal, used by templates)

| URL | Description |
|-----|-------------|
| `/htmx/stats/` | Landing page stats fragment |
| `/htmx/gmail/cleanup-status/` | Gmail cleanup status fragment |
| `/htmx/gmail/audit-log/` | Gmail audit log fragment |
| `/htmx/gmail/progress/` | Gmail progress fragment |

---

## External / Docs

| URL | Description |
|-----|-------------|
| `http://localhost:8001` | MkDocs dev server (`make docs`) |
| `https://devadalberto.github.io/backdeezup` | Published MkDocs site (GitHub Pages) |
