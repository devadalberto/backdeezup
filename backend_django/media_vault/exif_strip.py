"""
EXIF metadata preservation and stripping service.

Workflow:
    1. Read full EXIF from image bytes
    2. Save all metadata to MediaMetadata DB record
    3. Re-save image without any EXIF/metadata
    4. Return clean bytes

Supports: JPEG, PNG, HEIC (via Pillow), TIFF
Does NOT modify video files — video metadata stripping requires ffmpeg (future).

Usage:
    from media_vault.exif_strip import strip_and_preserve

    clean_data, metadata_record = strip_and_preserve(
        data=raw_bytes,
        source_path="/path/to/file.jpg",
        filename="photo.jpg",
        mime_type="image/jpeg",
        sha256="abc123...",
        gmail_message_id="msg123",
    )
    # clean_data has no EXIF
    # metadata_record is the saved MediaMetadata instance
"""
import io
import logging
import struct
from datetime import datetime, timezone as dt_timezone
from typing import Optional

log = logging.getLogger(__name__)


# ── GPS coordinate conversion ─────────────────────────────────────────────────

def _dms_to_decimal(dms_tuple, ref: str) -> Optional[float]:
    """Convert GPS DMS tuple (degrees, minutes, seconds) + ref to decimal degrees."""
    try:
        d, m, s = float(dms_tuple[0]), float(dms_tuple[1]), float(dms_tuple[2])
        decimal = d + m / 60.0 + s / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)
    except (TypeError, IndexError, ValueError, ZeroDivisionError):
        return None


# ── EXIF parser ───────────────────────────────────────────────────────────────

def _extract_exif(data: bytes) -> dict:
    """
    Extract all EXIF tags from image bytes. Returns dict of tag_name → value.
    Returns empty dict if no EXIF or parse error.
    """
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        import io as _io

        img = Image.open(_io.BytesIO(data))
        raw_exif = img._getexif()
        if not raw_exif:
            return {}

        result = {}
        for tag_id, value in raw_exif.items():
            tag_name = TAGS.get(tag_id, str(tag_id))

            if tag_name == "GPSInfo" and isinstance(value, dict):
                gps = {}
                for gps_id, gps_val in value.items():
                    gps_tag = GPSTAGS.get(gps_id, str(gps_id))
                    # Convert IFDRational to float for JSON serialisation
                    if hasattr(gps_val, "numerator"):
                        gps_val = float(gps_val)
                    elif isinstance(gps_val, tuple):
                        gps_val = [float(v) if hasattr(v, "numerator") else v for v in gps_val]
                    elif isinstance(gps_val, bytes):
                        gps_val = gps_val.hex()
                    gps[gps_tag] = gps_val
                result["GPSInfo"] = gps
            else:
                # Normalise non-serialisable types
                if hasattr(value, "numerator"):
                    value = float(value)
                elif isinstance(value, tuple):
                    value = [float(v) if hasattr(v, "numerator") else v for v in value]
                elif isinstance(value, bytes):
                    value = value.hex()
                result[tag_name] = value

        return result

    except Exception as exc:
        log.debug("EXIF extraction failed: %s", exc)
        return {}


def _parse_exif_datetime(dt_str: str) -> Optional[datetime]:
    """Parse EXIF datetime string 'YYYY:MM:DD HH:MM:SS' → aware datetime."""
    try:
        return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S").replace(
            tzinfo=dt_timezone.utc
        )
    except (ValueError, TypeError):
        return None


# ── Image stripping ───────────────────────────────────────────────────────────

def _strip_exif(data: bytes, mime_type: str) -> bytes:
    """
    Return image bytes with all metadata removed.
    Re-encodes via Pillow which drops EXIF, ICC profiles, XMP, thumbnails.
    Preserves image quality: JPEG saved at quality=95, others lossless.
    """
    from PIL import Image
    import io as _io

    img = Image.open(_io.BytesIO(data))

    # Convert RGBA → RGB for JPEG (JPEG doesn't support alpha)
    if mime_type in ("image/jpeg", "image/jpg") and img.mode in ("RGBA", "P", "LA"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
        img = background

    buf = _io.BytesIO()

    if mime_type in ("image/jpeg", "image/jpg"):
        img.save(buf, format="JPEG", quality=95, optimize=True, exif=b"")
    elif mime_type == "image/png":
        # PNG: save without metadata chunks
        img.save(buf, format="PNG", optimize=True, pnginfo=None)
    elif mime_type == "image/webp":
        img.save(buf, format="WEBP", quality=95, exif=b"")
    elif mime_type in ("image/tiff", "image/tif"):
        img.save(buf, format="TIFF")
    else:
        # Generic fallback — Pillow handles HEIC/HEIF via pillow-heif plugin if installed
        img.save(buf, format=img.format or "JPEG", exif=b"")

    return buf.getvalue()


# ── Public API ────────────────────────────────────────────────────────────────

def strip_and_preserve(
    data: bytes,
    source_path: str,
    filename: str = "",
    mime_type: str = "image/jpeg",
    sha256: str = "",
    gmail_message_id: str = "",
) -> tuple[bytes, Optional[object]]:
    """
    Extract EXIF, preserve to DB, return stripped image bytes.

    Returns:
        (clean_bytes, MediaMetadata_instance_or_None)

    If no EXIF found, returns original bytes unchanged and metadata record
    with empty raw_exif (still creates a record for audit trail).
    """
    from media_vault.models import MediaMetadata

    original_size = len(data)
    exif_dict = _extract_exif(data)

    # ── Build structured fields from EXIF ─────────────────────────────────
    gps_info = exif_dict.get("GPSInfo", {})

    lat = lon = alt = speed = None
    gps_ts = None

    if gps_info:
        lat_dms = gps_info.get("GPSLatitude")
        lat_ref = gps_info.get("GPSLatitudeRef", "N")
        lon_dms = gps_info.get("GPSLongitude")
        lon_ref = gps_info.get("GPSLongitudeRef", "E")
        alt_val = gps_info.get("GPSAltitude")
        speed_val = gps_info.get("GPSSpeed")

        if lat_dms and lon_dms:
            lat = _dms_to_decimal(lat_dms, lat_ref)
            lon = _dms_to_decimal(lon_dms, lon_ref)
        if alt_val is not None:
            try:
                alt = float(alt_val)
                if gps_info.get("GPSAltitudeRef") == b"\x01":  # below sea level
                    alt = -alt
            except (TypeError, ValueError):
                pass
        if speed_val is not None:
            try:
                speed = float(speed_val)
            except (TypeError, ValueError):
                pass

        # GPS timestamp
        gps_date = gps_info.get("GPSDateStamp", "")
        gps_time = gps_info.get("GPSTimeStamp")
        if gps_date and gps_time:
            try:
                h, m, s = [int(float(x)) for x in gps_time]
                y, mo, d = gps_date.split(":")
                gps_ts = datetime(int(y), int(mo), int(d), h, m, s, tzinfo=dt_timezone.utc)
            except (ValueError, TypeError):
                pass

    dt_orig = _parse_exif_datetime(exif_dict.get("DateTimeOriginal", ""))
    dt_dig  = _parse_exif_datetime(exif_dict.get("DateTimeDigitized", ""))

    # ── Strip EXIF ────────────────────────────────────────────────────────
    supported = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/tiff", "image/tif"}
    if mime_type.lower() in supported:
        try:
            clean_data = _strip_exif(data, mime_type.lower())
        except Exception as exc:
            log.warning("EXIF strip failed for %s: %s — using original", filename, exc)
            clean_data = data
    else:
        # Unsupported format (HEIC, SVG, etc.) — skip strip, still preserve metadata
        clean_data = data

    stripped_size = len(clean_data)

    # ── Save metadata record ──────────────────────────────────────────────
    try:
        record, created = MediaMetadata.objects.get_or_create(
            source_path=source_path,
            defaults={
                "source_sha256": sha256,
                "gmail_message_id": gmail_message_id,
                "filename": filename[:512],
                "mime_type": mime_type[:128],
                "raw_exif": exif_dict,
                "device_make": str(exif_dict.get("Make", ""))[:100],
                "device_model": str(exif_dict.get("Model", ""))[:100],
                "software": str(exif_dict.get("Software", ""))[:200],
                "datetime_original": dt_orig,
                "datetime_digitized": dt_dig,
                "gps_latitude": lat,
                "gps_longitude": lon,
                "gps_altitude": alt,
                "gps_speed": speed,
                "gps_timestamp": gps_ts,
                "original_size_bytes": original_size,
                "stripped_size_bytes": stripped_size,
            },
        )
        if not created:
            # Already processed — return existing record
            log.debug("Metadata already preserved for %s", source_path)
    except Exception as exc:
        log.error("Failed to save MediaMetadata for %s: %s", source_path, exc)
        record = None

    if exif_dict:
        has_gps = "GPSInfo" in exif_dict and lat is not None
        log.info(
            "Stripped EXIF from %s: %d→%d bytes, GPS=%s, device=%s %s",
            filename, original_size, stripped_size,
            f"{lat:.4f},{lon:.4f}" if has_gps else "none",
            exif_dict.get("Make", ""), exif_dict.get("Model", ""),
        )

    return clean_data, record
