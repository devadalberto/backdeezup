from django.contrib.auth.models import AbstractUser


class BackupUser(AbstractUser):
    """
    Custom user model for BackDeezUp.
    Extends AbstractUser with no additional fields initially.
    Always define a custom user model before first migration per Django best practices.
    Fields can be added here without painful migrations later.
    """

    class Meta(AbstractUser.Meta):
        verbose_name = "Backup User"
        verbose_name_plural = "Backup Users"
        swappable = "AUTH_USER_MODEL"
