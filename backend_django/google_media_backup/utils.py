from __future__ import annotations

import base64
import hashlib
import os
import shutil
from pathlib import Path

from cryptography.fernet import Fernet
from decouple import config

MEDIA_ROOT = Path(config('MEDIA_ROOT', default='media')).resolve()


def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()


def deterministic_path(file_name: str, digest_hint: str, kind: str = 'file') -> str:
    sub = digest_hint[:2] if digest_hint else 'xx'
    ext = (os.path.splitext(file_name)[1] or '').lower().strip('.') or 'bin'
    rel = Path(kind) / Path(digest_hint[:4] or 'xxxx') / sub / f"{digest_hint}.{ext}"
    abs_path = MEDIA_ROOT / rel
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return str(abs_path)


def copy_into_media(src_path: str, digest_hex: str, ext_hint: str = 'bin') -> str:
    dst_dir = MEDIA_ROOT / 'imported' / digest_hex[:2]
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{digest_hex}.{ext_hint}"
    shutil.copy2(src_path, dst)
    return str(dst)


def get_fernet() -> Fernet:
    from django.core.exceptions import ImproperlyConfigured
    key = config('GOOGLE_ENCRYPTION_KEY', default='')
    if not key:
        raise ImproperlyConfigured(
            "GOOGLE_ENCRYPTION_KEY is not set. "
            "Generate: python -c \"import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
        )
    if len(key) != 44:
        raise ImproperlyConfigured(
            f"GOOGLE_ENCRYPTION_KEY must be exactly 44 chars (got {len(key)}). "
            "Generate: python -c \"import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
        )
    # Validate it is real base64url-encoded 32 bytes — rejects human-typed placeholders
    try:
        raw = base64.urlsafe_b64decode(key + "==")
        if len(raw) != 32:
            raise ValueError("Decoded key must be 32 bytes")
    except Exception:
        raise ImproperlyConfigured(
            "GOOGLE_ENCRYPTION_KEY is not a valid base64url-encoded 32-byte key. "
            "Generate: python -c \"import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
        )
    return Fernet(key)
