from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, StreamingHttpResponse, Http404
from django.shortcuts import get_object_or_404, render


@staff_member_required
def review_view(request):
    return render(request, "media_vault/review.html", {"title": "Media Review"})


@staff_member_required
def stream_video(request, media_id):
    """
    HTTP Range-aware video streaming. Supports seek/scrub in browser.
    Serves VaultMedia files with 206 Partial Content responses.
    """
    from .models import VaultMedia
    import mimetypes, os

    media = get_object_or_404(VaultMedia, pk=media_id)

    if not media.file:
        raise Http404("No file attached to this media item.")

    file_path = media.file.path
    if not os.path.exists(file_path):
        raise Http404("File not found on disk.")

    file_size = os.path.getsize(file_path)
    content_type = mimetypes.guess_type(file_path)[0] or "video/mp4"

    range_header = request.META.get("HTTP_RANGE", "")

    if range_header.startswith("bytes="):
        try:
            range_spec = range_header[6:]
            start_str, end_str = range_spec.split("-")
            start = int(start_str) if start_str else 0
            end   = int(end_str)   if end_str   else file_size - 1
        except (ValueError, AttributeError):
            start, end = 0, file_size - 1

        start = max(0, min(start, file_size - 1))
        end   = max(start, min(end, file_size - 1))
        length = end - start + 1

        def _iter_range(path, s, chunk=65536):
            with open(path, "rb") as f:
                f.seek(s)
                remaining = length
                while remaining > 0:
                    data = f.read(min(chunk, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        response = StreamingHttpResponse(
            _iter_range(file_path, start),
            status=206,
            content_type=content_type,
        )
        response["Content-Range"]  = f"bytes {start}-{end}/{file_size}"
        response["Content-Length"] = str(length)
    else:
        response = FileResponse(open(file_path, "rb"), content_type=content_type)
        response["Content-Length"] = str(file_size)

    response["Accept-Ranges"] = "bytes"
    return response


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
