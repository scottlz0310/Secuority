"""Data models for Secuority."""

from .config import (
    ApplyResult,
    BackupStrategy,
    ChangeSet,
    ConfigChange,
    Conflict,
    ConflictResolution,
)
from .exceptions import (
    ConfigurationError,
    FileOperationError,
    GitHubAPIError,
    ProjectAnalysisError,
    SecuorityError,
    TemplateError,
    ValidationError,
)
from .interfaces import (
    ChangeType,
    DependencyAnalysis,
    DependencyManager,
    Package,
    QualityTool,
    SecurityTool,
    ToolConfig,
    Workflow,
    validate_file_path,
    validate_package_name,
    validate_project_path,
    validate_tool_config,
    validate_version_string,
)
from .project import ProjectState

__all__ = [
    # Enums
    "ChangeType",
    "DependencyManager",
    "SecurityTool",
    "QualityTool",
    "ConflictResolution",
    "BackupStrategy",
    # Data models
    "Package",
    "DependencyAnalysis",
    "ToolConfig",
    "Workflow",
    "ProjectState",
    "ConfigChange",
    "ApplyResult",
    "Conflict",
    "ChangeSet",
    # Validation functions
    "validate_project_path",
    "validate_file_path",
    "validate_package_name",
    "validate_version_string",
    "validate_tool_config",
    # Exceptions
    "SecuorityError",
    "ProjectAnalysisError",
    "TemplateError",
    "GitHubAPIError",
    "ConfigurationError",
    "ValidationError",
    "FileOperationError",
]
