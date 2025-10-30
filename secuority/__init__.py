"""
Secuority CLI - Python project security and quality configuration tool.
"""

from .cli.main import SecuorityCLI
from .core.engine import CoreEngine
from .models.exceptions import (
    ConfigurationError,
    FileOperationError,
    GitHubAPIError,
    ProjectAnalysisError,
    SecuorityError,
    TemplateError,
    ValidationError,
)
from .models.interfaces import (
    ApplyResult,
    CLIInterface,
    ChangeType,
    ConfigChange,
    ConfigurationApplierInterface,
    GitHubClientInterface,
    ProjectAnalyzerInterface,
    ProjectState,
    TemplateManagerInterface,
)

__version__ = "0.1.0"
__author__ = "Secuority Team"
__description__ = (
    "Automate and standardize Python project security and quality configurations"
)

__all__ = [
    "ApplyResult",
    "CLIInterface",
    "ChangeType",
    "ConfigChange",
    "ConfigurationApplierInterface",
    "ConfigurationError",
    "CoreEngine",
    "FileOperationError",
    "GitHubAPIError",
    "GitHubClientInterface",
    "ProjectAnalysisError",
    "ProjectAnalyzerInterface",
    "ProjectState",
    "SecuorityCLI",
    "SecuorityError",
    "TemplateError",
    "TemplateManagerInterface",
    "ValidationError",
]