"""Setup wizard views (Phase 29 welcome/admin; Phase 30 services/connect/storage/
schedule/test backup).

Two stacked guards on every view:
  - ``is_first_run()`` (core.models): is the wizard unlocked at all? False once
    completed=True, or on an existing install whose admin wasn't created by
    this wizard. This is the security boundary -- there is no admin account
    yet to gate on for the early steps, and it stays the only gate for later
    steps too (see its docstring for why a superuser existing doesn't lock
    them once the wizard's own flow created it).
  - ``_guard(state, step)``: is THIS step reachable given how far the wizard
    has actually progressed? Prevents skipping ahead by guessing a URL;
    revisiting an earlier/current step is always allowed (read-only or
    idempotent).
"""
from django.contrib.auth import login
from django.shortcuts import redirect, render

from core.models import SetupState, get_or_create_state, is_first_run
from core.setup.forms import CreateAdminForm, ScheduleForm, ServicesForm
from core.setup.schedule import apply_schedule
from core.setup.test_backup import run_test_backup
from core.setup.validators import can_continue, run_checks
from core.errors import humanize_error
from core.health import check_media_write, check_storage
from core import oauth

STEP_URL_NAMES = {
    SetupState.Step.WELCOME: "setup_welcome",
    SetupState.Step.ADMIN: "setup_admin",
    SetupState.Step.SERVICES: "setup_services",
    SetupState.Step.CONNECT: "setup_connect",
    SetupState.Step.STORAGE: "setup_storage",
    SetupState.Step.SCHEDULE: "setup_schedule",
    SetupState.Step.TEST: "setup_test",
    SetupState.Step.DONE: "dashboard",
}
_ORDER = list(SetupState.Step.values)


def _guard(state, step):
    """None when ``step`` is reachable (the wizard has already reached at least
    that far); otherwise the url name of the step the wizard is actually at."""
    have, need = _ORDER.index(state.step), _ORDER.index(step)
    return None if have >= need else STEP_URL_NAMES[state.step]


def _advance(state, step):
    state.step = step
    state.save(update_fields=["step", "data", "updated_at"])


def setup_welcome(request):
    if not is_first_run():
        return redirect("dashboard")
    state = get_or_create_state()
    results = run_checks(request)
    ok = can_continue(results)
    error = None
    if request.method == "POST":
        if ok:
            _advance(state, SetupState.Step.ADMIN)
            return redirect("setup_admin")
        error = "Fix the failing checks above, then Continue."
    return render(request, "core/setup_welcome.html", {"checks": results, "can_continue": ok, "error": error})


def setup_admin(request):
    if not is_first_run():
        return redirect("dashboard")
    state = get_or_create_state()
    blocked = _guard(state, SetupState.Step.ADMIN)
    if blocked:
        return redirect(blocked)
    form = CreateAdminForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        _advance(state, SetupState.Step.SERVICES)
        return redirect("setup_services")
    return render(request, "core/setup_admin.html", {"form": form})


def setup_services(request):
    if not is_first_run():
        return redirect("dashboard")
    state = get_or_create_state()
    blocked = _guard(state, SetupState.Step.SERVICES)
    if blocked:
        return redirect(blocked)
    initial = state.data.get("services", ["gmail", "drive", "photos"])
    form = ServicesForm(request.POST if request.method == "POST" else None, initial={"services": initial})
    if request.method == "POST" and form.is_valid():
        state.data["services"] = form.cleaned_data["services"]
        _advance(state, SetupState.Step.CONNECT)
        return redirect("setup_connect")
    return render(request, "core/setup_services.html", {"form": form})


def setup_connect(request):
    if not is_first_run():
        return redirect("dashboard")
    state = get_or_create_state()
    blocked = _guard(state, SetupState.Step.CONNECT)
    if blocked:
        return redirect(blocked)
    result = request.session.pop("oauth_result", None)
    connection = oauth.status()
    error = None
    if request.method == "POST":
        if connection["status"] == "ok":
            _advance(state, SetupState.Step.STORAGE)
            return redirect("setup_storage")
        error = "Connect your Google account before continuing."
    return render(request, "core/setup_connect.html", {
        "scopes": oauth.scope_list(), "connection": connection, "result": result, "error": error,
    })


def setup_connect_start(request):
    if not is_first_run() or request.method != "POST":
        return redirect("dashboard")
    try:
        return redirect(oauth.start(request, return_to="setup_connect"))
    except Exception as exc:
        info = humanize_error(exc)
        request.session["oauth_result"] = {"ok": False, "message": f"{info['title']} -- {info['hint']}"}
        return redirect("setup_connect")


def setup_storage(request):
    if not is_first_run():
        return redirect("dashboard")
    state = get_or_create_state()
    blocked = _guard(state, SetupState.Step.STORAGE)
    if blocked:
        return redirect(blocked)
    from django.conf import settings

    write_status, write_detail = check_media_write()
    disk_status, disk_detail = check_storage()
    ok = write_status == "ok"
    error = None
    if request.method == "POST":
        if ok:
            _advance(state, SetupState.Step.SCHEDULE)
            return redirect("setup_schedule")
        error = "Storage is not writable -- fix it, then Recheck."
    return render(request, "core/setup_storage.html", {
        "media_root": settings.MEDIA_ROOT,
        "write_status": write_status, "write_detail": write_detail,
        "disk_status": disk_status, "disk_detail": disk_detail,
        "can_continue": ok, "error": error,
    })


def setup_schedule(request):
    if not is_first_run():
        return redirect("dashboard")
    state = get_or_create_state()
    blocked = _guard(state, SetupState.Step.SCHEDULE)
    if blocked:
        return redirect(blocked)
    from django.conf import settings

    saved = state.data.get("schedule", {"preset": "daily", "time": "02:00"})
    form = ScheduleForm(request.POST if request.method == "POST" else None, initial=saved)
    error = None
    if request.method == "POST" and form.is_valid():
        hour, minute = form.cleaned_data["hour"], form.cleaned_data["minute"]
        try:
            apply_schedule(form.cleaned_data["preset"], hour, minute)
        except Exception as exc:
            info = humanize_error(exc)
            error = f"{info['title']} -- {info['hint']}"
        else:
            state.data["schedule"] = {"preset": form.cleaned_data["preset"], "time": f"{hour:02d}:{minute:02d}"}
            _advance(state, SetupState.Step.TEST)
            return redirect("setup_test")
    return render(request, "core/setup_schedule.html", {"form": form, "timezone": settings.TIME_ZONE, "error": error})


def setup_test(request):
    if not is_first_run():
        return redirect("dashboard")
    state = get_or_create_state()
    blocked = _guard(state, SetupState.Step.TEST)
    if blocked:
        return redirect(blocked)
    services = state.data.get("services", [])
    result = state.data.get("test_backup_result")
    if request.method == "POST":
        try:
            result = run_test_backup(services, limit=10)
        except Exception as exc:
            info = humanize_error(exc)
            result = {"success": False, "discovered": 0, "verified": 0, "errors": [
                {"source": "test backup", "title": info["title"], "hint": info["hint"]}
            ]}
        state.data["test_backup_result"] = result
        if result["success"]:
            state.completed = True
            state.step = SetupState.Step.DONE
            state.save(update_fields=["completed", "step", "data", "updated_at"])
        else:
            state.save(update_fields=["data", "updated_at"])
    return render(request, "core/setup_test.html", {"services": services, "result": result, "completed": state.completed})
