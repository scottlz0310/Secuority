"""GitHub integration module with comprehensive error handling."""

import logging
from typing import Any

from rich.console import Console

from ..utils.github_error_handler import GitHubErrorHandler, safe_github_call
from .github_client import GitHubClient

logger = logging.getLogger(__name__)


class GitHubIntegration:
    """Manages GitHub integration with comprehensive error handling."""

    def __init__(self, show_warnings: bool = True, continue_on_error: bool = True):
        """Initialize GitHub integration.

        Args:
            show_warnings: Whether to display warning messages for API errors
            continue_on_error: Whether to continue execution after API errors
        """
        self.client = GitHubClient()
        self.error_handler = GitHubErrorHandler(continue_on_error, show_warnings)
        self.show_warnings = show_warnings
        self.continue_on_error = continue_on_error
        self.console = Console()

    def analyze_repository_comprehensive(self, owner: str, repo: str) -> dict[str, Any]:
        """Perform comprehensive repository analysis with error handling.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Dictionary containing analysis results and error information
        """
        analysis_result = {
            "owner": owner,
            "repo": repo,
            "api_status": self._get_api_status(),
            "security_analysis": {},
            "workflow_analysis": {},
            "dependabot_analysis": {},
            "errors": [],
            "warnings": [],
            "analysis_complete": False,
        }

        # If not authenticated, provide helpful information
        api_status = analysis_result["api_status"]
        if isinstance(api_status, dict) and not api_status.get("authenticated"):
            warnings_list = analysis_result.get("warnings")
            if not isinstance(warnings_list, list):
                warnings_list = []
                analysis_result["warnings"] = warnings_list
            warnings_list.append(
                "GitHub API authentication not available. "
                "Set GITHUB_PERSONAL_ACCESS_TOKEN environment variable for full analysis.",
            )
            if not self.continue_on_error:
                return analysis_result

        # Perform security analysis
        security_result = self._analyze_security_settings(owner, repo)
        analysis_result["security_analysis"] = security_result

        # Perform workflow analysis
        workflow_result = self._analyze_workflows(owner, repo)
        analysis_result["workflow_analysis"] = workflow_result

        # Perform dependency management analysis (Renovate/Dependabot)
        dependency_result = self._analyze_dependency_management(owner, repo)
        analysis_result["dependency_analysis"] = dependency_result

        # Collect all errors from error handler
        error_summary = self.error_handler.get_error_summary()
        analysis_result["errors"] = error_summary["errors"]
        analysis_result["total_errors"] = error_summary["total_errors"]

        # Mark analysis as complete if we got some results
        analysis_result["analysis_complete"] = bool(security_result) or bool(workflow_result) or bool(dependency_result)

        return analysis_result

    def _get_api_status(self) -> dict[str, Any]:
        """Get GitHub API status with error handling."""
        result = safe_github_call(
            self.client.get_api_status,
            fallback_value={
                "has_token": False,
                "authenticated": False,
                "api_accessible": False,
                "errors": ["Could not check API status"],
            },
            operation_name="API status check",
            show_warnings=self.show_warnings,
        )
        return result or {
            "has_token": False,
            "authenticated": False,
            "api_accessible": False,
            "errors": ["Could not check API status"],
        }

    def _analyze_security_settings(self, owner: str, repo: str) -> dict[str, Any]:
        """Analyze repository security settings with error handling."""
        security_settings: dict[str, Any] = (
            safe_github_call(
                self.client.check_security_settings,
                owner,
                repo,
                fallback_value={},
                operation_name="security settings check",
                show_warnings=self.show_warnings,
            )
            or {}
        )

        push_protection = (
            safe_github_call(
                self.client.check_push_protection,
                owner,
                repo,
                fallback_value=False,
                operation_name="push protection check",
                show_warnings=self.show_warnings,
            )
            or False
        )

        return {
            "security_settings": security_settings,
            "push_protection": push_protection,
            "recommendations": self._get_security_recommendations(security_settings, push_protection),
        }

    def _analyze_workflows(self, owner: str, repo: str) -> dict[str, Any]:
        """Analyze repository workflows with error handling."""
        workflows: list[dict[str, Any]] = (
            safe_github_call(
                self.client.list_workflows,
                owner,
                repo,
                fallback_value=[],
                operation_name="workflow listing",
                show_warnings=self.show_warnings,
            )
            or []
        )

        if not workflows:
            return {
                "workflows": [],
                "has_security_workflows": False,
                "has_quality_workflows": False,
                "recommendations": [
                    "Consider adding GitHub Actions workflows for automated testing",
                    "Add security scanning workflows (CodeQL, Dependabot)",
                    "Set up quality checks (linting, type checking)",
                ],
            }

        # Analyze workflow types
        security_workflows = []
        quality_workflows = []

        for workflow in workflows:
            workflow_name = workflow.get("name", "").lower()
            workflow_path = workflow.get("path", "").lower()

            if self._is_security_workflow(workflow_name, workflow_path):
                security_workflows.append(workflow)

            if self._is_quality_workflow(workflow_name, workflow_path):
                quality_workflows.append(workflow)

        return {
            "workflows": workflows,
            "security_workflows": security_workflows,
            "quality_workflows": quality_workflows,
            "has_security_workflows": bool(security_workflows),
            "has_quality_workflows": bool(quality_workflows),
            "recommendations": self._get_workflow_recommendations(bool(security_workflows), bool(quality_workflows)),
        }

    def _analyze_dependency_management(self, owner: str, repo: str) -> dict[str, Any]:
        """Analyze dependency management (Renovate/Dependabot) with error handling."""
        # Check for Renovate first (preferred)
        renovate_config_result = safe_github_call(
            self.client.get_renovate_config,
            owner,
            repo,
            fallback_value={
                "enabled": False,
                "config_file": None,
                "config_file_exists": False,
                "config_content": "",
            },
            operation_name="Renovate configuration check",
            show_warnings=self.show_warnings,
        )

        renovate_config: dict[str, Any] = (
            renovate_config_result
            if renovate_config_result is not None
            else {
                "enabled": False,
                "config_file": None,
                "config_file_exists": False,
                "config_content": "",
            }
        )

        # Check for Dependabot as fallback
        dependabot_config_result = safe_github_call(
            self.client.get_dependabot_config,
            owner,
            repo,
            fallback_value={
                "enabled": False,
                "config_file_exists": False,
                "config_content": "",
            },
            operation_name="Dependabot configuration check",
            show_warnings=self.show_warnings,
        )

        dependabot_config: dict[str, Any] = (
            dependabot_config_result
            if dependabot_config_result is not None
            else {
                "enabled": False,
                "config_file_exists": False,
                "config_content": "",
            }
        )

        recommendations = []
        has_renovate = renovate_config.get("enabled", False)
        has_dependabot = dependabot_config.get("enabled", False)

        if not has_renovate and not has_dependabot:
            recommendations.append(
                "Enable Renovate for automated dependency updates (modern alternative to Dependabot)",
            )
            recommendations.append("Add renovate.json configuration file")
        elif has_dependabot and not has_renovate:
            recommendations.append("Consider migrating to Renovate for better dependency management")

        return {
            "renovate_config": renovate_config,
            "dependabot_config": dependabot_config,
            "using_renovate": has_renovate,
            "using_dependabot": has_dependabot,
            "should_migrate": has_dependabot and not has_renovate,
            "recommendations": recommendations,
        }

    def _is_security_workflow(self, name: str, path: str) -> bool:
        """Check if a workflow is security-related."""
        security_keywords = [
            "security",
            "bandit",
            "safety",
            "gitleaks",
            "semgrep",
            "snyk",
            "codeql",
            "dependabot",
            "vulnerability",
            "audit",
        ]
        return any(keyword in name or keyword in path for keyword in security_keywords)

    def _is_quality_workflow(self, name: str, path: str) -> bool:
        """Check if a workflow is quality-related."""
        quality_keywords = [
            "test",
            "lint",
            "quality",
            "ruff",
            "mypy",
            "black",
            "flake8",
            "pylint",
            "pytest",
            "coverage",
            "ci",
            "check",
        ]
        return any(keyword in name or keyword in path for keyword in quality_keywords)

    def _get_security_recommendations(self, security_settings: dict[str, Any], push_protection: bool) -> list[str]:
        """Get security recommendations based on current settings."""
        recommendations = []

        if not security_settings:
            recommendations.append("Could not analyze security settings - check GitHub token permissions")
            return recommendations

        if not security_settings.get("secret_scanning", False):
            recommendations.append("Enable secret scanning in repository security settings")

        if not push_protection:
            recommendations.append("Enable push protection for secret scanning")

        if not security_settings.get("dependency_graph", False):
            recommendations.append("Enable dependency graph for vulnerability alerts")

        if not security_settings.get("private_vulnerability_reporting", False):
            recommendations.append("Enable private vulnerability reporting")

        return recommendations

    def _get_workflow_recommendations(self, has_security: bool, has_quality: bool) -> list[str]:
        """Get workflow recommendations based on current setup."""
        recommendations = []

        if not has_security:
            recommendations.append("Add security workflow with Bandit, Safety, and CodeQL")

        if not has_quality:
            recommendations.append("Add quality workflow with linting and testing")

        return recommendations

    def print_analysis_summary(self, analysis_result: dict[str, Any]) -> None:
        """Print a summary of the GitHub analysis results."""
        self.console.print(f"\n📊 GitHub Repository Analysis: {analysis_result['owner']}/{analysis_result['repo']}")
        self.console.print("=" * 60)

        # API Status
        api_status = analysis_result["api_status"]
        if api_status["authenticated"]:
            self.console.print("✅ GitHub API: Authenticated and accessible")
        elif api_status["has_token"]:
            self.console.print("⚠️  GitHub API: Token provided but authentication failed")
        else:
            self.console.print("📝 GitHub API: No token provided (limited analysis)")

        # Security Analysis
        security = analysis_result["security_analysis"]
        if security.get("security_settings"):
            settings = security["security_settings"]
            self.console.print("\n🔒 Security Settings:")
            self.console.print(f"   Secret Scanning: {'✅' if settings.get('secret_scanning') else '❌'}")
            self.console.print(f"   Push Protection: {'✅' if security.get('push_protection') else '❌'}")
            self.console.print(f"   Dependency Graph: {'✅' if settings.get('dependency_graph') else '❌'}")

        # Workflow Analysis
        workflows = analysis_result["workflow_analysis"]
        if workflows.get("workflows"):
            self.console.print(f"\n⚙️  GitHub Actions: {len(workflows['workflows'])} workflows found")
            self.console.print(f"   Security Workflows: {'✅' if workflows['has_security_workflows'] else '❌'}")
            self.console.print(f"   Quality Workflows: {'✅' if workflows['has_quality_workflows'] else '❌'}")

        # Recommendations
        all_recommendations = []
        for section in [security, workflows, analysis_result.get("dependabot_analysis", {})]:
            all_recommendations.extend(section.get("recommendations", []))

        if all_recommendations:
            self.console.print("\n💡 Recommendations:")
            for i, rec in enumerate(all_recommendations[:5], 1):  # Show top 5
                self.console.print(f"   {i}. {rec}")

        # Errors
        if analysis_result["errors"]:
            self.console.print(f"\n⚠️  Encountered {len(analysis_result['errors'])} API errors")
            if self.show_warnings:
                self.error_handler.print_setup_instructions()

        self.console.print("=" * 60)

    def get_setup_instructions(self) -> str:
        """Get setup instructions for GitHub integration."""
        return """
GitHub Integration Setup:

1. Create a Personal Access Token:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: repo, security_events, read:org

2. Set Environment Variable:
   export GITHUB_PERSONAL_ACCESS_TOKEN=your_token_here

3. Verify Setup:
   secuority check --verbose

For more information, visit: https://docs.github.com/en/authentication
"""
