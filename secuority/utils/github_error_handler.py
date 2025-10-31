"""Error handling utilities for GitHub API operations."""

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from rich.console import Console

from ..models.exceptions import GitHubAPIError

# Type variable for return type of wrapped functions
T = TypeVar("T")

logger = logging.getLogger(__name__)


class GitHubErrorHandler:
    """Handles GitHub API errors gracefully with warnings and continuation logic."""

    def __init__(self, continue_on_error: bool = True, show_warnings: bool = True):
        """Initialize error handler.

        Args:
            continue_on_error: Whether to continue execution after API errors
            show_warnings: Whether to display warnings for API errors
        """
        self.continue_on_error = continue_on_error
        self.show_warnings = show_warnings
        self.errors_encountered: list[dict[str, Any]] = []
        self.console = Console()

    def handle_api_call(
        self,
        func: Callable[..., T],
        *args,
        fallback_value: T | None = None,
        operation_name: str = "GitHub API operation",
        **kwargs,
    ) -> T | None:
        """Execute a GitHub API call with error handling.

        Args:
            func: Function to execute
            *args: Arguments to pass to function
            fallback_value: Value to return if operation fails
            operation_name: Name of operation for error messages
            **kwargs: Keyword arguments to pass to function

        Returns:
            Function result or fallback value if error occurred
        """
        try:
            return func(*args, **kwargs)
        except GitHubAPIError as e:
            self._handle_github_error(e, operation_name)
            return fallback_value
        except Exception as e:
            # Handle unexpected errors
            error_msg = f"Unexpected error during {operation_name}: {e}"
            self._log_and_warn(error_msg)
            return fallback_value

    def _handle_github_error(self, error: GitHubAPIError, operation_name: str) -> None:
        """Handle a GitHub API error.

        Args:
            error: The GitHub API error
            operation_name: Name of the operation that failed
        """
        error_info = {"operation": operation_name, "error": str(error), "type": "github_api_error"}
        self.errors_encountered.append(error_info)

        # Create user-friendly error message
        user_message = self._create_user_friendly_message(error, operation_name)
        self._log_and_warn(user_message)

    def _create_user_friendly_message(self, error: GitHubAPIError, operation_name: str) -> str:
        """Create a user-friendly error message.

        Args:
            error: The GitHub API error
            operation_name: Name of the operation that failed

        Returns:
            User-friendly error message
        """
        error_str = str(error).lower()

        if "authentication failed" in error_str or "401" in error_str:
            return (
                f"⚠️  GitHub API authentication failed during {operation_name}. "
                "Please check your GITHUB_PERSONAL_ACCESS_TOKEN environment variable. "
                "Continuing with local analysis only."
            )
        elif "rate limit" in error_str or "403" in error_str:
            return (
                f"⚠️  GitHub API rate limit exceeded during {operation_name}. "
                "Please try again later. Continuing with local analysis only."
            )
        elif "not found" in error_str or "404" in error_str:
            return (
                f"⚠️  Repository not found or not accessible during {operation_name}. "
                "This might be a private repository or the URL is incorrect. "
                "Continuing with local analysis only."
            )
        elif "network error" in error_str:
            return (
                f"⚠️  Network error during {operation_name}. "
                "Please check your internet connection. "
                "Continuing with local analysis only."
            )
        else:
            return f"⚠️  GitHub API error during {operation_name}: {error}. " "Continuing with local analysis only."

    def _log_and_warn(self, message: str) -> None:
        """Log error and display warning if configured.

        Args:
            message: Message to log and display
        """
        logger.warning(message)

        if self.show_warnings:
            self.console.print(message)

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of all errors encountered.

        Returns:
            Dictionary containing error summary
        """
        return {
            "total_errors": len(self.errors_encountered),
            "errors": self.errors_encountered,
            "has_auth_errors": any("authentication" in err["error"].lower() for err in self.errors_encountered),
            "has_rate_limit_errors": any("rate limit" in err["error"].lower() for err in self.errors_encountered),
            "has_network_errors": any("network" in err["error"].lower() for err in self.errors_encountered),
        }

    def print_setup_instructions(self) -> None:
        """Print instructions for setting up GitHub integration."""
        if not self.errors_encountered:
            return

        error_summary = self.get_error_summary()

        self.console.print("\n" + "=" * 60)
        self.console.print("GitHub Integration Setup Instructions")
        self.console.print("=" * 60)

        if error_summary["has_auth_errors"]:
            self.console.print("\n🔑 Authentication Issues:")
            self.console.print("   To enable GitHub integration, you need a personal access token.")
            self.console.print("   1. Go to https://github.com/settings/tokens")
            self.console.print("   2. Generate a new token with 'repo' scope")
            self.console.print("   3. Set the GITHUB_PERSONAL_ACCESS_TOKEN environment variable:")
            self.console.print("      export GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here")

        if error_summary["has_rate_limit_errors"]:
            self.console.print("\n⏱️  Rate Limit Issues:")
            self.console.print("   GitHub API rate limits have been exceeded.")
            self.console.print("   - Wait for the rate limit to reset")
            self.console.print("   - Use authentication to get higher rate limits")

        if error_summary["has_network_errors"]:
            self.console.print("\n🌐 Network Issues:")
            self.console.print("   Network connectivity problems detected.")
            self.console.print("   - Check your internet connection")
            self.console.print("   - Verify GitHub.com is accessible")

        self.console.print("\n💡 Alternative:")
        self.console.print("   Secuority can still analyze your project locally without GitHub integration.")
        self.console.print("   GitHub features provide additional security insights but are not required.")
        self.console.print("=" * 60 + "\n")


def with_github_error_handling(
    continue_on_error: bool = True,
    show_warnings: bool = True,
    fallback_value: Any = None,
    operation_name: str = "GitHub operation",
):
    """Decorator for GitHub API operations with error handling.

    Args:
        continue_on_error: Whether to continue execution after errors
        show_warnings: Whether to show warning messages
        fallback_value: Value to return if operation fails
        operation_name: Name of operation for error messages
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T | Any]:
        def wrapper(*args, **kwargs) -> T | Any:
            handler = GitHubErrorHandler(continue_on_error, show_warnings)
            return handler.handle_api_call(
                func, *args, fallback_value=fallback_value, operation_name=operation_name, **kwargs,
            )

        return wrapper

    return decorator


# Convenience functions for common GitHub operations
def safe_github_call(
    func: Callable[..., T],
    *args,
    fallback_value: T | None = None,
    operation_name: str = "GitHub API call",
    show_warnings: bool = True,
    **kwargs,
) -> T | None:
    """Safely execute a GitHub API call with error handling.

    Args:
        func: Function to execute
        *args: Arguments to pass to function
        fallback_value: Value to return if operation fails
        operation_name: Name of operation for error messages
        show_warnings: Whether to show warning messages
        **kwargs: Keyword arguments to pass to function

    Returns:
        Function result or fallback value if error occurred
    """
    handler = GitHubErrorHandler(continue_on_error=True, show_warnings=show_warnings)
    return handler.handle_api_call(func, *args, fallback_value=fallback_value, operation_name=operation_name, **kwargs)
