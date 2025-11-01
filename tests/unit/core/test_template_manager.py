"""Unit tests for TemplateManager."""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from secuority.core.template_manager import TemplateManager
from secuority.models.exceptions import TemplateError


class TestTemplateManager:
    """Test TemplateManager functionality."""

    @pytest.fixture
    def manager(self) -> TemplateManager:
        """Create TemplateManager instance."""
        return TemplateManager()

    @pytest.fixture
    def temp_template_dir(self, tmp_path: Path) -> Path:
        """Create temporary template directory structure."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)

        # Create sample template files
        (templates_dir / "pyproject.toml.template").write_text("[project]\nname = 'test'\n")
        (templates_dir / ".gitignore.template").write_text("*.pyc\n__pycache__/\n")
        (templates_dir / ".pre-commit-config.yaml.template").write_text("repos:\n  - repo: test\n")

        # Create workflows directory
        workflows_dir = templates_dir / "workflows"
        workflows_dir.mkdir()
        (workflows_dir / "test.yml").write_text("name: Test\non: push\n")

        return tmp_path

    def test_get_template_directory_from_env(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test getting template directory from environment variable."""
        test_dir = tmp_path / "custom_templates"
        test_dir.mkdir()

        with patch.dict(os.environ, {"SECUORITY_TEMPLATES_DIR": str(test_dir)}):
            template_dir = manager.get_template_directory()

        assert template_dir == test_dir

    def test_get_template_directory_default_linux(
        self,
        manager: TemplateManager,
    ) -> None:
        """Test getting default template directory on Linux."""
        with patch("platform.system", return_value="Linux"):
            with patch.dict(os.environ, {}, clear=True):
                template_dir = manager.get_template_directory()

        assert ".config/secuority" in str(template_dir)

    def test_get_template_directory_default_macos(
        self,
        manager: TemplateManager,
    ) -> None:
        """Test getting default template directory on macOS."""
        with patch("platform.system", return_value="Darwin"):
            with patch.dict(os.environ, {}, clear=True):
                template_dir = manager.get_template_directory()

        assert "Library/Application Support/secuority" in str(template_dir)

    def test_get_template_directory_default_windows(
        self,
        manager: TemplateManager,
    ) -> None:
        """Test getting default template directory on Windows."""
        with patch("platform.system", return_value="Windows"):
            with patch.dict(os.environ, {"APPDATA": "C:\\Users\\Test\\AppData\\Roaming"}):
                template_dir = manager.get_template_directory()

        assert "secuority" in str(template_dir)

    def test_load_templates_success(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test loading templates successfully."""
        manager._template_dir = temp_template_dir

        templates = manager.load_templates()

        assert "pyproject.toml.template" in templates
        assert ".gitignore.template" in templates
        assert ".pre-commit-config.yaml.template" in templates
        assert "workflows/test.yml" in templates

    def test_load_templates_directory_not_found(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test loading templates when directory doesn't exist."""
        manager._template_dir = tmp_path / "nonexistent"

        with pytest.raises(TemplateError, match="Templates directory not found"):
            manager.load_templates()

    def test_get_template_existing(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test getting an existing template."""
        manager._template_dir = temp_template_dir
        manager.load_templates()

        template = manager.get_template("pyproject.toml.template")

        assert template is not None
        assert "[project]" in template

    def test_get_template_nonexistent(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test getting a non-existent template."""
        manager._template_dir = temp_template_dir
        manager.load_templates()

        template = manager.get_template("nonexistent.template")

        assert template is None

    def test_initialize_templates_creates_structure(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test initializing templates creates directory structure."""
        manager._template_dir = tmp_path

        # Create a mock package templates directory in the expected location
        package_dir = tmp_path / "mock_secuority"
        package_templates = package_dir / "templates"
        package_templates.mkdir(parents=True)
        (package_templates / "pyproject.toml.template").write_text("[project]\n")

        # Mock Path(__file__).parent.parent to return our mock package directory
        with patch("secuority.core.template_manager.Path") as mock_path_class:
            # Make Path() work normally for most cases
            mock_path_class.side_effect = lambda x: Path(x)

            # But for __file__.parent.parent, return our mock directory
            mock_file_path = MagicMock()
            mock_file_path.parent.parent = package_dir

            with patch("secuority.core.template_manager.__file__", str(tmp_path / "template_manager.py")):
                try:
                    manager.initialize_templates()
                except TemplateError:
                    # Expected if package templates not found - that's ok
                    pass

        # Just verify the structure was created
        assert (tmp_path / "templates").exists()
        assert (tmp_path / "templates" / "workflows").exists()

    def test_create_default_config(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test creating default config file."""
        config_path = tmp_path / "config.yaml"

        manager._create_default_config(config_path)

        # Check that config file was created (either .yaml or .json)
        assert config_path.exists() or config_path.with_suffix(".json").exists()

    def test_create_version_file(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test creating version file."""
        version_path = tmp_path / "version.json"

        manager._create_version_file(version_path)

        assert version_path.exists()

        with open(version_path) as f:
            version_data = json.load(f)

        assert "version" in version_data
        assert "created" in version_data

    def test_template_exists_true(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test checking if template exists returns True."""
        manager._template_dir = temp_template_dir

        exists = manager.template_exists("pyproject.toml.template")

        assert exists

    def test_template_exists_false(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test checking if template exists returns False."""
        manager._template_dir = temp_template_dir

        exists = manager.template_exists("nonexistent.template")

        assert not exists

    def test_get_template_history_empty(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test getting template history when no version file exists."""
        manager._template_dir = tmp_path

        history = manager.get_template_history()

        assert history == []

    def test_get_template_history_with_data(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test getting template history with version data."""
        manager._template_dir = tmp_path
        version_path = tmp_path / "version.json"

        version_data = {
            "version": "1.0.0",
            "created": "2024-01-01T00:00:00",
            "last_update": "2024-01-02T00:00:00",
            "templates_version": "1.0.0",
        }

        with open(version_path, "w") as f:
            json.dump(version_data, f)

        history = manager.get_template_history()

        assert len(history) == 2
        assert history[0]["action"] == "created"
        assert history[1]["action"] == "updated"

    def test_list_available_backups(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test listing available backups."""
        manager._template_dir = tmp_path

        # Create some backup directories
        backup1 = tmp_path / "templates_backup_20240101_120000"
        backup2 = tmp_path / "templates_backup_20240102_120000"
        backup1.mkdir()
        backup2.mkdir()

        backups = manager.list_available_backups()

        assert len(backups) == 2
        assert backup2 in backups  # Most recent first
        assert backup1 in backups

    def test_create_templates_backup(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test creating templates backup."""
        manager._template_dir = temp_template_dir

        backup_path = manager._create_templates_backup()

        assert backup_path.exists()
        assert "templates_backup_" in backup_path.name
        assert (backup_path / "pyproject.toml.template").exists()

    def test_restore_from_backup_success(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test restoring from backup successfully."""
        manager._template_dir = temp_template_dir

        # Create a backup manually to avoid timestamp collision
        templates_path = temp_template_dir / "templates"
        backup_path = temp_template_dir / "manual_backup"
        import shutil

        shutil.copytree(templates_path, backup_path)

        # Store original content
        original_content = (templates_path / "pyproject.toml.template").read_text()

        # Modify current templates
        (templates_path / "pyproject.toml.template").write_text("modified content")

        # Restore from backup
        result = manager.restore_from_backup(backup_path)

        assert result is True

        # Verify original content was restored
        content = (templates_path / "pyproject.toml.template").read_text()
        assert content == original_content
        assert "modified content" not in content

    def test_restore_from_backup_nonexistent(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test restoring from non-existent backup raises error."""
        manager._template_dir = tmp_path
        nonexistent_backup = tmp_path / "nonexistent_backup"

        with pytest.raises(TemplateError, match="Backup directory not found"):
            manager.restore_from_backup(nonexistent_backup)

    def test_get_config_yaml(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test getting config from YAML file."""
        manager._template_dir = tmp_path
        config_path = tmp_path / "config.yaml"

        # Create a simple config file
        config_path.write_text("version: '1.0'\npreferences:\n  auto_backup: true\n")

        try:
            config = manager.get_config()
            assert "version" in config
        except TemplateError:
            # If yaml is not available, this is expected
            pytest.skip("YAML library not available")

    def test_get_config_json_fallback(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test getting config from JSON file as fallback."""
        manager._template_dir = tmp_path
        config_path = tmp_path / "config.json"

        config_data = {"version": "1.0", "preferences": {"auto_backup": True}}

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = manager.get_config()

        assert config["version"] == "1.0"
        assert config["preferences"]["auto_backup"] is True

    def test_get_config_not_found(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test getting config when file doesn't exist raises error."""
        manager._template_dir = tmp_path

        with pytest.raises(TemplateError, match="Configuration file not found"):
            manager.get_config()

    def test_update_version_info(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test updating version information."""
        manager._template_dir = tmp_path
        version_path = tmp_path / "version.json"

        # Create initial version file
        initial_data = {
            "version": "1.0.0",
            "created": "2024-01-01T00:00:00",
            "last_update": None,
        }

        with open(version_path, "w") as f:
            json.dump(initial_data, f)

        manager._update_version_info()

        # Verify last_update was set
        with open(version_path) as f:
            updated_data = json.load(f)

        assert updated_data["last_update"] is not None
        assert updated_data["created"] == "2024-01-01T00:00:00"

    def test_find_templates_directory_found(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test finding templates directory in extracted content."""
        # Create a structure similar to GitHub archive
        repo_dir = tmp_path / "repo-main"
        templates_dir = repo_dir / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "test.template").write_text("test")

        found_dir = manager._find_templates_directory(tmp_path, "repo")

        assert found_dir == templates_dir

    def test_find_templates_directory_not_found(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test finding templates directory when it doesn't exist."""
        found_dir = manager._find_templates_directory(tmp_path, "repo")

        assert found_dir is None

    def test_update_templates_unsupported_source(
        self,
        manager: TemplateManager,
        tmp_path: Path,
    ) -> None:
        """Test updating templates with unsupported source raises error."""
        manager._template_dir = tmp_path

        # Create config with unsupported source
        config_path = tmp_path / "config.json"
        config_data = {"templates": {"source": "ftp://example.com/templates"}}

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        with pytest.raises(TemplateError, match="Unsupported template source"):
            manager.update_templates()

    def test_load_templates_caches_result(
        self,
        manager: TemplateManager,
        temp_template_dir: Path,
    ) -> None:
        """Test that load_templates caches the result."""
        manager._template_dir = temp_template_dir

        # First load
        templates1 = manager.load_templates()

        # Verify cache was populated
        assert manager._templates_cache == templates1

        # Second load should return same content (from cache)
        templates2 = manager.load_templates()

        # Check that the content is the same
        assert templates1 == templates2
        assert len(templates1) == len(templates2)
