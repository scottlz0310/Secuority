"""Core interfaces that define system boundaries for Secuority."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ChangeType(Enum):
    """Types of configuration changes."""

    CREATE = "create"
    UPDATE = "update"
    MERGE = "merge"


class DependencyManager(Enum):
    """Supported dependency managers."""

    POETRY = "poetry"
    PDM = "pdm"
    SETUPTOOLS_SCM = "setuptools-scm"
    PIP = "pip"
    PIPENV = "pipenv"
    CONDA = "conda"


class SecurityTool(Enum):
    """Supported security tools."""

    BANDIT = "bandit"
    SAFETY = "safety"
    GITLEAKS = "gitleaks"
    SEMGREP = "semgrep"


class QualityTool(Enum):
    """Supported code quality tools."""

    RUFF = "ruff"
    MYPY = "mypy"
    BLACK = "black"
    ISORT = "isort"
    FLAKE8 = "flake8"
    PYLINT = "pylint"


def validate_project_path(path: Path) -> bool:
    """Validate that a path exists and is a directory."""
    return path.exists() and path.is_dir()


def validate_file_path(path: Path) -> bool:
    """Validate that a path exists and is a file."""
    return path.exists() and path.is_file()


def validate_package_name(name: str) -> bool:
    """Validate Python package name format."""
    if not name or not isinstance(name, str):
        return False
    # Python package names should match PEP 508 naming convention
    pattern = r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])$"
    return bool(re.match(pattern, name, re.IGNORECASE))


def validate_version_string(version: str) -> bool:
    """Validate version string format (PEP 440)."""
    if not version or not isinstance(version, str):
        return False
    # Simplified PEP 440 version pattern
    pattern = (
        r"^([1-9][0-9]*!)?(0|[1-9][0-9]*)(\.(0|[1-9][0-9]*))*"
        r"((a|b|rc)(0|[1-9][0-9]*))?(\.post(0|[1-9][0-9]*))?"
        r"(\.dev(0|[1-9][0-9]*))?$"
    )
    return bool(re.match(pattern, version))


def validate_tool_config(config: dict[str, Any]) -> bool:
    """Validate tool configuration dictionary."""
    if not isinstance(config, dict):
        return False
    # Basic validation - ensure it's a dictionary with string keys
    return all(isinstance(key, str) for key in config.keys())


@dataclass
class Package:
    """Represents a Python package dependency."""

    name: str
    version: str | None = None
    extras: list[str] = field(default_factory=list)
    markers: str | None = None

    def __post_init__(self) -> None:
        """Validate package data after initialization."""
        if not validate_package_name(self.name):
            raise ValueError(f"Invalid package name: {self.name}")
        if self.version and not validate_version_string(self.version):
            raise ValueError(f"Invalid version string: {self.version}")


@dataclass
class DependencyAnalysis:
    """Analysis of project dependencies."""

    requirements_packages: list[Package] = field(default_factory=list)
    pyproject_dependencies: list[Package] = field(default_factory=list)
    extras_found: list[str] = field(default_factory=list)
    migration_needed: bool = False
    conflicts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate dependency analysis data."""
        if not isinstance(self.requirements_packages, list):
            raise ValueError("requirements_packages must be a list")
        if not isinstance(self.pyproject_dependencies, list):
            raise ValueError("pyproject_dependencies must be a list")


@dataclass
class ToolConfig:
    """Configuration for a development tool."""

    name: str
    config: dict[str, Any]
    enabled: bool = True
    version: str | None = None

    def __post_init__(self) -> None:
        """Validate tool configuration."""
        if not self.name:
            raise ValueError("Tool name cannot be empty")
        if not validate_tool_config(self.config):
            raise ValueError("Invalid tool configuration")


@dataclass
class Workflow:
    """Represents a CI/CD workflow."""

    name: str
    file_path: Path
    triggers: list[str] = field(default_factory=list)
    jobs: list[str] = field(default_factory=list)
    has_security_checks: bool = False
    has_quality_checks: bool = False

    def __post_init__(self) -> None:
        """Validate workflow data."""
        if not self.name:
            raise ValueError("Workflow name cannot be empty")


@dataclass
class ConfigChange:
    """Represents a configuration change to be applied."""

    file_path: Path
    change_type: ChangeType
    old_content: str | None
    new_content: str
    description: str
    requires_backup: bool


@dataclass
class ApplyResult:
    """Result of applying configuration changes."""

    successful_changes: list[ConfigChange]
    failed_changes: list[tuple]  # (ConfigChange, Exception)
    conflicts: list[str]
    backups_created: list[Path]


class ProjectAnalyzerInterface(ABC):
    """Interface for project analysis functionality."""

    @abstractmethod
    def analyze_project(self, project_path: Path) -> "ProjectState":
        """Analyze a Python project and return its current state."""

    @abstractmethod
    def detect_configuration_files(self, project_path: Path) -> dict[str, Path]:
        """Detect existing configuration files in the project."""

    @abstractmethod
    def analyze_dependencies(self, project_path: Path) -> dict[str, Any]:
        """Analyze project dependencies and their configuration."""

    @abstractmethod
    def check_security_tools(self, project_path: Path) -> dict[str, bool]:
        """Check which security tools are configured in the project."""


class TemplateManagerInterface(ABC):
    """Interface for template management functionality."""

    @abstractmethod
    def load_templates(self) -> dict[str, str]:
        """Load configuration templates."""

    @abstractmethod
    def get_template_directory(self) -> Path:
        """Get the directory where templates are stored."""

    @abstractmethod
    def update_templates(self) -> bool:
        """Update templates from remote source."""

    @abstractmethod
    def initialize_templates(self) -> None:
        """Initialize template directory with default templates."""


class ConfigurationApplierInterface(ABC):
    """Interface for applying configuration changes."""

    @abstractmethod
    def apply_changes(self, changes: list[ConfigChange], dry_run: bool = False) -> ApplyResult:
        """Apply configuration changes to the project."""

    @abstractmethod
    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of the specified file."""

    @abstractmethod
    def merge_configurations(self, existing: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
        """Merge existing configuration with template configuration."""


class GitHubClientInterface(ABC):
    """Interface for GitHub API integration."""

    @abstractmethod
    def check_push_protection(self, repo: str) -> bool:
        """Check if GitHub Push Protection is enabled for the repository."""

    @abstractmethod
    def get_dependabot_config(self, repo: str) -> dict[str, Any]:
        """Get Dependabot configuration for the repository."""

    @abstractmethod
    def list_workflows(self, repo: str) -> list[str]:
        """List GitHub Actions workflows in the repository."""

    @abstractmethod
    def check_security_settings(self, repo: str) -> dict[str, Any]:
        """Check repository security settings."""


@dataclass
class ProjectState:
    """Represents the current state of a Python project."""

    project_path: Path
    has_pyproject_toml: bool = False
    has_requirements_txt: bool = False
    has_setup_py: bool = False
    has_gitignore: bool = False
    has_pre_commit_config: bool = False
    has_security_md: bool = False
    dependency_manager: DependencyManager | None = None
    current_tools: dict[str, ToolConfig] = field(default_factory=dict)
    security_tools: dict[SecurityTool, bool] = field(default_factory=dict)
    quality_tools: dict[QualityTool, bool] = field(default_factory=dict)
    ci_workflows: list[Workflow] = field(default_factory=list)
    dependency_analysis: DependencyAnalysis | None = None
    python_version: str | None = None

    def __post_init__(self) -> None:
        """Validate project state data."""
        if not validate_project_path(self.project_path):
            raise ValueError(f"Invalid project path: {self.project_path}")

    def validate(self) -> bool:
        """Validate the entire project state."""
        try:
            # Validate project path
            if not validate_project_path(self.project_path):
                return False

            # Validate tool configurations
            for tool_config in self.current_tools.values():
                if not isinstance(tool_config, ToolConfig):
                    return False

            # Validate workflows
            for workflow in self.ci_workflows:
                if not isinstance(workflow, Workflow):
                    return False

            # Validate dependency analysis if present
            if self.dependency_analysis and not isinstance(self.dependency_analysis, DependencyAnalysis):
                return False

            return True
        except Exception:
            return False

    def has_modern_config(self) -> bool:
        """Check if project uses modern configuration (pyproject.toml)."""
        return self.has_pyproject_toml and not self.has_requirements_txt

    def needs_migration(self) -> bool:
        """Check if project needs migration to modern configuration."""
        return self.has_requirements_txt and not self.has_pyproject_toml

    def get_missing_security_tools(self) -> list[SecurityTool]:
        """Get list of missing security tools."""
        return [tool for tool, enabled in self.security_tools.items() if not enabled]

    def get_missing_quality_tools(self) -> list[QualityTool]:
        """Get list of missing quality tools."""
        return [tool for tool, enabled in self.quality_tools.items() if not enabled]

    def has_ci_security_checks(self) -> bool:
        """Check if CI workflows include security checks."""
        return any(workflow.has_security_checks for workflow in self.ci_workflows)

    def has_ci_quality_checks(self) -> bool:
        """Check if CI workflows include quality checks."""
        return any(workflow.has_quality_checks for workflow in self.ci_workflows)


class CLIInterface(ABC):
    """Interface for CLI command implementations."""

    @abstractmethod
    def check(self, project_path: Path, verbose: bool = False) -> None:
        """Execute the check command to analyze project configuration."""

    @abstractmethod
    def apply(self, project_path: Path, dry_run: bool = False, force: bool = False) -> None:
        """Execute the apply command to apply configuration changes."""

    @abstractmethod
    def template_list(self) -> None:
        """List available templates."""

    @abstractmethod
    def template_update(self) -> None:
        """Update templates from remote source."""

    @abstractmethod
    def init(self) -> None:
        """Initialize Secuority configuration."""
