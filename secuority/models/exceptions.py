"""Exception hierarchy for Secuority."""


class SecuorityError(Exception):
    """Base exception class for all Secuority errors."""


class ProjectAnalysisError(SecuorityError):
    """Exception raised during project analysis."""


class TemplateError(SecuorityError):
    """Exception raised during template operations."""


class GitHubAPIError(SecuorityError):
    """Exception raised during GitHub API operations."""


class ConfigurationError(SecuorityError):
    """Exception raised during configuration application."""


class ValidationError(SecuorityError):
    """Exception raised during configuration validation."""


class FileOperationError(SecuorityError):
    """Exception raised during file operations."""