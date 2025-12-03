"""GitHub API client for repository analysis and security settings."""

import json
import logging
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from ..models.exceptions import GitHubAPIError
from ..models.interfaces import (
    DependabotConfig,
    GitHubClientInterface,
    GitHubSecuritySettings,
    GitHubWorkflowSummary,
)

logger = logging.getLogger(__name__)


class GitHubClient(GitHubClientInterface):
    """Client for interacting with GitHub API."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        """Initialize GitHub client with optional token.

        Args:
            token: GitHub personal access token. If None, will try to get from GITHUB_PERSONAL_ACCESS_TOKEN env var.
        """
        self.token = token or os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        self.headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "Secuority-CLI/1.0"}
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _make_request(self, endpoint: str) -> dict[str, Any]:
        """Make authenticated request to GitHub API.

        Args:
            endpoint: API endpoint path

        Returns:
            JSON response as dictionary

        Raises:
            GitHubAPIError: If API request fails
        """
        url = urljoin(self.BASE_URL, endpoint)
        # S310: Safe - URL is constructed from BASE_URL constant (https://api.github.com)
        request = Request(url, headers=self.headers)  # noqa: S310

        try:
            # S310: Safe - Opening GitHub API endpoint with validated HTTPS URL
            with urlopen(request) as response:  # noqa: S310
                result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                return result
        except HTTPError as e:
            if e.code == 401:
                raise GitHubAPIError("GitHub API authentication failed. Check GITHUB_PERSONAL_ACCESS_TOKEN.") from None
            if e.code == 403:
                raise GitHubAPIError("GitHub API rate limit exceeded or insufficient permissions.") from None
            if e.code == 404:
                raise GitHubAPIError("Repository not found or not accessible.") from None
            raise GitHubAPIError(f"GitHub API request failed: {e.code} {e.reason}") from None
        except URLError as e:
            raise GitHubAPIError(f"Network error accessing GitHub API: {e.reason}") from None
        except json.JSONDecodeError as e:
            raise GitHubAPIError(f"Invalid JSON response from GitHub API: {e}") from None

    def check_push_protection(self, owner: str, repo: str) -> bool:
        """Check if push protection is enabled for the repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            True if push protection is enabled, False otherwise

        Raises:
            GitHubAPIError: If API request fails
        """
        endpoint = f"/repos/{owner}/{repo}"
        try:
            repo_data = self._make_request(endpoint)
            # Check if the repository has security features enabled
            # Push protection is part of secret scanning
            security_endpoint = f"/repos/{owner}/{repo}/secret-scanning/push-protection"
            try:
                protection_data = self._make_request(security_endpoint)
                enabled: bool = protection_data.get("enabled", False)
                return enabled
            except GitHubAPIError:
                # If we can't access push protection endpoint, check general security settings
                security_analysis = repo_data.get("security_and_analysis", {})
                if isinstance(security_analysis, dict):
                    secret_scanning = security_analysis.get("secret_scanning", {})
                else:
                    secret_scanning = {}
                status = secret_scanning.get("status") if isinstance(secret_scanning, dict) else None
                return status == "enabled"
        except GitHubAPIError:
            raise

    def get_renovate_config(self, owner: str, repo: str) -> dict[str, Any]:
        """Get Renovate configuration for the repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Dictionary containing Renovate configuration

        Raises:
            GitHubAPIError: If API request fails
        """
        # Try to get Renovate configuration file (renovate.json)
        config_endpoint = f"/repos/{owner}/{repo}/contents/renovate.json"
        try:
            config_data = self._make_request(config_endpoint)
            return {
                "enabled": True,
                "config_file": "renovate.json",
                "config_file_exists": True,
                "config_content": config_data.get("content", ""),
            }
        except GitHubAPIError:
            pass

        # Try renovate.json5 as alternative
        config5_endpoint = f"/repos/{owner}/{repo}/contents/renovate.json5"
        try:
            config_data = self._make_request(config5_endpoint)
            return {
                "enabled": True,
                "config_file": "renovate.json5",
                "config_file_exists": True,
                "config_content": config_data.get("content", ""),
            }
        except GitHubAPIError:
            pass

        # Try .github/renovate.json
        github_config_endpoint = f"/repos/{owner}/{repo}/contents/.github/renovate.json"
        try:
            config_data = self._make_request(github_config_endpoint)
            return {
                "enabled": True,
                "config_file": ".github/renovate.json",
                "config_file_exists": True,
                "config_content": config_data.get("content", ""),
            }
        except GitHubAPIError:
            return {
                "enabled": False,
                "config_file": None,
                "config_file_exists": False,
                "config_content": "",
            }

    def get_dependabot_config(self, owner: str, repo: str) -> DependabotConfig:
        """Get Dependabot configuration for the repository.

        DEPRECATED: Use get_renovate_config instead for modern dependency management.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Dictionary containing Dependabot configuration

        Raises:
            GitHubAPIError: If API request fails
        """
        # First check if Dependabot is enabled
        endpoint = f"/repos/{owner}/{repo}/vulnerability-alerts"
        try:
            self._make_request(endpoint)
            dependabot_enabled = True
        except GitHubAPIError:
            dependabot_enabled = False

        # Try to get Dependabot configuration file
        config_endpoint = f"/repos/{owner}/{repo}/contents/.github/dependabot.yml"
        try:
            config_data = self._make_request(config_endpoint)
            return DependabotConfig(
                enabled=dependabot_enabled,
                config_file_exists=True,
                config_content=config_data.get("content", ""),
            )
        except GitHubAPIError:
            return DependabotConfig(
                enabled=dependabot_enabled,
                config_file_exists=False,
                config_content="",
            )

    def list_workflows(self, owner: str, repo: str) -> list[GitHubWorkflowSummary]:
        """List GitHub Actions workflows for the repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of workflow dictionaries

        Raises:
            GitHubAPIError: If API request fails
        """
        endpoint = f"/repos/{owner}/{repo}/actions/workflows"
        try:
            response = self._make_request(endpoint)
            workflows: list[GitHubWorkflowSummary] = []
            for workflow in response.get("workflows", []):
                if not isinstance(workflow, dict):
                    continue
                workflows.append(
                    GitHubWorkflowSummary(
                        id=int(workflow.get("id", 0)),
                        name=str(workflow.get("name", "unknown")),
                        path=str(workflow.get("path", "")),
                        state=str(workflow.get("state", "")),
                        html_url=str(workflow.get("html_url", "")),
                    )
                )
            return workflows
        except GitHubAPIError:
            raise

    def check_security_settings(self, owner: str, repo: str) -> GitHubSecuritySettings:
        """Check various security settings for the repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Dictionary containing security settings status

        Raises:
            GitHubAPIError: If API request fails
        """
        endpoint = f"/repos/{owner}/{repo}"
        try:
            repo_data = self._make_request(endpoint)
            security_analysis = repo_data.get("security_and_analysis", {})

            # Check if SECURITY.md exists in the repository
            has_security_policy = False
            try:
                security_md_endpoint = f"/repos/{owner}/{repo}/contents/SECURITY.md"
                self._make_request(security_md_endpoint)
                has_security_policy = True
            except GitHubAPIError:
                # SECURITY.md doesn't exist
                pass

            # Check repository visibility
            is_private = repo_data.get("private", False)

            return GitHubSecuritySettings(
                secret_scanning=security_analysis.get("secret_scanning", {}).get("status") == "enabled",
                secret_scanning_push_protection=security_analysis.get("secret_scanning_push_protection", {}).get(
                    "status",
                )
                == "enabled",
                dependency_graph=repo_data.get("has_vulnerability_alerts", False),
                private_vulnerability_reporting=security_analysis.get("private_vulnerability_reporting", {}).get(
                    "status",
                )
                == "enabled",
                security_policy=has_security_policy,
                is_private=is_private,
            )
        except GitHubAPIError:
            raise

    def is_authenticated(self) -> bool:
        """Check if the client is properly authenticated.

        Returns:
            True if authenticated, False otherwise
        """
        if not self.token:
            return False

        try:
            self._make_request("/user")
            return True
        except GitHubAPIError:
            return False

    def safe_api_call(self, operation: str, endpoint: str, fallback_value: Any = None, log_errors: bool = True) -> Any:
        """Make a safe API call with error handling and logging.

        Args:
            operation: Description of the operation being performed
            endpoint: API endpoint to call
            fallback_value: Value to return if the call fails
            log_errors: Whether to log errors

        Returns:
            API response or fallback value if error occurred
        """
        try:
            return self._make_request(endpoint)
        except GitHubAPIError as e:
            if log_errors:
                logger.warning(f"GitHub API {operation} failed: {e}")
            return fallback_value
        except Exception as e:
            if log_errors:
                logger.warning(f"Unexpected error during GitHub API {operation}: {e}")
            return fallback_value

    def get_api_status(self) -> dict[str, Any]:
        """Get the status of GitHub API connectivity and authentication.

        Returns:
            Dictionary containing API status information
        """
        status: dict[str, Any] = {
            "has_token": bool(self.token),
            "authenticated": False,
            "api_accessible": False,
            "rate_limit_info": None,
            "errors": [],
        }

        if not self.token:
            status["errors"].append("No GitHub token provided")
            return status

        # Test authentication
        try:
            user_data = self._make_request("/user")
            status["authenticated"] = True
            status["api_accessible"] = True
            status["user"] = user_data.get("login", "unknown")
        except GitHubAPIError as e:
            status["errors"].append(f"Authentication failed: {e}")

            # Still try to check if API is accessible without auth
            try:
                # Use a public endpoint that doesn't require auth
                self._make_request("/zen")
                status["api_accessible"] = True
            except GitHubAPIError:
                status["errors"].append("GitHub API not accessible")

        # Get rate limit info if authenticated
        if status["authenticated"]:
            try:
                rate_limit = self._make_request("/rate_limit")
                status["rate_limit_info"] = rate_limit.get("rate", {})
            except GitHubAPIError:
                status["errors"].append("Could not retrieve rate limit information")

        return status
