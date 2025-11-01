"""Unit tests for ConfigurationApplier and ConfigurationMerger."""

from pathlib import Path

import pytest

from secuority.core.applier import ConfigurationApplier, ConfigurationMerger
from secuority.models.config import ConfigChange
from secuority.models.exceptions import ConfigurationError
from secuority.models.interfaces import ChangeType


class TestConfigurationMerger:
    """Test ConfigurationMerger functionality."""

    @pytest.fixture
    def merger(self) -> ConfigurationMerger:
        """Create ConfigurationMerger instance."""
        return ConfigurationMerger()

    def test_merge_toml_configs_new_section(
        self,
        merger: ConfigurationMerger,
        tmp_path: Path,
    ) -> None:
        """Test merging TOML configs with new section."""
        existing = {"tool": {"ruff": {"line-length": 88}}}
        template = {"tool": {"mypy": {"strict": True}}}

        merged, conflicts = merger.merge_toml_configs(existing, template, tmp_path / "test.toml")

        assert "tool" in merged
        assert "ruff" in merged["tool"]
        assert "mypy" in merged["tool"]
        assert len(conflicts) == 0

    def test_merge_toml_configs_with_conflict(
        self,
        merger: ConfigurationMerger,
        tmp_path: Path,
    ) -> None:
        """Test merging TOML configs with value conflict."""
        existing = {"tool": {"ruff": {"line-length": 88}}}
        template = {"tool": {"ruff": {"line-length": 120}}}

        merged, conflicts = merger.merge_toml_configs(existing, template, tmp_path / "test.toml")

        assert merged["tool"]["ruff"]["line-length"] == 88  # Keeps existing
        assert len(conflicts) == 1
        assert conflicts[0].section == "tool.ruff.line-length"

    def test_merge_toml_configs_nested_dicts(
        self,
        merger: ConfigurationMerger,
        tmp_path: Path,
    ) -> None:
        """Test merging nested dictionary sections."""
        existing = {"tool": {"ruff": {"select": ["E", "F"], "line-length": 88}}}
        template = {"tool": {"ruff": {"select": ["E", "F", "I"], "target-version": "py312"}}}

        merged, conflicts = merger.merge_toml_configs(existing, template, tmp_path / "test.toml")

        assert "target-version" in merged["tool"]["ruff"]
        assert len(conflicts) == 1  # Conflict on 'select'

    def test_merge_text_configs_gitignore(
        self,
        merger: ConfigurationMerger,
        tmp_path: Path,
    ) -> None:
        """Test merging text configs like .gitignore."""
        existing_content = "*.pyc\n__pycache__/\n"
        template_content = "*.pyc\n.env\n.venv/\n"

        merged, conflicts = merger.merge_text_configs(existing_content, template_content, tmp_path / ".gitignore")

        assert "*.pyc" in merged
        assert "__pycache__/" in merged
        assert ".env" in merged
        assert ".venv/" in merged
        assert len(conflicts) == 0

    def test_merge_text_configs_preserves_existing(
        self,
        merger: ConfigurationMerger,
        tmp_path: Path,
    ) -> None:
        """Test that text merge preserves existing lines."""
        existing_content = "# Custom ignore\ncustom_file.txt\n"
        template_content = "*.pyc\n"

        merged, conflicts = merger.merge_text_configs(existing_content, template_content, tmp_path / ".gitignore")

        assert "custom_file.txt" in merged
        assert "*.pyc" in merged

    def test_merge_dict_section_recursive(
        self,
        merger: ConfigurationMerger,
    ) -> None:
        """Test recursive dictionary section merging."""
        existing = {"level1": {"level2": {"key": "value1"}}}
        template = {"level1": {"level2": {"key": "value2", "new_key": "new_value"}}}

        merged, conflicts = merger._merge_dict_section(existing, template, "test")

        assert merged["level1"]["level2"]["new_key"] == "new_value"
        assert merged["level1"]["level2"]["key"] == "value1"  # Keeps existing
        assert len(conflicts) == 1


class TestConfigurationApplier:
    """Test ConfigurationApplier functionality."""

    @pytest.fixture
    def applier(self, tmp_path: Path) -> ConfigurationApplier:
        """Create ConfigurationApplier instance."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        return ConfigurationApplier(backup_dir=backup_dir)

    def test_apply_changes_dry_run(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test applying changes in dry-run mode."""
        test_file = tmp_path / "test.txt"
        change = ConfigChange.create_file_change(
            file_path=test_file,
            content="test content",
            description="Create test file",
        )

        result = applier.apply_changes([change], dry_run=True)

        assert result.dry_run
        assert len(result.successful_changes) == 1
        assert not test_file.exists()  # File not created in dry-run

    def test_apply_changes_create_file(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test applying changes to create a file."""
        test_file = tmp_path / "test.txt"
        change = ConfigChange.create_file_change(
            file_path=test_file,
            content="test content",
            description="Create test file",
        )

        result = applier.apply_changes([change], dry_run=False)

        assert len(result.successful_changes) == 1
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    def test_apply_changes_update_file(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test applying changes to update a file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        change = ConfigChange.update_file_change(
            file_path=test_file,
            old_content="old content",
            new_content="new content",
            description="Update test file",
        )

        result = applier.apply_changes([change], dry_run=False)

        assert len(result.successful_changes) == 1
        assert test_file.read_text() == "new content"
        assert len(result.backups_created) > 0

    def test_apply_changes_with_conflicts(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test applying changes with unresolved conflicts."""
        from secuority.models.config import Conflict

        test_file = tmp_path / "test.toml"
        conflict = Conflict(
            file_path=test_file,
            section="tool.ruff",
            existing_value=88,
            template_value=120,
            description="Line length conflict",
        )

        change = ConfigChange.merge_file_change(
            file_path=test_file,
            old_content="[tool.ruff]\nline-length = 88\n",
            new_content="[tool.ruff]\nline-length = 120\n",
            description="Merge config",
            conflicts=[conflict],
        )

        result = applier.apply_changes([change], dry_run=False)

        assert len(result.conflicts) == 1
        assert len(result.successful_changes) == 0

    def test_create_backup(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test creating file backup."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("original content")

        backup_path = applier.create_backup(test_file)

        assert backup_path.exists()
        assert backup_path.read_text() == "original content"

    def test_merge_configurations_simple(
        self,
        applier: ConfigurationApplier,
    ) -> None:
        """Test merging configurations."""
        existing = {"tool": {"ruff": {"line-length": 88}}}
        template = {"tool": {"mypy": {"strict": True}}}

        merged = applier.merge_configurations(existing, template)

        assert "ruff" in merged["tool"]
        assert "mypy" in merged["tool"]

    def test_merge_file_configurations_new_file(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test merging file configurations for new file."""
        test_file = tmp_path / "test.toml"
        template_content = "[tool.ruff]\nline-length = 120\n"

        change = applier.merge_file_configurations(test_file, template_content)

        assert change.change_type == ChangeType.CREATE
        assert change.file_path == test_file

    def test_merge_file_configurations_existing_file(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test merging file configurations for existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("existing line\n")
        template_content = "new line\n"

        change = applier.merge_file_configurations(test_file, template_content)

        assert change.change_type == ChangeType.MERGE
        assert "existing line" in change.new_content
        assert "new line" in change.new_content

    def test_create_file_already_exists(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test creating file that already exists raises error."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("existing")

        change = ConfigChange.create_file_change(
            file_path=test_file,
            content="new content",
            description="Create file",
        )

        with pytest.raises(ConfigurationError, match="already exists"):
            applier._create_file(change)

    def test_update_file_not_exists(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test updating file that doesn't exist raises error."""
        test_file = tmp_path / "nonexistent.txt"

        change = ConfigChange.update_file_change(
            file_path=test_file,
            old_content="old",
            new_content="new",
            description="Update file",
        )

        with pytest.raises(ConfigurationError, match="does not exist"):
            applier._update_file(change)

    def test_apply_changes_handles_exceptions(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test that apply_changes handles exceptions gracefully."""
        # Create a change that will fail (file doesn't exist for update)
        test_file = tmp_path / "nonexistent.txt"
        change = ConfigChange.update_file_change(
            file_path=test_file,
            old_content="old",
            new_content="new",
            description="Update nonexistent file",
        )

        result = applier.apply_changes([change], dry_run=False)

        assert len(result.failed_changes) == 1
        assert len(result.successful_changes) == 0

    def test_process_template_variables(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test processing template variables."""
        test_file = tmp_path / "test.toml"
        template_content = "name = '{{ project_name }}'\nversion = '{{ project_version }}'\n"

        processed = applier._process_template_variables(template_content, test_file)

        assert "{{ project_name }}" not in processed
        assert "{{ project_version }}" not in processed

    def test_process_template_variables_with_defaults(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test processing template variables with default values."""
        test_file = tmp_path / "test.toml"
        template_content = "name = '{{ project_name | default('my-project') }}'\n"

        processed = applier._process_template_variables(template_content, test_file)

        assert "my-project" in processed or tmp_path.name in processed

    def test_process_template_variables_preserves_github_actions(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test that GitHub Actions variables are preserved."""
        test_file = tmp_path / "workflow.yml"
        template_content = "run: echo ${{ github.sha }}\n"

        processed = applier._process_template_variables(template_content, test_file)

        assert "${{ github.sha }}" in processed

    def test_merge_toml_file(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test merging TOML file contents."""
        existing_content = "[tool.ruff]\nline-length = 88\n"
        template_content = "[tool.mypy]\nstrict = true\n"

        try:
            merged_content, conflicts = applier._merge_toml_file(
                existing_content,
                template_content,
                tmp_path / "test.toml",
            )

            assert "[tool.ruff]" in merged_content
            assert "[tool.mypy]" in merged_content
        except ConfigurationError:
            # TOML support not available
            pytest.skip("TOML support not available")

    def test_extract_project_info_from_pyproject(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test extracting project info from pyproject.toml."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test-project"\nversion = "1.0.0"\n')

        project_info = applier._extract_project_info(pyproject_path)

        # Should extract info if TOML support is available
        assert isinstance(project_info, dict)
