"""Setup wizard state (Phase 29). Additive: this is the ``core`` app's first model."""
from django.db import models


def _validate_list(value: object) -> None:
    from django.core.exceptions import ValidationError

    if not isinstance(value, list):
        raise ValidationError("Value must be a JSON array.")


def _validate_dict_shape(value: object) -> None:
    from django.core.exceptions import ValidationError

    if not isinstance(value, dict):
        raise ValidationError("Value must be a JSON object.")


class SetupState(models.Model):
    """Singleton row (pk=1) tracking wizard progress.

    ``completed`` is the permanent lock: once True the wizard is unreachable
    forever, even if the admin account created by it is later deleted.
    """

    class Step(models.TextChoices):
        WELCOME = "welcome", "Welcome"
        ADMIN = "admin", "Create admin account"
        SERVICES = "services", "Choose services"
        CONNECT = "connect", "Connect Google"
        STORAGE = "storage", "Storage location"
        SCHEDULE = "schedule", "Schedule"
        TEST = "test", "Test backup"
        DONE = "done", "Done"

    completed = models.BooleanField(default=False)
    step = models.CharField(max_length=20, choices=Step, default=Step.WELCOME)
    #: wizard-only scratch data: {"services": [...], "schedule": {...}, "test_backup_result": {...}}
    data = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Setup State"
        verbose_name_plural = "Setup State"

    def __str__(self) -> str:
        return f"SetupState(step={self.step}, completed={self.completed})"


def is_first_run() -> bool:
    """True while the wizard is still unlocked and reachable.

    Two rules stack:
    - Locked forever once a SetupState row has completed=True -- deleting the
      admin account the wizard created does not reopen it (Phase 29's
      "impossible after setup" guard).
    - Before that: the account-creation entry point (no SetupState row yet,
      or one still sitting at the WELCOME step) additionally requires no
      superuser to exist yet. That is what keeps the wizard unreachable on an
      existing install whose admin was created some other way (e.g. `make
      auth` + `createsuperuser`, wizard never touched).
      Once the wizard's own flow has advanced past WELCOME (Phase 30's later
      steps: services, connect Google, storage, schedule, test backup), the
      superuser it just created in the ADMIN step no longer blocks it --
      those steps stay reachable, gated only by ``completed``, until setup
      finishes.
    """
    state = SetupState.objects.filter(pk=1).first()
    if state is not None and state.completed:
        return False
    if state is None or state.step == SetupState.Step.WELCOME:
        from django.contrib.auth import get_user_model

        return not get_user_model().objects.filter(is_superuser=True).exists()
    return True


def get_or_create_state() -> SetupState:
    state, _ = SetupState.objects.get_or_create(pk=1)
    return state


class IntegrityRun(models.Model):
    """One run of ``core.tasks.task_integrity_check`` (Phase 31).

    Read-only auditing: the task samples already-backed-up items, re-hashes the
    file on disk against the stored checksum, and records the outcome here. It
    never touches ``DriveAsset.state`` / ``GmailMessage.state``.
    """

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    sampled = models.IntegerField(default=0)
    ok = models.IntegerField(default=0)
    missing = models.IntegerField(default=0)
    mismatched = models.IntegerField(default=0)
    #: [{"source": "drive"|"gmail", "id": <pk>, "path": "...", "issue": "missing"|"mismatch"}, ...]
    details = models.JSONField(default=list, blank=True, validators=[_validate_list])

    class Meta:
        verbose_name = "Integrity Run"
        verbose_name_plural = "Integrity Runs"
        ordering = ["-started_at"]

    def __str__(self) -> str:
        return f"IntegrityRun({self.started_at:%Y-%m-%d %H:%M}, sampled={self.sampled})"


class ExportJob(models.Model):
    """One async archive export (Phase 36) -- only created for scope=everything
    or when the resolved item count exceeds ``EXPORT_ASYNC_THRESHOLD``. Small
    exports are streamed synchronously and never create a row here.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        DONE = "DONE", "Done"
        ERROR = "ERROR", "Error"

    scope  = models.CharField(max_length=20)
    source = models.CharField(max_length=20, blank=True, default="")
    format = models.CharField(max_length=10)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)

    item_count = models.IntegerField(default=0)
    #: {"gmail": [ids...], "media": [ids...]} -- resolved once at creation time,
    #: so the task re-runs against a stable set even if state changes mid-run.
    item_ids = models.JSONField(default=dict, blank=True, validators=[_validate_dict_shape])

    file_path = models.TextField(blank=True, default="")
    error     = models.TextField(blank=True, default="")

    created_at  = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = "Export Job"
        verbose_name_plural = "Export Jobs"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"ExportJob({self.scope}/{self.format}, {self.status}, {self.item_count} items)"
