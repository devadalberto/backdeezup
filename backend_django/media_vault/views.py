from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def review_view(request):
    return render(request, "media_vault/review.html", {"title": "Media Review"})


@staff_member_required
def vault_ops(request):
    from .models import VaultImage, VaultMedia, MediaDecision
    from google_media_backup.models import DriveAsset

    images_total = VaultImage.objects.count()
    images_keep = VaultImage.objects.filter(keep=True).count()
    images_delete = VaultImage.objects.filter(keep=False).count()
    images_undecided = VaultImage.objects.filter(keep__isnull=True).count()

    media_total = VaultMedia.objects.count()
    media_keep = VaultMedia.objects.filter(keep=True).count()
    media_delete = VaultMedia.objects.filter(keep=False).count()
    media_undecided = VaultMedia.objects.filter(keep__isnull=True).count()

    drive_verified = DriveAsset.objects.filter(state="VERIFIED").count()
    drive_imported = VaultImage.objects.filter(source_type="drive").count() + \
                     VaultMedia.objects.filter(source_type="drive").count()

    ctx = {
        "title": "Media Vault Ops",
        "images_total": images_total,
        "images_keep": images_keep,
        "images_delete": images_delete,
        "images_undecided": images_undecided,
        "media_total": media_total,
        "media_keep": media_keep,
        "media_delete": media_delete,
        "media_undecided": media_undecided,
        "drive_verified": drive_verified,
        "drive_imported": drive_imported,
        "decisions_total": MediaDecision.objects.count(),
    }
    return render(request, "media_vault/vault_ops.html", ctx)
