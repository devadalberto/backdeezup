"""Phase 42 -- stale .part file cleanup, run inside the existing (Phase 31)
weekly integrity task. Never deletes anything younger than PART_MAX_AGE_DAYS,
so an actively-downloading .part (fresh mtime) is always left alone.
"""
import os

import pytest

from core.tasks import PART_MAX_AGE_DAYS, _cleanup_stale_part_files


def _touch(path, age_days=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    if age_days:
        stamp = __import__("time").time() - age_days * 86400
        os.utime(path, (stamp, stamp))


@pytest.mark.unit
def test_removes_only_part_files_older_than_max_age(tmp_path):
    stale = tmp_path / "video" / "abcd" / "ab" / "old.part"
    fresh = tmp_path / "video" / "abcd" / "ab" / "new.part"
    _touch(stale, age_days=PART_MAX_AGE_DAYS + 1)
    _touch(fresh, age_days=0)

    removed = _cleanup_stale_part_files(str(tmp_path))

    assert removed == [str(stale)]
    assert not stale.exists()
    assert fresh.exists()


@pytest.mark.unit
def test_ignores_non_part_files_regardless_of_age(tmp_path):
    old_other = tmp_path / "old.bin"
    _touch(old_other, age_days=PART_MAX_AGE_DAYS + 5)

    removed = _cleanup_stale_part_files(str(tmp_path))

    assert removed == []
    assert old_other.exists()


@pytest.mark.unit
def test_missing_root_is_a_noop():
    assert _cleanup_stale_part_files("/no/such/directory") == []


@pytest.mark.unit
def test_exactly_at_boundary_is_kept():
    """A .part file just under the cutoff (an active download, e.g.) is never removed."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        from pathlib import Path
        p = Path(d) / "boundary.part"
        _touch(p, age_days=PART_MAX_AGE_DAYS - 1)
        removed = _cleanup_stale_part_files(d)
        assert removed == []
        assert p.exists()


@pytest.mark.django_db
def test_task_integrity_check_reports_and_removes_stale_parts(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    stale = tmp_path / "old.part"
    _touch(stale, age_days=PART_MAX_AGE_DAYS + 1)

    from core.tasks import task_integrity_check
    result = task_integrity_check(sample_size=1)

    assert result["stale_part_files_removed"] == 1
    assert not stale.exists()
