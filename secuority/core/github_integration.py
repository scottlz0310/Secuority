"""GitHub integration module with comprehensive error handling."""

import logging

from rich.console import Console

from ..models.interfaces import DependabotConfig, GitHubSecuritySettings, GitHubWorkflowSummary
from ..types import (
    ComprehensiveAnalysisResult,
    DependencyManagementReport,
    GitHubApiStatus,
    RenovateConfig,
    SecurityAnalysisReport,
    WorkflowAnalysisReport,
)
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

    def analyze_repository_comprehensive(self, owner: str, repo: str) -> ComprehensiveAnalysisResult:
        """Perform comprehensive repository analysis with error handling.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Dictionary containing analysis results and error information
        """
        analysis_result: ComprehensiveAnalysisResult = {
            "owner": owner,
            "repo": repo,
            "api_status": self._get_api_status(),
            "security_analysis": self._empty_security_report(),
            "workflow_analysis": self._empty_workflow_report(),
            "dependency_analysis": self._empty_dependency_report(),
            "errors": [],
            "warnings": [],
            "total_errors": 0,
            "analysis_complete": False,
        }

        # If not authenticated, provide helpful information
        api_status = analysis_result["api_status"]
        if not api_status["authenticated"]:
            analysis_result["warnings"].append(
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
        errors_value = error_summary.get("errors")
        analysis_result["errors"] = errors_value if isinstance(errors_value, list) else []
        total_errors = error_summary.get("total_errors", 0)
        analysis_result["total_errors"] = int(total_errors)

        # Mark analysis as complete if we got some results
        analysis_result["analysis_complete"] = bool(security_result) or bool(workflow_result) or bool(dependency_result)

        return analysis_result

    def _get_api_status(self) -> GitHubApiStatus:
        """Get GitHub API status with error handling."""
        fallback_status: GitHubApiStatus = {
            "has_token": False,
            "authenticated": False,
            "api_accessible": False,
            "user": "unknown",
            "rate_limit_info": None,
            "errors": ["Could not check API status"],
        }

        result = safe_github_call(
            self.client.get_api_status,
            fallback_value=fallback_status,
            operation_name="API status check",
            show_warnings=self.show_warnings,
        )
        if result is None:
            return fallback_status
        return result

    def _analyze_security_settings(self, owner: str, repo: str) -> SecurityAnalysisReport:
        """Analyze repository security settings with error handling."""
        raw_settings = safe_github_call(
            self.client.check_security_settings,
            owner,
            repo,
            fallback_value=self._default_security_settings(),
            operation_name="security settings check",
            show_warnings=self.show_warnings,
        )

        security_settings = raw_settings if isinstance(raw_settings, dict) else self._default_security_settings()

        push_protection = bool(
            safe_github_call(
                self.client.check_push_protection,
                owner,
                repo,
                fallback_value=False,
                operation_name="push protection check",
                show_warnings=self.show_warnings,
            )
            or False,
        )

        return SecurityAnalysisReport(
            security_settings=security_settings,
            push_protection=push_protection,
            recommendations=self._get_security_recommendations(security_settings, push_protection),
        )

    def _analyze_workflows(self, owner: str, repo: str) -> WorkflowAnalysisReport:
        """Analyze repository workflows with error handling."""
        raw_workflows = safe_github_call(
            self.client.list_workflows,
            owner,
            repo,
            fallback_value=[],
            operation_name="workflow listing",
            show_warnings=self.show_warnings,
        )

        workflows_result = raw_workflows if isinstance(raw_workflows, list) else []
        workflows: list[GitHubWorkflowSummary] = list(workflows_result)

        if not workflows:
            return WorkflowAnalysisReport(
                workflows=[],
                security_workflows=[],
                quality_workflows=[],
                has_security_workflows=False,
                has_quality_workflows=False,
                recommendations=[
                    "Consider adding GitHub Actions workflows for automated testing",
                    "Add security scanning workflows (CodeQL, Dependabot)",
                    "Set up quality checks (linting, type checking)",
                ],
            )

        # Analyze workflow types
        security_workflows: list[GitHubWorkflowSummary] = []
        quality_workflows: list[GitHubWorkflowSummary] = []

        for workflow in workflows:
            workflow_name = str(workflow.get("name", "")).lower()
            workflow_path = str(workflow.get("path", "")).lower()

            if self._is_security_workflow(workflow_name, workflow_path):
                security_workflows.append(workflow)

            if self._is_quality_workflow(workflow_name, workflow_path):
                quality_workflows.append(workflow)

        return WorkflowAnalysisReport(
            workflows=workflows,
            security_workflows=security_workflows,
            quality_workflows=quality_workflows,
            has_security_workflows=bool(security_workflows),
            has_quality_workflows=bool(quality_workflows),
            recommendations=self._get_workflow_recommendations(bool(security_workflows), bool(quality_workflows)),
        )

    def _analyze_dependency_management(self, owner: str, repo: str) -> DependencyManagementReport:
        """Analyze dependency management (Renovate/Dependabot) with error handling."""
        renovate_config_result = safe_github_call(
            self.client.get_renovate_config,
            owner,
            repo,
            fallback_value=self._default_renovate_config(),
            operation_name="Renovate configuration check",
            show_warnings=self.show_warnings,
        )
        renovate_config = (
            renovate_config_result if isinstance(renovate_config_result, dict) else self._default_renovate_config()
        )

        dependabot_config_result = safe_github_call(
            self.client.get_dependabot_config,
            owner,
            repo,
            fallback_value=self._default_dependabot_config(),
            operation_name="Dependabot configuration check",
            show_warnings=self.show_warnings,
        )
        dependabot_config = (
            dependabot_config_result
            if isinstance(dependabot_config_result, dict)
            else self._default_dependabot_config()
        )

        recommendations = self._build_dependency_recommendations(renovate_config, dependabot_config)

        return DependencyManagementReport(
            renovate=renovate_config,
            dependabot=dependabot_config,
            recommendations=recommendations,
        )

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

    def _get_security_recommendations(
        self,
        security_settings: GitHubSecuritySettings,
        push_protection: bool,
    ) -> list[str]:
        """Get security recommendations based on current settings."""
        recommendations: list[str] = []

        if not security_settings["secret_scanning"]:
            recommendations.append("Enable secret scanning in repository security settings")

        if not push_protection:
            recommendations.append("Enable push protection for secret scanning")

        if not security_settings["dependency_graph"]:
            recommendations.append("Enable dependency graph for vulnerability alerts")

        if not security_settings["private_vulnerability_reporting"]:
            recommendations.append("Enable private vulnerability reporting")

        return recommendations

    def _get_workflow_recommendations(self, has_security: bool, has_quality: bool) -> list[str]:
        """Get workflow recommendations based on current setup."""
        recommendations: list[str] = []

        if not has_security:
            recommendations.append("Add security workflow with Bandit, Safety, and CodeQL")

        if not has_quality:
            recommendations.append("Add quality workflow with linting and testing")

        return recommendations

    def _default_security_settings(self) -> GitHubSecuritySettings:
        return GitHubSecuritySettings(
            secret_scanning=False,
            secret_scanning_push_protection=False,
            dependency_graph=False,
            private_vulnerability_reporting=False,
            security_policy=False,
            is_private=False,
        )

    def _empty_security_report(self) -> SecurityAnalysisReport:
        return SecurityAnalysisReport(
            security_settings=self._default_security_settings(),
            push_protection=False,
            recommendations=[],
        )

    def _empty_workflow_report(self) -> WorkflowAnalysisReport:
        return WorkflowAnalysisReport(
            workflows=[],
            security_workflows=[],
            quality_workflows=[],
            has_security_workflows=False,
            has_quality_workflows=False,
            recommendations=[],
        )

    def _empty_dependency_report(self) -> DependencyManagementReport:
        return DependencyManagementReport(
            renovate=self._default_renovate_config(),
            dependabot=self._default_dependabot_config(),
            recommendations=[],
        )

    def _default_renovate_config(self) -> RenovateConfig:
        return RenovateConfig(
            enabled=False,
            config_file=None,
            config_file_exists=False,
            config_content="",
        )

    def _default_dependabot_config(self) -> DependabotConfig:
        return DependabotConfig(
            enabled=False,
            config_file_exists=False,
            config_content="",
        )

    def _build_dependency_recommendations(
        self,
        renovate_config: RenovateConfig,
        dependabot_config: DependabotConfig,
    ) -> list[str]:
        recommendations: list[str] = []
        renovate_enabled = bool(renovate_config.get("enabled", False))
        dependabot_enabled = bool(dependabot_config.get("enabled", False))

        if not renovate_enabled and not dependabot_enabled:
            recommendations.append(
                "Enable Renovate for automated dependency updates (modern alternative to Dependabot)",
            )
            recommendations.append("Add renovate.json configuration file")
        elif dependabot_enabled and not renovate_enabled:
            recommendations.append("Consider migrating to Renovate for better dependency management")

        return recommendations

    def print_analysis_summary(self, analysis_result: ComprehensiveAnalysisResult) -> None:
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
        settings = security["security_settings"]
        self.console.print("\n🔒 Security Settings:")
        self.console.print(f"   Secret Scanning: {'✅' if settings.get('secret_scanning') else '❌'}")
        self.console.print(f"   Push Protection: {'✅' if security['push_protection'] else '❌'}")
        self.console.print(f"   Dependency Graph: {'✅' if settings.get('dependency_graph') else '❌'}")

        # Workflow Analysis
        workflows = analysis_result["workflow_analysis"]
        self.console.print(f"\n⚙️  GitHub Actions: {len(workflows['workflows'])} workflows found")
        self.console.print(f"   Security Workflows: {'✅' if workflows['has_security_workflows'] else '❌'}")
        self.console.print(f"   Quality Workflows: {'✅' if workflows['has_quality_workflows'] else '❌'}")

        dependency = analysis_result["dependency_analysis"]
        renovate_status = "✅" if dependency["renovate"].get("enabled", False) else "❌"
        dependabot_status = "✅" if dependency["dependabot"]["enabled"] else "❌"
        self.console.print(f"\n🔁 Dependency Automation: Renovate {renovate_status}, Dependabot {dependabot_status}")

        # Recommendations
        all_recommendations: list[str] = []
        for rec_source in (
            security["recommendations"],
            workflows["recommendations"],
            dependency["recommendations"],
        ):
            all_recommendations.extend(rec_source)

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
