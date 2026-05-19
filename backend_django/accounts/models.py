from __future__ import annotations

from django.contrib.auth.models import AbstractUser


class BackupUser(AbstractUser):
    """
    Custom user model for BackDeezUp.

    Always define a custom user model before the first migration (Django best practice).
    Fields can be added here later without painful migrations.
    AbstractUser already sets swappable = "AUTH_USER_MODEL" — no need to repeat it.
    """

    class Meta(AbstractUser.Meta):
        verbose_name        = "Backup User"
        verbose_name_plural = "Backup Users"
