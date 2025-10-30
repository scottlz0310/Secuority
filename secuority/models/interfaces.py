"""Core interfaces that define system boundaries for Secuority."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class ChangeType(Enum):
    """Types of configuration changes."""
    CREATE = "create"
    UPDATE = "update"
    MERGE = "merge"


@dataclass
class ProjectState:
    """Represents the current state of a Python project."""
    project_path: Path
    has_pyproject_toml: bool
    has_requirements_txt: bool
    has_setup_py: bool
    has_gitignore: bool
    dependency_manager: Optional[str]  # poetry, pdm, setuptools-scm
    current_tools: Dict[str, Any]
    security_tools: Dict[str, bool]
    ci_workflows: List[str]


@dataclass
class ConfigChange:
    """Represents a configuration change to be applied."""
    file_path: Path
    change_type: ChangeType
    old_content: Optional[str]
    new_content: str
    description: str
    requires_backup: bool


@dataclass
class ApplyResult:
    """Result of applying configuration changes."""
    successful_changes: List[ConfigChange]
    failed_changes: List[tuple]  # (ConfigChange, Exception)
    conflicts: List[str]
    backups_created: List[Path]


class ProjectAnalyzerInterface(ABC):
    """Interface for project analysis functionality."""
    
    @abstractmethod
    def analyze_project(self, project_path: Path) -> ProjectState:
        """Analyze a Python project and return its current state."""

    @abstractmethod
    def detect_configuration_files(self, project_path: Path) -> Dict[str, Path]:
        """Detect existing configuration files in the project."""

    @abstractmethod
    def analyze_dependencies(self, project_path: Path) -> Dict[str, Any]:
        """Analyze project dependencies and their configuration."""

    @abstractmethod
    def check_security_tools(self, project_path: Path) -> Dict[str, bool]:
        """Check which security tools are configured in the project."""


class TemplateManagerInterface(ABC):
    """Interface for template management functionality."""
    
    @abstractmethod
    def load_templates(self) -> Dict[str, str]:
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
    def apply_changes(
        self, changes: List[ConfigChange], dry_run: bool = False
    ) -> ApplyResult:
        """Apply configuration changes to the project."""

    @abstractmethod
    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of the specified file."""

    @abstractmethod
    def merge_configurations(
        self, existing: Dict[str, Any], template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge existing configuration with template configuration."""


class GitHubClientInterface(ABC):
    """Interface for GitHub API integration."""
    
    @abstractmethod
    def check_push_protection(self, repo: str) -> bool:
        """Check if GitHub Push Protection is enabled for the repository."""

    @abstractmethod
    def get_dependabot_config(self, repo: str) -> Dict[str, Any]:
        """Get Dependabot configuration for the repository."""

    @abstractmethod
    def list_workflows(self, repo: str) -> List[str]:
        """List GitHub Actions workflows in the repository."""

    @abstractmethod
    def check_security_settings(self, repo: str) -> Dict[str, Any]:
        """Check repository security settings."""


class CLIInterface(ABC):
    """Interface for CLI command implementations."""
    
    @abstractmethod
    def check(self, project_path: Path, verbose: bool = False) -> None:
        """Execute the check command to analyze project configuration."""

    @abstractmethod
    def apply(
        self, project_path: Path, dry_run: bool = False, force: bool = False
    ) -> None:
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