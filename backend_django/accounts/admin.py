from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import BackupUser


@admin.register(BackupUser)
class BackupUserAdmin(UserAdmin):
    """Custom user admin — same as Django's default UserAdmin."""
    pass
