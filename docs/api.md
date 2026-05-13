# API Reference

Base URL: `http://localhost:8844/api`

Interactive Swagger UI: **http://localhost:8844/api/docs**

All endpoints return JSON. Pipeline endpoints return a `run_id` (UUID) for audit purposes.

---

## Authentication

### POST /auth/connect

Launches the local Google OAuth flow. Opens a browser window for account selection and consent. On completion, the encrypted token is saved to `GOOGLE_TOKEN_FILE`.

**Request:** No body required.

**Response:**

```json
{
  "status": "ok",
  "message": "OAuth completed and token saved"
}
```

!!! note
    This endpoint starts a local OAuth server. Run it from a machine with a browser available, or set up port forwarding if running headlessly.

---

## Discovery

All discovery endpoints create `DriveAsset` rows in `DISCOVERED` state using `get_or_create` — safe to call multiple times.

### POST /sync/discover

Discovers media files (images and videos) from Google Drive.

**Query params:**

| Param | Default | Description |
|---|---|---|
| `page_size` | `50` | Results per Drive API page. |
| `max_pages` | `10` | Maximum pages to fetch per call. |

**Response:**

```json
{
  "discovered": 47,
  "run_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### POST /sync/discover-files

Discovers document-type files from Google Drive (PDF, Office, CSV, archives, iWork).

Same params and response shape as `/sync/discover`.

---

### POST /sync/discover-photos

Discovers items from Google Photos Library API. Photos items are stored with a `photos:` prefix on `drive_id` to prevent collision with Drive IDs.

Same params and response shape as `/sync/discover`.

---

## Pipeline

### POST /sync/download

Downloads `DISCOVERED` assets to local disk. Files are written to a `.part` temporary path then atomically renamed — no partial files reach `DOWNLOADED` state.

**Query params:**

| Param | Default | Description |
|---|---|---|
| `limit` | `20` | Max assets to process per call. |

**Response:**

```json
{
  "downloaded": 20,
  "errors": 0,
  "run_id": "..."
}
```

---

### POST /sync/import

SHA-256 hashes each `DOWNLOADED` file, copies it into the media library at `media/imported/<sha[:2]>/<sha>.ext`, and creates (or reuses) a `MediaItem` record.

**Query params:**

| Param | Default | Description |
|---|---|---|
| `limit` | `20` | Max assets to process per call. |

**Response:**

```json
{
  "imported": 20,
  "deduplicated": 2,
  "errors": 0,
  "run_id": "..."
}
```

---

### POST /sync/verify

Confirms both proofs for each `IMPORTED` asset:

1. File exists at `download_path` on disk
2. `MediaItem` record exists in database

Assets that pass both proofs advance to `VERIFIED`. Assets that fail either proof stay in `IMPORTED` with an error recorded.

**Query params:**

| Param | Default | Description |
|---|---|---|
| `limit` | `50` | Max assets to process per call. |

**Response:**

```json
{
  "verified": 48,
  "failed": 2,
  "run_id": "..."
}
```

---

### POST /sync/mark-delete

Advances all `VERIFIED` assets to `DELETE_PENDING`. This is a bulk operation with no API rate limit concerns (no Google API calls).

**Query params:**

| Param | Default | Description |
|---|---|---|
| `limit` | `100` | Max assets to queue per call. |

**Response:**

```json
{
  "queued_for_delete": 46,
  "run_id": "..."
}
```

---

### POST /sync/commit-delete

Executes Drive deletion for `DELETE_PENDING` assets that pass the retention guard (`imported_at` age >= `MIN_RETENTION_DAYS`).

**Query params:**

| Param | Default | Description |
|---|---|---|
| `limit` | `50` | Max assets to delete per call. |
| `force` | `false` | If `true`, bypass the retention guard. Use with caution. |

**Response:**

```json
{
  "deleted": 44,
  "skipped_retention": 2,
  "mode": "trash",
  "run_id": "..."
}
```

!!! danger "Deletion is real"
    `commit-delete` makes actual calls to the Google Drive API. In `trash` mode files go to Drive trash (recoverable for 30 days). In `hard` mode they are permanently deleted.

---

## Asset listing

### GET /assets

Lists `DriveAsset` records with optional filters.

**Query params:**

| Param | Description |
|---|---|
| `state` | Filter by state (e.g. `DISCOVERED`, `VERIFIED`). |
| `q` | Text search on file name. |

**Response:**

```json
[
  {
    "drive_id": "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
    "name": "photo.jpg",
    "mime_type": "image/jpeg",
    "size_bytes": 2457600,
    "state": "VERIFIED",
    "imported_at": "2026-05-10T14:32:00Z"
  }
]
```

---

## Error responses

All endpoints return standard HTTP status codes:

| Status | Meaning |
|---|---|
| `200` | Success |
| `400` | Bad request (invalid params) |
| `401` | Not authenticated — run `/auth/connect` first |
| `500` | Internal error — check `RunLog` for details |
