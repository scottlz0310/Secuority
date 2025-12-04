"""Project state model with comprehensive validation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exceptions import ValidationError
from .interfaces import (
    DependencyAnalysis,
    DependencyManager,
    QualityTool,
    SecurityTool,
    ToolConfig,
    Workflow,
    validate_project_path,
)


@dataclass
class ProjectState:
    """Enhanced project state model with comprehensive validation methods."""

    project_path: Path
    has_pyproject_toml: bool = False
    has_requirements_txt: bool = False
    has_setup_py: bool = False
    has_gitignore: bool = False
    has_pre_commit_config: bool = False
    dependency_manager: DependencyManager | None = None
    current_tools: dict[str, ToolConfig] = field(default_factory=dict)
    security_tools: dict[SecurityTool, bool] = field(default_factory=dict)
    quality_tools: dict[QualityTool, bool] = field(default_factory=dict)
    ci_workflows: list[Workflow] = field(default_factory=list)
    dependency_analysis: DependencyAnalysis | None = None
    python_version: str | None = None

    def __post_init__(self) -> None:
        """Validate project state data after initialization."""
        if not validate_project_path(self.project_path):
            raise ValidationError(f"Invalid project path: {self.project_path}")

    def validate(self) -> bool:
        """Comprehensive validation of the project state."""
        try:
            # Validate project path exists and is accessible
            if not self.project_path.exists():
                return False

            if not self.project_path.is_dir():
                return False

            # Validate file existence claims
            pyproject_path = self.project_path / "pyproject.toml"
            if self.has_pyproject_toml and not pyproject_path.exists():
                return False

            requirements_path = self.project_path / "requirements.txt"
            if self.has_requirements_txt and not requirements_path.exists():
                return False

            setup_path = self.project_path / "setup.py"
            if self.has_setup_py and not setup_path.exists():
                return False

            gitignore_path = self.project_path / ".gitignore"
            if self.has_gitignore and not gitignore_path.exists():
                return False

            precommit_path = self.project_path / ".pre-commit-config.yaml"
            if self.has_pre_commit_config and not precommit_path.exists():
                return False

            # Validate tool configurations
            for tool_name, tool_config in self.current_tools.items():
                if tool_config.name != tool_name:
                    return False

            # Validate workflows
            return all(workflow.file_path.exists() for workflow in self.ci_workflows)
        except Exception:
            return False

    def validate_pyproject_toml(self) -> bool:
        """Validate pyproject.toml file structure and content."""
        if not self.has_pyproject_toml:
            return True  # No file to validate

        pyproject_path = self.project_path / "pyproject.toml"
        try:
            # For now, just check if file is readable
            # In a real implementation, you'd use tomllib or toml library
            with pyproject_path.open(encoding="utf-8") as f:
                content = f.read()
                return bool(content.strip())
        except (OSError, UnicodeDecodeError):
            return False

    def validate_requirements_txt(self) -> bool:
        """Validate requirements.txt file format."""
        if not self.has_requirements_txt:
            return True  # No file to validate

        requirements_path = self.project_path / "requirements.txt"
        try:
            with requirements_path.open(encoding="utf-8") as f:
                lines = f.readlines()

            # Basic format validation
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue  # Skip empty lines and comments

                # Basic package name validation (simplified)
                package_name = line.split("==")[0].split(">=")[0].split("<=")[0]
                package_name = package_name.split(">")[0].split("<")[0].split("~=")[0]
                if not any(c.isalnum() or c in "-_." for c in package_name):
                    return False

            return True
        except (OSError, UnicodeDecodeError):
            return False

    def validate_gitignore(self) -> bool:
        """Validate .gitignore file accessibility."""
        if not self.has_gitignore:
            return True  # No file to validate

        gitignore_path = self.project_path / ".gitignore"
        try:
            with gitignore_path.open(encoding="utf-8") as f:
                f.read()  # Just check if we can read it
            return True
        except (OSError, UnicodeDecodeError):
            return False

    def has_modern_config(self) -> bool:
        """Check if project uses modern configuration (pyproject.toml)."""
        return self.has_pyproject_toml and self.validate_pyproject_toml()

    def needs_migration(self) -> bool:
        """Check if project needs migration to modern configuration."""
        return self.has_requirements_txt and not self.has_pyproject_toml

    def needs_dependency_migration(self) -> bool:
        """Check if project needs dependency migration from requirements.txt."""
        return (
            self.has_requirements_txt
            and self.has_pyproject_toml
            and self.dependency_analysis is not None
            and self.dependency_analysis.migration_needed
        )

    def get_missing_security_tools(self) -> list[SecurityTool]:
        """Get list of missing security tools."""
        return [tool for tool, enabled in self.security_tools.items() if not enabled]

    def get_missing_quality_tools(self) -> list[QualityTool]:
        """Get list of missing quality tools."""
        return [tool for tool, enabled in self.quality_tools.items() if not enabled]

    def get_configured_tools(self) -> set[str]:
        """Get set of all configured tool names."""
        return set(self.current_tools.keys())

    def has_ci_security_checks(self) -> bool:
        """Check if CI workflows include security checks."""
        return any(workflow.has_security_checks for workflow in self.ci_workflows)

    def has_ci_quality_checks(self) -> bool:
        """Check if CI workflows include quality checks."""
        return any(workflow.has_quality_checks for workflow in self.ci_workflows)

    def get_dependency_manager_from_files(self) -> DependencyManager | None:
        """Detect dependency manager from project files."""
        # Check for Poetry
        if (self.project_path / "poetry.lock").exists():
            return DependencyManager.POETRY

        # Check for PDM
        if (self.project_path / "pdm.lock").exists():
            return DependencyManager.PDM

        # Check for Pipenv
        if (self.project_path / "Pipfile").exists():
            return DependencyManager.PIPENV

        # Check for Conda
        if (self.project_path / "environment.yml").exists():
            return DependencyManager.CONDA

        # Default to pip if requirements.txt exists
        if self.has_requirements_txt:
            return DependencyManager.PIP

        return None

    def refresh_file_detection(self) -> None:
        """Refresh file existence detection."""
        pyproject_path = self.project_path / "pyproject.toml"
        self.has_pyproject_toml = pyproject_path.exists()

        requirements_path = self.project_path / "requirements.txt"
        self.has_requirements_txt = requirements_path.exists()

        setup_path = self.project_path / "setup.py"
        self.has_setup_py = setup_path.exists()

        gitignore_path = self.project_path / ".gitignore"
        self.has_gitignore = gitignore_path.exists()

        precommit_path = self.project_path / ".pre-commit-config.yaml"
        self.has_pre_commit_config = precommit_path.exists()

        self.dependency_manager = self.get_dependency_manager_from_files()

    def to_dict(self) -> dict[str, Any]:
        """Convert project state to dictionary for serialization."""
        return {
            "project_path": str(self.project_path),
            "has_pyproject_toml": self.has_pyproject_toml,
            "has_requirements_txt": self.has_requirements_txt,
            "has_setup_py": self.has_setup_py,
            "has_gitignore": self.has_gitignore,
            "has_pre_commit_config": self.has_pre_commit_config,
            "dependency_manager": (self.dependency_manager.value if self.dependency_manager else None),
            "current_tools": {
                name: {
                    "name": config.name,
                    "enabled": config.enabled,
                    "version": config.version,
                    "config": config.config,
                }
                for name, config in self.current_tools.items()
            },
            "security_tools": {tool.value: enabled for tool, enabled in self.security_tools.items()},
            "quality_tools": {tool.value: enabled for tool, enabled in self.quality_tools.items()},
            "ci_workflows": [
                {
                    "name": w.name,
                    "file_path": str(w.file_path),
                    "triggers": w.triggers,
                    "jobs": w.jobs,
                    "has_security_checks": w.has_security_checks,
                    "has_quality_checks": w.has_quality_checks,
                }
                for w in self.ci_workflows
            ],
            "python_version": self.python_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        """Create ProjectState from dictionary."""
        # Simplified implementation for deserialization
        project_path = Path(data["project_path"])
        state = cls(project_path=project_path)

        # Set basic attributes
        basic_attrs = [
            "has_pyproject_toml",
            "has_requirements_txt",
            "has_setup_py",
            "has_gitignore",
            "has_pre_commit_config",
            "python_version",
        ]
        for attr in basic_attrs:
            if attr in data:
                setattr(state, attr, data[attr])

        # Set dependency manager
        if data.get("dependency_manager"):
            state.dependency_manager = DependencyManager(data["dependency_manager"])

        return state
