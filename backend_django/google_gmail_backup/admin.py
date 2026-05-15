from django.contrib import admin

from .models import GmailMessage, GmailAttachment, GmailSyncState


@admin.register(GmailSyncState)
class GmailSyncStateAdmin(admin.ModelAdmin):
    list_display = ["email", "last_history_id", "last_full_sync_at", "last_incremental_at", "total_messages"]
    readonly_fields = ["email", "last_history_id", "last_full_sync_at", "last_incremental_at", "total_messages", "created_at", "updated_at"]


@admin.register(GmailAttachment)
class GmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ["filename", "mime_type", "size", "downloaded_at"]
    search_fields = ["filename", "mime_type"]
    list_filter = ["mime_type"]


@admin.register(GmailMessage)
class GmailMessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "from_address", "date", "state", "has_attachments", "size_estimate", "account_email"]
    list_filter = ["state", "has_attachments", "account_email"]
    search_fields = ["subject", "from_address", "gmail_id"]
    readonly_fields = ["gmail_id", "thread_id", "history_id", "discovered_at", "downloaded_at", "last_attempt_at", "sha256", "raw_path"]
    date_hierarchy = "date"

    actions = ["action_trash_selected"]

    @admin.action(description="Trash selected messages in Gmail (requires gmail.modify scope)")
    def action_trash_selected(self, request, queryset):
        from .services_gmail import trash_message
        trashed = 0
        for msg in queryset:
            if trash_message(msg.gmail_id):
                msg.state = GmailMessage.STATE_TRASHED
                msg.save(update_fields=["state"])
                trashed += 1
        self.message_user(request, f"Trashed {trashed} message(s) in Gmail.")
