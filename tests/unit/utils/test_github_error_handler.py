"""Unit tests for GitHubErrorHandler."""

from unittest.mock import patch

import pytest

from secuority.models.exceptions import GitHubAPIError
from secuority.utils.github_error_handler import (
    GitHubErrorHandler,
    safe_github_call,
    with_github_error_handling,
)


class TestGitHubErrorHandler:
    """Test GitHubErrorHandler functionality."""

    @pytest.fixture
    def handler(self) -> GitHubErrorHandler:
        """Create GitHubErrorHandler instance."""
        return GitHubErrorHandler(continue_on_error=True, show_warnings=False)

    @pytest.fixture
    def handler_with_warnings(self) -> GitHubErrorHandler:
        """Create GitHubErrorHandler instance with warnings enabled."""
        return GitHubErrorHandler(continue_on_error=True, show_warnings=True)

    def test_handle_api_call_success(self, handler: GitHubErrorHandler) -> None:
        """Test successful API call."""

        def successful_func() -> str:
            return "success"

        result = handler.handle_api_call(successful_func, operation_name="test operation")

        assert result == "success"
        assert len(handler.errors_encountered) == 0

    def test_handle_api_call_with_github_error(self, handler: GitHubErrorHandler) -> None:
        """Test API call that raises GitHubAPIError."""

        def failing_func() -> str:
            raise GitHubAPIError("API error")

        result = handler.handle_api_call(
            failing_func,
            fallback_value="fallback",
            operation_name="test operation",
        )

        assert result == "fallback"
        assert len(handler.errors_encountered) == 1
        assert handler.errors_encountered[0]["operation"] == "test operation"

    def test_handle_api_call_with_unexpected_error(self, handler: GitHubErrorHandler) -> None:
        """Test API call that raises unexpected error."""

        def failing_func() -> str:
            raise ValueError("Unexpected error")

        result = handler.handle_api_call(
            failing_func,
            fallback_value="fallback",
            operation_name="test operation",
        )

        assert result == "fallback"

    def test_handle_api_call_with_args_and_kwargs(self, handler: GitHubErrorHandler) -> None:
        """Test API call with arguments and keyword arguments."""

        def func_with_args(a: int, b: int, c: int = 0) -> int:
            return a + b + c

        result = handler.handle_api_call(
            func_with_args,
            1,
            2,
            c=3,
            operation_name="test operation",
        )

        assert result == 6

    def test_create_user_friendly_message_auth_error(self, handler: GitHubErrorHandler) -> None:
        """Test user-friendly message for authentication error."""
        error = GitHubAPIError("Authentication failed (401)")
        message = handler._create_user_friendly_message(error, "test operation")

        assert "authentication failed" in message.lower()
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in message

    def test_create_user_friendly_message_rate_limit(self, handler: GitHubErrorHandler) -> None:
        """Test user-friendly message for rate limit error."""
        error = GitHubAPIError("Rate limit exceeded (403)")
        message = handler._create_user_friendly_message(error, "test operation")

        assert "rate limit" in message.lower()
        assert "try again later" in message.lower()

    def test_create_user_friendly_message_not_found(self, handler: GitHubErrorHandler) -> None:
        """Test user-friendly message for not found error."""
        error = GitHubAPIError("Repository not found (404)")
        message = handler._create_user_friendly_message(error, "test operation")

        assert "not found" in message.lower()
        assert "private repository" in message.lower()

    def test_create_user_friendly_message_network_error(self, handler: GitHubErrorHandler) -> None:
        """Test user-friendly message for network error."""
        error = GitHubAPIError("Network error occurred")
        message = handler._create_user_friendly_message(error, "test operation")

        assert "network error" in message.lower()
        assert "internet connection" in message.lower()

    def test_create_user_friendly_message_generic_error(self, handler: GitHubErrorHandler) -> None:
        """Test user-friendly message for generic error."""
        error = GitHubAPIError("Some other error")
        message = handler._create_user_friendly_message(error, "test operation")

        assert "GitHub API error" in message
        assert "test operation" in message

    def test_log_and_warn_without_warnings(self, handler: GitHubErrorHandler) -> None:
        """Test logging without displaying warnings."""
        with patch("secuority.utils.github_error_handler.logger") as mock_logger:
            handler._log_and_warn("test message")

            mock_logger.warning.assert_called_once_with("test message")

    def test_log_and_warn_with_warnings(self, handler_with_warnings: GitHubErrorHandler) -> None:
        """Test logging with displaying warnings."""
        with patch("secuority.utils.github_error_handler.logger") as mock_logger:
            handler_with_warnings._log_and_warn("test message")

            mock_logger.warning.assert_called_once_with("test message")

    def test_get_error_summary_no_errors(self, handler: GitHubErrorHandler) -> None:
        """Test error summary with no errors."""
        summary = handler.get_error_summary()

        assert summary["total_errors"] == 0
        assert summary["errors"] == []
        assert summary["has_auth_errors"] is False
        assert summary["has_rate_limit_errors"] is False
        assert summary["has_network_errors"] is False

    def test_get_error_summary_with_errors(self, handler: GitHubErrorHandler) -> None:
        """Test error summary with various errors."""
        handler.errors_encountered = [
            {"operation": "op1", "error": "Authentication failed", "type": "github_api_error"},
            {"operation": "op2", "error": "Rate limit exceeded", "type": "github_api_error"},
            {"operation": "op3", "error": "Network error", "type": "github_api_error"},
        ]

        summary = handler.get_error_summary()

        assert summary["total_errors"] == 3
        assert summary["has_auth_errors"] is True
        assert summary["has_rate_limit_errors"] is True
        assert summary["has_network_errors"] is True

    def test_print_setup_instructions_no_errors(self, handler: GitHubErrorHandler) -> None:
        """Test printing setup instructions with no errors."""
        # Should not raise any exceptions
        handler.print_setup_instructions()

    def test_print_setup_instructions_with_auth_errors(self, handler: GitHubErrorHandler) -> None:
        """Test printing setup instructions with auth errors."""
        handler.errors_encountered = [
            {"operation": "op1", "error": "Authentication failed", "type": "github_api_error"},
        ]

        # Should not raise any exceptions
        handler.print_setup_instructions()

    def test_print_setup_instructions_with_rate_limit_errors(self, handler: GitHubErrorHandler) -> None:
        """Test printing setup instructions with rate limit errors."""
        handler.errors_encountered = [
            {"operation": "op1", "error": "Rate limit exceeded", "type": "github_api_error"},
        ]

        # Should not raise any exceptions
        handler.print_setup_instructions()

    def test_print_setup_instructions_with_network_errors(self, handler: GitHubErrorHandler) -> None:
        """Test printing setup instructions with network errors."""
        handler.errors_encountered = [
            {"operation": "op1", "error": "Network error", "type": "github_api_error"},
        ]

        # Should not raise any exceptions
        handler.print_setup_instructions()


class TestWithGitHubErrorHandling:
    """Test with_github_error_handling decorator."""

    def test_decorator_success(self) -> None:
        """Test decorator with successful function."""

        @with_github_error_handling(operation_name="test op")
        def successful_func() -> str:
            return "success"

        result = successful_func()
        assert result == "success"

    def test_decorator_with_error(self) -> None:
        """Test decorator with failing function."""

        @with_github_error_handling(fallback_value="fallback", operation_name="test op", show_warnings=False)
        def failing_func() -> str:
            raise GitHubAPIError("API error")

        result = failing_func()
        assert result == "fallback"

    def test_decorator_with_args(self) -> None:
        """Test decorator with function arguments."""

        @with_github_error_handling(operation_name="test op")
        def func_with_args(a: int, b: int) -> int:
            return a + b

        result = func_with_args(1, 2)
        assert result == 3


class TestSafeGitHubCall:
    """Test safe_github_call function."""

    def test_safe_call_success(self) -> None:
        """Test safe call with successful function."""

        def successful_func() -> str:
            return "success"

        result = safe_github_call(successful_func, operation_name="test op", show_warnings=False)
        assert result == "success"

    def test_safe_call_with_error(self) -> None:
        """Test safe call with failing function."""

        def failing_func() -> str:
            raise GitHubAPIError("API error")

        result = safe_github_call(
            failing_func,
            fallback_value="fallback",
            operation_name="test op",
            show_warnings=False,
        )
        assert result == "fallback"

    def test_safe_call_with_args(self) -> None:
        """Test safe call with function arguments."""

        def func_with_args(a: int, b: int) -> int:
            return a + b

        result = safe_github_call(func_with_args, 1, 2, operation_name="test op", show_warnings=False)
        assert result == 3

    def test_safe_call_with_kwargs(self) -> None:
        """Test safe call with keyword arguments."""

        def func_with_kwargs(a: int, b: int = 0) -> int:
            return a + b

        result = safe_github_call(func_with_kwargs, 1, b=2, operation_name="test op", show_warnings=False)
        assert result == 3

    def test_safe_call_with_unexpected_error(self) -> None:
        """Test safe call with unexpected error."""

        def failing_func() -> str:
            raise ValueError("Unexpected error")

        result = safe_github_call(
            failing_func,
            fallback_value="fallback",
            operation_name="test op",
            show_warnings=False,
        )
        assert result == "fallback"
