"""Phase 38 — PostgreSQL backup/restore. No live Postgres here (this sandbox has
no backdeezup db container running): pruning is pure filesystem logic and is
tested directly against real files; the pg_dump invocation itself is mocked
(subprocess.run) since it needs a real server to talk to.
"""
import os
from unittest.mock import patch

import pytest

from core.tasks import DUMP_SUFFIX, prune_old_dumps, task_db_backup


def _touch_dump(dir_path, name, mtime):
    path = os.path.join(dir_path, name)
    open(path, "wb").close()
    os.utime(path, (mtime, mtime))
    return path


def test_prune_keeps_newest_n_and_deletes_the_rest(tmp_path):
    now = 1_000_000
    paths = [_touch_dump(tmp_path, f"backdeezup-{i}{DUMP_SUFFIX}", now + i) for i in range(5)]

    deleted = prune_old_dumps(str(tmp_path), keep_last=2)

    assert set(deleted) == set(paths[:3])  # the three oldest
    remaining = sorted(os.listdir(tmp_path))
    assert remaining == ["backdeezup-3.dump", "backdeezup-4.dump"]


def test_prune_ignores_non_dump_files(tmp_path):
    _touch_dump(tmp_path, "backdeezup-1.dump", 1)
    (tmp_path / "notes.txt").write_text("keep me")
    (tmp_path / "other-app.dump").write_text("not ours")

    deleted = prune_old_dumps(str(tmp_path), keep_last=0)

    assert deleted == [str(tmp_path / "backdeezup-1.dump")]
    assert (tmp_path / "notes.txt").exists()
    assert (tmp_path / "other-app.dump").exists()


def test_prune_on_missing_directory_is_a_noop():
    assert prune_old_dumps("/no/such/dir", keep_last=5) == []


def test_prune_keep_last_zero_deletes_everything(tmp_path):
    _touch_dump(tmp_path, f"backdeezup-1{DUMP_SUFFIX}", 1)
    _touch_dump(tmp_path, f"backdeezup-2{DUMP_SUFFIX}", 2)
    deleted = prune_old_dumps(str(tmp_path), keep_last=0)
    assert len(deleted) == 2
    assert os.listdir(tmp_path) == []


# ── task_db_backup gating + subprocess call ───────────────────────────────────

@pytest.mark.django_db
def test_task_skips_when_disabled(settings):
    settings.DB_BACKUP_ENABLED = False
    with patch("subprocess.run") as run:
        result = task_db_backup()
    assert result["skipped"] is True
    run.assert_not_called()


@pytest.mark.django_db
def test_task_skips_when_no_database_url(settings, monkeypatch):
    settings.DB_BACKUP_ENABLED = True
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with patch("subprocess.run") as run:
        result = task_db_backup()
    assert result["skipped"] is True
    run.assert_not_called()


@pytest.mark.django_db
def test_task_calls_pg_dump_and_prunes(tmp_path, settings, monkeypatch):
    settings.DB_BACKUP_ENABLED = True
    settings.DB_BACKUP_DIR = str(tmp_path)
    settings.DB_BACKUP_KEEP_LAST = 1
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@db:5432/backdeezup")

    _touch_dump(tmp_path, f"backdeezup-old{DUMP_SUFFIX}", 1)

    def fake_run(cmd, check):
        assert cmd[0] == "pg_dump"
        assert "--dbname" in cmd and cmd[-1] == "postgres://u:p@db:5432/backdeezup"
        dest = cmd[cmd.index("-f") + 1]
        open(dest, "wb").close()  # simulate pg_dump writing the file

    with patch("subprocess.run", side_effect=fake_run) as run:
        result = task_db_backup()

    run.assert_called_once()
    assert os.path.exists(result["file"])
    assert result["pruned"] == [str(tmp_path / f"backdeezup-old{DUMP_SUFFIX}")]
    assert not os.path.exists(tmp_path / f"backdeezup-old{DUMP_SUFFIX}")
