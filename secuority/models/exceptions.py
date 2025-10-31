"""Exception hierarchy for Secuority."""

from typing import Any


class SecuorityError(Exception):
    """Base exception class for all Secuority errors.

    Attributes:
        message: Human-readable error message
        details: Additional error details for debugging
        exit_code: Suggested exit code for CLI
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.exit_code = exit_code

    def __str__(self) -> str:
        return self.message


class ProjectAnalysisError(SecuorityError):
    """Exception raised during project analysis.

    Used when the tool cannot properly analyze the project structure,
    dependencies, or existing configurations.
    """

    def __init__(self, message: str, project_path: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if project_path:
            self.details["project_path"] = project_path


class TemplateError(SecuorityError):
    """Exception raised during template operations.

    Used for template loading, parsing, updating, or application failures.
    """

    def __init__(self, message: str, template_name: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if template_name:
            self.details["template_name"] = template_name


class TemplateNotFoundError(TemplateError):
    """Exception raised when a required template cannot be found."""

    def __init__(self, template_name: str, search_paths: list | None = None):
        message = f"Template '{template_name}' not found"
        if search_paths:
            message += f" in paths: {', '.join(search_paths)}"
        super().__init__(message, template_name=template_name)
        if search_paths:
            self.details["search_paths"] = search_paths


class TemplateParsingError(TemplateError):
    """Exception raised when template content cannot be parsed."""

    def __init__(self, template_name: str, parsing_error: str):
        message = f"Failed to parse template '{template_name}': {parsing_error}"
        super().__init__(message, template_name=template_name)
        self.details["parsing_error"] = parsing_error


class GitHubAPIError(SecuorityError):
    """Exception raised during GitHub API operations.

    Note: These are typically handled as warnings to allow execution to continue.
    """

    def __init__(self, message: str, status_code: int | None = None, response_data: dict | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if status_code:
            self.details["status_code"] = status_code
        if response_data:
            self.details["response_data"] = response_data


class GitHubAuthenticationError(GitHubAPIError):
    """Exception raised when GitHub API authentication fails."""

    def __init__(
        self,
        message: str = "GitHub API authentication failed. Please check your GITHUB_PERSONAL_ACCESS_TOKEN.",
        **kwargs,
    ):
        super().__init__(message, **kwargs)


class GitHubRateLimitError(GitHubAPIError):
    """Exception raised when GitHub API rate limit is exceeded."""

    def __init__(self, reset_time: int | None = None, **kwargs):
        message = "GitHub API rate limit exceeded"
        if reset_time:
            message += f". Rate limit resets at {reset_time}"
        super().__init__(message, **kwargs)
        if reset_time:
            self.details["reset_time"] = reset_time


class ConfigurationError(SecuorityError):
    """Exception raised during configuration application.

    Used when configuration changes cannot be applied safely.
    """

    def __init__(self, message: str, file_path: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if file_path:
            self.details["file_path"] = file_path


class ConfigurationConflictError(ConfigurationError):
    """Exception raised when configuration conflicts cannot be resolved automatically."""

    def __init__(self, message: str, conflicts: list | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if conflicts:
            self.details["conflicts"] = conflicts


class ValidationError(SecuorityError):
    """Exception raised during configuration validation.

    Used when configuration files or templates fail validation checks.
    """

    def __init__(self, message: str, validation_errors: list | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if validation_errors:
            self.details["validation_errors"] = validation_errors


class FileOperationError(SecuorityError):
    """Exception raised during file operations.

    Used for file reading, writing, backup, or permission issues.
    """

    def __init__(self, message: str, file_path: str | None = None, operation: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if file_path:
            self.details["file_path"] = file_path
        if operation:
            self.details["operation"] = operation


class BackupError(FileOperationError):
    """Exception raised when backup operations fail."""

    def __init__(self, message: str, original_file: str | None = None, backup_file: str | None = None, **kwargs):
        super().__init__(message, operation="backup", **kwargs)
        if original_file:
            self.details["original_file"] = original_file
        if backup_file:
            self.details["backup_file"] = backup_file


class DependencyAnalysisError(ProjectAnalysisError):
    """Exception raised during dependency analysis."""

    def __init__(self, message: str, dependency_file: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if dependency_file:
            self.details["dependency_file"] = dependency_file


class SecurityToolError(SecuorityError):
    """Exception raised during security tool configuration or execution."""

    def __init__(self, message: str, tool_name: str | None = None, **kwargs):
        super().__init__(message, **kwargs)
        if tool_name:
            self.details["tool_name"] = tool_name
