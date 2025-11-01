"""Tests for exception hierarchy and error handling."""

import pytest

from secuority.models.exceptions import (
    BackupError,
    ConfigurationConflictError,
    ConfigurationError,
    DependencyAnalysisError,
    FileOperationError,
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubRateLimitError,
    ProjectAnalysisError,
    SecuorityError,
    SecurityToolError,
    TemplateError,
    TemplateNotFoundError,
    TemplateParsingError,
    ValidationError,
)


class TestSecuorityError:
    """Tests for base SecuorityError exception."""

    def test_basic_error_creation(self) -> None:
        """Test creating a basic error with message."""
        error = SecuorityError("Test error message")
        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.details == {}
        assert error.exit_code == 1

    def test_error_with_details(self) -> None:
        """Test creating error with additional details."""
        details = {"key": "value", "count": 42}
        error = SecuorityError("Test error", details=details)
        assert error.details == details
        assert error.details["key"] == "value"
        assert error.details["count"] == 42

    def test_error_with_custom_exit_code(self) -> None:
        """Test creating error with custom exit code."""
        error = SecuorityError("Test error", exit_code=2)
        assert error.exit_code == 2

    def test_error_inheritance(self) -> None:
        """Test that SecuorityError inherits from Exception."""
        error = SecuorityError("Test error")
        assert isinstance(error, Exception)


class TestProjectAnalysisError:
    """Tests for ProjectAnalysisError exception."""

    def test_basic_project_analysis_error(self) -> None:
        """Test creating project analysis error."""
        error = ProjectAnalysisError("Analysis failed")
        assert str(error) == "Analysis failed"
        assert isinstance(error, SecuorityError)

    def test_project_analysis_error_with_path(self) -> None:
        """Test project analysis error with project path."""
        error = ProjectAnalysisError("Analysis failed", project_path="/path/to/project")
        assert error.details["project_path"] == "/path/to/project"

    def test_project_analysis_error_with_details(self) -> None:
        """Test project analysis error with additional details."""
        error = ProjectAnalysisError(
            "Analysis failed",
            project_path="/path/to/project",
            details={"reason": "missing files"},
        )
        assert error.details["project_path"] == "/path/to/project"
        assert error.details["reason"] == "missing files"


class TestTemplateError:
    """Tests for template-related exceptions."""

    def test_basic_template_error(self) -> None:
        """Test creating basic template error."""
        error = TemplateError("Template error")
        assert str(error) == "Template error"
        assert isinstance(error, SecuorityError)

    def test_template_error_with_name(self) -> None:
        """Test template error with template name."""
        error = TemplateError("Template error", template_name="pyproject.toml.template")
        assert error.details["template_name"] == "pyproject.toml.template"

    def test_template_not_found_error(self) -> None:
        """Test TemplateNotFoundError."""
        error = TemplateNotFoundError("config.yaml")
        assert "config.yaml" in str(error)
        assert error.details["template_name"] == "config.yaml"
        assert isinstance(error, TemplateError)

    def test_template_not_found_with_search_paths(self) -> None:
        """Test TemplateNotFoundError with search paths."""
        search_paths = ["/path/1", "/path/2"]
        error = TemplateNotFoundError("config.yaml", search_paths=search_paths)
        assert "config.yaml" in str(error)
        assert error.details["search_paths"] == search_paths

    def test_template_parsing_error(self) -> None:
        """Test TemplateParsingError."""
        error = TemplateParsingError("config.yaml", "Invalid YAML syntax")
        assert "config.yaml" in str(error)
        assert "Invalid YAML syntax" in str(error)
        assert error.details["template_name"] == "config.yaml"
        assert error.details["parsing_error"] == "Invalid YAML syntax"
        assert isinstance(error, TemplateError)


class TestGitHubAPIError:
    """Tests for GitHub API-related exceptions."""

    def test_basic_github_api_error(self) -> None:
        """Test creating basic GitHub API error."""
        error = GitHubAPIError("API call failed")
        assert str(error) == "API call failed"
        assert isinstance(error, SecuorityError)

    def test_github_api_error_with_status_code(self) -> None:
        """Test GitHub API error with status code."""
        error = GitHubAPIError("API call failed", status_code=404)
        assert error.details["status_code"] == 404

    def test_github_api_error_with_response_data(self) -> None:
        """Test GitHub API error with response data."""
        response_data = {"message": "Not Found", "documentation_url": "https://docs.github.com"}
        error = GitHubAPIError("API call failed", response_data=response_data)
        assert error.details["response_data"] == response_data

    def test_github_authentication_error(self) -> None:
        """Test GitHubAuthenticationError."""
        error = GitHubAuthenticationError()
        assert "authentication failed" in str(error).lower()
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in str(error)
        assert isinstance(error, GitHubAPIError)

    def test_github_authentication_error_custom_message(self) -> None:
        """Test GitHubAuthenticationError with custom message."""
        error = GitHubAuthenticationError("Custom auth error")
        assert str(error) == "Custom auth error"

    def test_github_rate_limit_error(self) -> None:
        """Test GitHubRateLimitError."""
        error = GitHubRateLimitError()
        assert "rate limit exceeded" in str(error).lower()
        assert isinstance(error, GitHubAPIError)

    def test_github_rate_limit_error_with_reset_time(self) -> None:
        """Test GitHubRateLimitError with reset time."""
        reset_time = 1234567890
        error = GitHubRateLimitError(reset_time=reset_time)
        assert str(reset_time) in str(error)
        assert error.details["reset_time"] == reset_time


class TestConfigurationError:
    """Tests for configuration-related exceptions."""

    def test_basic_configuration_error(self) -> None:
        """Test creating basic configuration error."""
        error = ConfigurationError("Config error")
        assert str(error) == "Config error"
        assert isinstance(error, SecuorityError)

    def test_configuration_error_with_file_path(self) -> None:
        """Test configuration error with file path."""
        error = ConfigurationError("Config error", file_path="/path/to/config.toml")
        assert error.details["file_path"] == "/path/to/config.toml"

    def test_configuration_conflict_error(self) -> None:
        """Test ConfigurationConflictError."""
        conflicts = ["conflict1", "conflict2"]
        error = ConfigurationConflictError("Conflicts detected", conflicts=conflicts)
        assert error.details["conflicts"] == conflicts
        assert isinstance(error, ConfigurationError)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_basic_validation_error(self) -> None:
        """Test creating basic validation error."""
        error = ValidationError("Validation failed")
        assert str(error) == "Validation failed"
        assert isinstance(error, SecuorityError)

    def test_validation_error_with_errors(self) -> None:
        """Test validation error with validation errors list."""
        validation_errors = ["Missing required field", "Invalid format"]
        error = ValidationError("Validation failed", validation_errors=validation_errors)
        assert error.details["validation_errors"] == validation_errors


class TestFileOperationError:
    """Tests for file operation-related exceptions."""

    def test_basic_file_operation_error(self) -> None:
        """Test creating basic file operation error."""
        error = FileOperationError("File operation failed")
        assert str(error) == "File operation failed"
        assert isinstance(error, SecuorityError)

    def test_file_operation_error_with_details(self) -> None:
        """Test file operation error with file path and operation."""
        error = FileOperationError(
            "File operation failed",
            file_path="/path/to/file.txt",
            operation="write",
        )
        assert error.details["file_path"] == "/path/to/file.txt"
        assert error.details["operation"] == "write"

    def test_backup_error(self) -> None:
        """Test BackupError."""
        error = BackupError(
            "Backup failed",
            original_file="/path/to/original.txt",
            backup_file="/path/to/backup.txt",
        )
        assert error.details["operation"] == "backup"
        assert error.details["original_file"] == "/path/to/original.txt"
        assert error.details["backup_file"] == "/path/to/backup.txt"
        assert isinstance(error, FileOperationError)


class TestDependencyAnalysisError:
    """Tests for DependencyAnalysisError exception."""

    def test_basic_dependency_analysis_error(self) -> None:
        """Test creating basic dependency analysis error."""
        error = DependencyAnalysisError("Dependency analysis failed")
        assert str(error) == "Dependency analysis failed"
        assert isinstance(error, ProjectAnalysisError)

    def test_dependency_analysis_error_with_file(self) -> None:
        """Test dependency analysis error with dependency file."""
        error = DependencyAnalysisError(
            "Dependency analysis failed",
            dependency_file="requirements.txt",
        )
        assert error.details["dependency_file"] == "requirements.txt"


class TestSecurityToolError:
    """Tests for SecurityToolError exception."""

    def test_basic_security_tool_error(self) -> None:
        """Test creating basic security tool error."""
        error = SecurityToolError("Security tool failed")
        assert str(error) == "Security tool failed"
        assert isinstance(error, SecuorityError)

    def test_security_tool_error_with_tool_name(self) -> None:
        """Test security tool error with tool name."""
        error = SecurityToolError("Security tool failed", tool_name="bandit")
        assert error.details["tool_name"] == "bandit"


class TestExceptionRaising:
    """Tests for raising and catching exceptions."""

    def test_raise_and_catch_secuority_error(self) -> None:
        """Test raising and catching SecuorityError."""
        with pytest.raises(SecuorityError) as exc_info:
            raise SecuorityError("Test error")
        assert str(exc_info.value) == "Test error"

    def test_catch_specific_exception(self) -> None:
        """Test catching specific exception type."""
        with pytest.raises(TemplateNotFoundError) as exc_info:
            raise TemplateNotFoundError("missing.template")
        # Assertion moved outside context manager to avoid unreachable code
        assert "missing.template" in str(exc_info.value)

    def test_catch_base_exception(self) -> None:
        """Test catching derived exception with base class."""
        with pytest.raises(SecuorityError) as exc_info:
            raise ProjectAnalysisError("Analysis failed")
        assert isinstance(exc_info.value, ProjectAnalysisError)

    def test_exception_details_preserved(self) -> None:
        """Test that exception details are preserved when raised."""
        details = {"key": "value", "count": 42}
        with pytest.raises(SecuorityError) as exc_info:
            raise SecuorityError("Test error", details=details)
        # Assertion moved outside context manager to avoid unreachable code
        assert exc_info.value.details == details
