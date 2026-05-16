"""
Media Vault API — progress, decisions, import status.
Mounted at /api/vault/ in config/urls.py.
"""
from ninja import NinjaAPI

from .models import MediaDecision, VaultImage, VaultMedia

from ninja.security import django_auth

vault_api = NinjaAPI(urls_namespace="vault", docs_url="/docs", auth=django_auth)


@vault_api.get("/status")
def vault_status(request):
    """Overview of vault contents and review progress."""
    images_total = VaultImage.objects.count()
    images_keep = VaultImage.objects.filter(keep=True).count()
    images_delete = VaultImage.objects.filter(keep=False).count()
    images_undecided = VaultImage.objects.filter(keep__isnull=True).count()

    media_total = VaultMedia.objects.count()
    media_keep = VaultMedia.objects.filter(keep=True).count()
    media_delete = VaultMedia.objects.filter(keep=False).count()
    media_undecided = VaultMedia.objects.filter(keep__isnull=True).count()

    decisions_total = MediaDecision.objects.count()

    return {
        "images": {
            "total": images_total, "keep": images_keep,
            "delete": images_delete, "undecided": images_undecided,
            "reviewed_pct": round((images_keep + images_delete) / max(images_total, 1) * 100, 1),
        },
        "media": {
            "total": media_total, "keep": media_keep,
            "delete": media_delete, "undecided": media_undecided,
            "reviewed_pct": round((media_keep + media_delete) / max(media_total, 1) * 100, 1),
        },
        "decisions_logged": decisions_total,
        "total_items": images_total + media_total,
        "total_undecided": images_undecided + media_undecided,
    }


@vault_api.post("/decide")
def record_decision(request):
    """Record a keep/delete/undecided decision for a vault item."""
    from pydantic import ValidationError
    from schemas import MediaDecisionPayload
    try:
        payload = MediaDecisionPayload.model_validate_json(request.body)
    except ValidationError as exc:
        return {"error": "Validation failed", "details": exc.errors()}

    keep_value = True if payload.action == "keep" else (False if payload.action == "delete" else None)

    if payload.item_type == "image":
        VaultImage.objects.filter(id=payload.item_id).update(keep=keep_value)
    elif payload.item_type == "video":
        VaultMedia.objects.filter(id=payload.item_id).update(keep=keep_value)

    MediaDecision.objects.create(
        item_type=payload.item_type,
        item_id=payload.item_id,
        action=payload.action,
        decided_by=request.user.username if request.user.is_authenticated else "anonymous",
    )

    return {"recorded": True, "item_type": payload.item_type, "item_id": payload.item_id, "action": payload.action}


@vault_api.get("/next-undecided")
def next_undecided(request, item_type: str = "image"):
    """Returns the next undecided item for the review UI."""
    if item_type == "image":
        item = VaultImage.objects.filter(keep__isnull=True).order_by("id").first()
        if not item:
            return {"done": True}
        return {
            "done": False, "id": item.id, "title": item.title,
            "url": item.file.url if item.file else None,
            "source_type": item.source_type, "source_id": item.source_id, "type": "image",
        }
    item = VaultMedia.objects.filter(keep__isnull=True, type="video").order_by("id").first()
    if not item:
        return {"done": True}
    sources = [{"src": s["src"], "type": s["type"]} for s in item.sources] if hasattr(item, "sources") else []
    return {
        "done": False, "id": item.id, "title": item.title,
        "sources": sources, "source_type": item.source_type, "type": "video",
    }
