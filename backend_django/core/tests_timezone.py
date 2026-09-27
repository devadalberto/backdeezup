"""Phase 22 — TIME_ZONE is read from the environment, default unchanged."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
PRINT_TZ = "from django.conf import settings; print(settings.TIME_ZONE)"


def _settings_time_zone(**overrides):
    env = {k: v for k, v in os.environ.items() if k != "TIME_ZONE"}
    env.setdefault("DJANGO_SECRET_KEY", "test-only-not-a-real-key-0123456789abcdef")
    env.update(DATABASE_URL="", DJANGO_SETTINGS_MODULE="config.settings", **overrides)
    result = subprocess.run(
        [sys.executable, "-c", PRINT_TZ],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


@pytest.mark.unit
def test_time_zone_default_unchanged():
    assert _settings_time_zone() == "America/Los_Angeles"


@pytest.mark.unit
def test_time_zone_from_env():
    assert _settings_time_zone(TIME_ZONE="Europe/Berlin") == "Europe/Berlin"
