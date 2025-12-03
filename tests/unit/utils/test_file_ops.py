"""Unit tests for file operations helper."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from secuority.models.exceptions import ConfigurationError
from secuority.utils.file_ops import FileOperations


class TestFileOperations:
    """Ensure backup, write, and cleanup routines behave safely."""

    def _make_ops(self, tmp_path: Path) -> FileOperations:
        return FileOperations(backup_dir=tmp_path / "backups")

    def test_create_backup_success(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)
        original = tmp_path / "pyproject.toml"
        original.write_text("data", encoding="utf-8")

        backup = ops.create_backup(original)

        assert backup.exists()
        assert backup.read_text(encoding="utf-8") == "data"

    def test_create_backup_missing_file_raises(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)

        with pytest.raises(ConfigurationError, match="Cannot backup non-existent file"):
            ops.create_backup(tmp_path / "missing.txt")

    def test_safe_write_file_creates_backup_when_existing(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)
        target = tmp_path / "config.yaml"
        target.write_text("old", encoding="utf-8")

        backup = ops.safe_write_file(target, "new")

        assert backup is not None and backup.exists()
        assert backup.read_text(encoding="utf-8") == "old"
        assert target.read_text(encoding="utf-8") == "new"

    def test_safe_write_file_without_backup_for_new_file(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)
        target = tmp_path / "new.txt"

        backup = ops.safe_write_file(target, "fresh", create_backup=False)

        assert backup is None
        assert target.read_text(encoding="utf-8") == "fresh"

    def test_safe_write_file_failure_includes_backup_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ops = self._make_ops(tmp_path)
        target = tmp_path / "config.txt"
        target.write_text("initial", encoding="utf-8")

        original_replace = Path.replace

        def fail_replace(self: Path, target_path: Path, *, _orig=original_replace) -> Path:
            if self.name.endswith(".tmp"):
                raise OSError("disk full")
            return _orig(self, target_path)

        monkeypatch.setattr(Path, "replace", fail_replace)

        with pytest.raises(ConfigurationError, match="backup created"):
            ops.safe_write_file(target, "content")

        assert not target.with_suffix(".txt.tmp").exists()

    def test_restore_from_backup_success(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)
        backup = tmp_path / "backups" / "data.txt.20240101.backup"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text("backup-data", encoding="utf-8")
        target = tmp_path / "data.txt"

        ops.restore_from_backup(backup, target)

        assert target.read_text(encoding="utf-8") == "backup-data"

    def test_restore_from_backup_missing_raises(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)

        with pytest.raises(ConfigurationError, match="Backup file does not exist"):
            ops.restore_from_backup(tmp_path / "missing.backup", tmp_path / "target.txt")

    def test_cleanup_old_backups_removes_expired(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)
        fresh = ops.backup_dir / "file.txt.20240102.backup"
        old = ops.backup_dir / "file.txt.20230101.backup"
        ops.backup_dir.mkdir(parents=True, exist_ok=True)
        for path in (fresh, old):
            path.write_text("data", encoding="utf-8")
        # Make old file stale
        stale_time = time.time() - (90 * 24 * 60 * 60)
        os.utime(old, (stale_time, stale_time))

        removed = ops.cleanup_old_backups(days_to_keep=30)

        assert removed == 1
        assert fresh.exists()
        assert not old.exists()

    def test_get_backup_info_sorted(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)
        first = ops.backup_dir / "demo.txt.1.backup"
        second = ops.backup_dir / "demo.txt.2.backup"
        ops.backup_dir.mkdir(parents=True, exist_ok=True)
        first.write_text("old", encoding="utf-8")
        second.write_text("new", encoding="utf-8")
        os.utime(first, (1, 1))
        os.utime(second, (2, 2))

        info = ops.get_backup_info(tmp_path / "demo.txt")

        assert info[0]["path"] == second
        assert info[1]["path"] == first

    def test_validate_file_permissions_existing_and_new_paths(self, tmp_path: Path) -> None:
        ops = self._make_ops(tmp_path)
        existing = tmp_path / "exists.txt"
        existing.write_text("data", encoding="utf-8")
        assert ops.validate_file_permissions(existing)

        new_file = tmp_path / "new" / "file.txt"
        assert ops.validate_file_permissions(new_file)

        nested = tmp_path / "missing" / "deep" / "file.txt"
        assert ops.validate_file_permissions(nested)
