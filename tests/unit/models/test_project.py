"""Unit tests for ProjectState model."""

import tempfile
from pathlib import Path

import pytest

from secuority.models.exceptions import ValidationError
from secuority.models.interfaces import (
    DependencyAnalysis,
    DependencyManager,
    Package,
    QualityTool,
    SecurityTool,
    ToolConfig,
    Workflow,
)
from secuority.models.project import ProjectState


class TestProjectState:
    """Test ProjectState model validation and methods."""

    def test_project_state_creation_valid_path(self, tmp_path: Path) -> None:
        """Test creating ProjectState with valid path."""
        state = ProjectState(project_path=tmp_path)
        assert state.project_path == tmp_path
        assert not state.has_pyproject_toml
        assert not state.has_requirements_txt

    def test_project_state_creation_invalid_path(self) -> None:
        """Test creating ProjectState with invalid path raises ValidationError."""
        invalid_path = Path("/nonexistent/path/that/does/not/exist")
        with pytest.raises(ValidationError):
            ProjectState(project_path=invalid_path)

    def test_validate_with_existing_files(self, tmp_path: Path) -> None:
        """Test validation succeeds when claimed files exist."""
        # Create test files
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")
        (tmp_path / "requirements.txt").write_text("pytest>=7.0.0\n")
        (tmp_path / ".gitignore").write_text("*.pyc\n")

        state = ProjectState(
            project_path=tmp_path,
            has_pyproject_toml=True,
            has_requirements_txt=True,
            has_gitignore=True,
        )

        assert state.validate()

    def test_validate_fails_when_claimed_files_missing(self, tmp_path: Path) -> None:
        """Test validation fails when claimed files don't exist."""
        state = ProjectState(
            project_path=tmp_path,
            has_pyproject_toml=True,  # Claim file exists but it doesn't
        )

        assert not state.validate()

    def test_validate_pyproject_toml_valid(self, tmp_path: Path) -> None:
        """Test pyproject.toml validation with valid file."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("[project]\nname = 'test'\n")

        state = ProjectState(project_path=tmp_path, has_pyproject_toml=True)
        assert state.validate_pyproject_toml()

    def test_validate_pyproject_toml_empty(self, tmp_path: Path) -> None:
        """Test pyproject.toml validation fails with empty file."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("")

        state = ProjectState(project_path=tmp_path, has_pyproject_toml=True)
        assert not state.validate_pyproject_toml()

    def test_validate_requirements_txt_valid(self, tmp_path: Path) -> None:
        """Test requirements.txt validation with valid file."""
        requirements_path = tmp_path / "requirements.txt"
        requirements_path.write_text("pytest>=7.0.0\nrequests==2.28.0\n")

        state = ProjectState(project_path=tmp_path, has_requirements_txt=True)
        assert state.validate_requirements_txt()

    def test_validate_requirements_txt_with_comments(self, tmp_path: Path) -> None:
        """Test requirements.txt validation handles comments."""
        requirements_path = tmp_path / "requirements.txt"
        requirements_path.write_text("# Comment\npytest>=7.0.0\n\n# Another comment\nrequests==2.28.0\n")

        state = ProjectState(project_path=tmp_path, has_requirements_txt=True)
        assert state.validate_requirements_txt()

    def test_has_modern_config_true(self, tmp_path: Path) -> None:
        """Test has_modern_config returns True when pyproject.toml exists."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        state = ProjectState(project_path=tmp_path, has_pyproject_toml=True)
        assert state.has_modern_config()

    def test_has_modern_config_false(self, tmp_path: Path) -> None:
        """Test has_modern_config returns False without pyproject.toml."""
        state = ProjectState(project_path=tmp_path, has_pyproject_toml=False)
        assert not state.has_modern_config()

    def test_needs_migration_true(self, tmp_path: Path) -> None:
        """Test needs_migration returns True when only requirements.txt exists."""
        state = ProjectState(
            project_path=tmp_path,
            has_requirements_txt=True,
            has_pyproject_toml=False,
        )
        assert state.needs_migration()

    def test_needs_migration_false(self, tmp_path: Path) -> None:
        """Test needs_migration returns False when pyproject.toml exists."""
        state = ProjectState(
            project_path=tmp_path,
            has_requirements_txt=True,
            has_pyproject_toml=True,
        )
        assert not state.needs_migration()

    def test_needs_dependency_migration(self, tmp_path: Path) -> None:
        """Test needs_dependency_migration with migration needed."""
        dep_analysis = DependencyAnalysis(
            requirements_packages=[Package(name="pytest", version="7.0.0")],
            migration_needed=True,
        )

        state = ProjectState(
            project_path=tmp_path,
            has_requirements_txt=True,
            has_pyproject_toml=True,
            dependency_analysis=dep_analysis,
        )
        assert state.needs_dependency_migration()

    def test_get_missing_security_tools(self, tmp_path: Path) -> None:
        """Test getting list of missing security tools."""
        state = ProjectState(
            project_path=tmp_path,
            security_tools={
                SecurityTool.BANDIT: True,
                SecurityTool.SAFETY: False,
                SecurityTool.GITLEAKS: False,
            },
        )

        missing = state.get_missing_security_tools()
        assert SecurityTool.SAFETY in missing
        assert SecurityTool.GITLEAKS in missing
        assert SecurityTool.BANDIT not in missing

    def test_get_missing_quality_tools(self, tmp_path: Path) -> None:
        """Test getting list of missing quality tools."""
        state = ProjectState(
            project_path=tmp_path,
            quality_tools={
                QualityTool.RUFF: True,
                QualityTool.MYPY: False,
            },
        )

        missing = state.get_missing_quality_tools()
        assert QualityTool.MYPY in missing
        assert QualityTool.RUFF not in missing

    def test_get_configured_tools(self, tmp_path: Path) -> None:
        """Test getting set of configured tool names."""
        state = ProjectState(
            project_path=tmp_path,
            current_tools={
                "ruff": ToolConfig(name="ruff", config={}),
                "mypy": ToolConfig(name="mypy", config={}),
            },
        )

        tools = state.get_configured_tools()
        assert "ruff" in tools
        assert "mypy" in tools
        assert len(tools) == 2

    def test_has_ci_security_checks(self, tmp_path: Path) -> None:
        """Test checking for CI security checks."""
        workflow_path = tmp_path / ".github" / "workflows" / "security.yml"
        workflow_path.parent.mkdir(parents=True)
        workflow_path.write_text("name: Security\n")

        state = ProjectState(
            project_path=tmp_path,
            ci_workflows=[
                Workflow(
                    name="security",
                    file_path=workflow_path,
                    has_security_checks=True,
                )
            ],
        )

        assert state.has_ci_security_checks()

    def test_has_ci_quality_checks(self, tmp_path: Path) -> None:
        """Test checking for CI quality checks."""
        workflow_path = tmp_path / ".github" / "workflows" / "quality.yml"
        workflow_path.parent.mkdir(parents=True)
        workflow_path.write_text("name: Quality\n")

        state = ProjectState(
            project_path=tmp_path,
            ci_workflows=[
                Workflow(
                    name="quality",
                    file_path=workflow_path,
                    has_quality_checks=True,
                )
            ],
        )

        assert state.has_ci_quality_checks()

    def test_get_dependency_manager_from_files_poetry(self, tmp_path: Path) -> None:
        """Test detecting Poetry as dependency manager."""
        (tmp_path / "poetry.lock").write_text("")

        state = ProjectState(project_path=tmp_path)
        manager = state.get_dependency_manager_from_files()

        assert manager == DependencyManager.POETRY

    def test_get_dependency_manager_from_files_pdm(self, tmp_path: Path) -> None:
        """Test detecting PDM as dependency manager."""
        (tmp_path / "pdm.lock").write_text("")

        state = ProjectState(project_path=tmp_path)
        manager = state.get_dependency_manager_from_files()

        assert manager == DependencyManager.PDM

    def test_get_dependency_manager_from_files_pip(self, tmp_path: Path) -> None:
        """Test detecting pip as dependency manager."""
        (tmp_path / "requirements.txt").write_text("pytest>=7.0.0\n")

        state = ProjectState(project_path=tmp_path, has_requirements_txt=True)
        manager = state.get_dependency_manager_from_files()

        assert manager == DependencyManager.PIP

    def test_refresh_file_detection(self, tmp_path: Path) -> None:
        """Test refreshing file detection updates state."""
        state = ProjectState(project_path=tmp_path)
        assert not state.has_pyproject_toml

        # Create file after state creation
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        # Refresh detection
        state.refresh_file_detection()

        assert state.has_pyproject_toml

    def test_to_dict(self, tmp_path: Path) -> None:
        """Test converting ProjectState to dictionary."""
        state = ProjectState(
            project_path=tmp_path,
            has_pyproject_toml=True,
            python_version="3.12",
        )

        data = state.to_dict()

        assert data["project_path"] == str(tmp_path)
        assert data["has_pyproject_toml"] is True
        assert data["python_version"] == "3.12"

    def test_from_dict(self, tmp_path: Path) -> None:
        """Test creating ProjectState from dictionary."""
        data = {
            "project_path": str(tmp_path),
            "has_pyproject_toml": True,
            "has_requirements_txt": False,
            "python_version": "3.12",
        }

        state = ProjectState.from_dict(data)

        assert state.project_path == tmp_path
        assert state.has_pyproject_toml is True
        assert state.python_version == "3.12"

    def test_validate_tool_configurations(self, tmp_path: Path) -> None:
        """Test validation fails when tool config name doesn't match key."""
        state = ProjectState(
            project_path=tmp_path,
            current_tools={
                "ruff": ToolConfig(name="wrong_name", config={}),  # Mismatched name
            },
        )

        assert not state.validate()

    def test_validate_workflows_with_missing_files(self, tmp_path: Path) -> None:
        """Test validation fails when workflow files don't exist."""
        nonexistent_path = tmp_path / ".github" / "workflows" / "missing.yml"

        state = ProjectState(
            project_path=tmp_path,
            ci_workflows=[
                Workflow(
                    name="missing",
                    file_path=nonexistent_path,
                )
            ],
        )

        assert not state.validate()
