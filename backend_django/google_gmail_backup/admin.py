from django.contrib import admin
from django.utils.html import format_html

from .models import (
    CleanupAuditLog,
    CleanupRule,
    GmailAttachment,
    GmailMessage,
    GmailSyncState,
    ProtectedSender,
)


@admin.register(GmailSyncState)
class GmailSyncStateAdmin(admin.ModelAdmin):
    list_display = ["email", "last_history_id", "last_full_sync_at", "last_incremental_at", "total_messages"]
    readonly_fields = ["email", "last_history_id", "last_full_sync_at",
                       "last_incremental_at", "total_messages", "created_at", "updated_at"]


@admin.register(GmailAttachment)
class GmailAttachmentAdmin(admin.ModelAdmin):
    list_display = ["filename", "mime_type", "size", "downloaded_at"]
    search_fields = ["filename", "mime_type"]


@admin.register(GmailMessage)
class GmailMessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "from_address", "date", "state", "has_attachments", "account_email"]
    list_filter = ["state", "has_attachments", "account_email"]
    search_fields = ["subject", "from_address", "gmail_id"]
    readonly_fields = ["gmail_id", "thread_id", "history_id", "discovered_at",
                       "downloaded_at", "last_attempt_at", "sha256", "raw_path"]
    date_hierarchy = "date"
    actions = ["action_trash"]

    @admin.action(description="Trash selected in Gmail (requires gmail.modify scope)")
    def action_trash(self, request, queryset):
        from .services_gmail import trash_message
        trashed = 0
        for msg in queryset:
            if trash_message(msg.gmail_id):
                msg.state = GmailMessage.STATE_TRASHED
                msg.save(update_fields=["state"])
                trashed += 1
        self.message_user(request, f"Trashed {trashed} message(s).")


@admin.register(ProtectedSender)
class ProtectedSenderAdmin(admin.ModelAdmin):
    list_display = ["email", "label_to_apply", "star", "note"]
    search_fields = ["email", "note"]


@admin.register(CleanupRule)
class CleanupRuleAdmin(admin.ModelAdmin):
    list_display = ["name", "action", "enabled_badge", "min_age_days",
                    "last_run_at", "last_affected_count", "last_dry_run_count"]
    list_filter = ["enabled", "action"]
    search_fields = ["name", "gmail_query"]
    readonly_fields = ["last_run_at", "last_run_dry", "last_affected_count",
                       "last_dry_run_count", "created_at", "updated_at"]
    actions = ["enable_rules", "disable_rules", "run_dry_run", "run_execute"]

    def enabled_badge(self, obj):
        color = "green" if obj.enabled else "gray"
        label = "ON" if obj.enabled else "OFF"
        return format_html('<span style="color:{}; font-weight:bold">{}</span>', color, label)
    enabled_badge.short_description = "Status"

    @admin.action(description="Enable selected rules")
    def enable_rules(self, request, queryset):
        updated = queryset.update(enabled=True)
        self.message_user(request, f"{updated} rule(s) enabled.")

    @admin.action(description="Disable selected rules")
    def disable_rules(self, request, queryset):
        updated = queryset.update(enabled=False)
        self.message_user(request, f"{updated} rule(s) disabled.")

    @admin.action(description="Dry-run selected rules (no changes)")
    def run_dry_run(self, request, queryset):
        from .services_rules import apply_rule
        total = 0
        for rule in queryset:
            audit = apply_rule(rule, dry_run=True, actor_label=request.user.username)
            total += audit.affected_count
        self.message_user(request, f"Dry-run complete. Would affect {total} message(s) total.")

    @admin.action(description="EXECUTE selected rules (real changes — confirm first!)")
    def run_execute(self, request, queryset):
        from .services_rules import apply_rule
        total = 0
        for rule in queryset:
            audit = apply_rule(rule, dry_run=False, actor_label=request.user.username)
            total += audit.affected_count
        self.message_user(request, f"Executed. Affected {total} message(s) total.")


@admin.register(CleanupAuditLog)
class CleanupAuditLogAdmin(admin.ModelAdmin):
    list_display = ["rule_name", "action", "dry_run", "affected_count",
                    "actor_label", "status", "started_at"]
    list_filter = ["dry_run", "status", "action"]
    search_fields = ["rule_name", "actor_label"]
    readonly_fields = ["rule", "rule_name", "action", "dry_run", "actor", "actor_label",
                       "affected_count", "affected_gmail_ids", "sample_subjects",
                       "started_at", "finished_at", "status", "error_text"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
