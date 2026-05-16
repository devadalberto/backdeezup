# Media Vault CMS

BackDeezUp uses **Wagtail 7.4 LTS** as the CMS layer for the Media Vault. This document covers how to use the CMS to browse, organise, and make keep/delete decisions on your backed-up Google media.

---

## Access

| URL | Purpose |
|---|---|
| `/cms/` | Wagtail CMS admin — manage all media |
| `/cms/images/` | Image library |
| `/cms/documents/` | Document library |
| `/cms/media/` | Video and audio library (wagtailmedia) |
| `/vault/` | Public media vault front-end |
| `/admin/gmail/ops/` | Gmail ops console |

Login with your Django superuser credentials.

---

## First-time setup

After `make redeploy && make migrate`, run:

```bash
docker compose exec web python manage.py createsuperuser
```

Then visit `/cms/` and log in.

### Create the site and vault homepage

1. Go to `/cms/` → **Settings → Sites** → Edit the default site
2. Set hostname to your server IP or hostname (e.g. `192.168.88.60`)
3. Go to **Pages** → **Root** → **Add child page** → choose **Vault Home Page**
4. Title: `Media Vault`, slug: `vault`
5. Publish

Now `/vault/` shows your media vault landing page.

---

## Page types

### Vault Home Page
Landing page. Shows links to all child pages. Add it once under Root.

### Media Gallery Page
General purpose — supports all media types (images, videos, audio, text).
Use this for a mixed collection from a specific date range or source.

**Add blocks:**
- **Image** — single photo with caption, credit, keep/delete decision
- **Image Gallery** — grid of photos
- **Video** — single video player
- **Video Gallery** — grid of video players
- **Audio** — audio player
- **Text** — rich text (bold, italic, links, lists)
- **Heading** — section heading
- **Raw HTML** — embed anything

### Photo Review Page
Images only. Optimised for bulk photo triage. Set `source_filter` to Drive, Gmail, or All.

### Video Review Page
Videos and audio only. Watch and mark keep/delete.

---

## Keep / Delete decisions

Every image, video, and audio block has a **Decision** field with three options:

| Value | Meaning |
|---|---|
| **Keep** | Mark this file as worth keeping |
| **Delete** | Mark for deletion |
| **Undecided** | Not yet reviewed (default) |

This field is also on the `VaultImage`, `VaultMedia`, and `VaultDocument` model records — browse and filter by decision in the **Media Vault** snippet section of the CMS.

To filter the vault front-end by decision, use query params:
```
/vault/my-gallery/?keep=keep
/vault/my-gallery/?keep=delete
/vault/my-gallery/?keep=undecided
```

---

## Uploading media

### Images

1. Go to `/cms/images/` → **Add image**
2. Upload file (up to **1 GB**)
3. Set focal point by clicking on the image
4. Fill in `source_type` (Drive, Gmail, or Manual Upload)
5. Set initial `keep` decision

### Videos

1. Go to `/cms/media/` → **Add media item**
2. Choose type: **Video** or **Audio**
3. Upload file (up to **256 GB** for video)
4. Fill in `source_type` and `keep`

### Documents

1. Go to `/cms/documents/` → **Add document**
2. Upload PDF or other file

---

## Snippet review (bulk triage)

In the CMS sidebar under **Media Vault**:

- **Images** — filter by `keep=None` (undecided) to see what still needs review
- **Videos & Audio** — same
- **Documents** — same
- **Decisions Log** — immutable record of all keep/delete decisions (read-only)

The list view supports bulk actions via the action bar.

---

## Wagtail CMS Matrix theme

The CMS admin at `/cms/` uses a custom Matrix dark theme (phosphor green `#00ff41` on black). Theme is applied via the `insert_global_admin_css` hook in `media_vault/wagtail_hooks.py`.

If you want to switch to Wagtail's default light theme, comment out the `matrix_admin_css` hook in `wagtail_hooks.py`.

---

## Pydantic v2 validation

All Django views (not just API endpoints) use Pydantic v2 schemas from `backend_django/schemas.py` for input validation.

```python
from schemas import MediaDecisionPayload
from pydantic import ValidationError

def my_view(request):
    try:
        payload = MediaDecisionPayload.model_validate_json(request.body)
    except ValidationError as e:
        return JsonResponse({"errors": e.errors()}, status=422)
```

Available schemas:
- `PaginationParams` — page/page_size
- `ErrorResponse` / `SuccessResponse` — standard responses
- `GmailDiscoverParams`, `GmailSyncParams` — Gmail pipeline
- `RuleBuilderPayload`, `RuleConditionSchema` — cleanup rules
- `DriveDiscoverParams`, `DriveDownloadParams` — Drive pipeline
- `MediaDecisionPayload`, `BulkMediaDecisionPayload` — keep/delete decisions

---

## Adding new pages from the CMS

1. Go to `/cms/pages/`
2. Click on your **Vault Home Page**
3. Click **Add child page**
4. Choose **Media Gallery Page**, **Photo Review Page**, or **Video Review Page**
5. Add StreamField blocks via the **+** button
6. For each image/video block, set the **Decision** field
7. Click **Publish**

The page is immediately live at `/vault/<slug>/`.
