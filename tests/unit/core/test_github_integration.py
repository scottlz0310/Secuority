"""Unit tests for GitHubIntegration."""

from unittest.mock import MagicMock

import pytest

from secuority.core.github_integration import GitHubIntegration
from secuority.models.exceptions import GitHubAPIError


class TestGitHubIntegration:
    """Test GitHubIntegration functionality."""

    @pytest.fixture
    def integration(self) -> GitHubIntegration:
        """Create GitHubIntegration instance."""
        return GitHubIntegration(show_warnings=False, continue_on_error=True)

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock GitHub client."""
        return MagicMock()

    def test_initialization(self, integration: GitHubIntegration) -> None:
        """Test GitHubIntegration initialization."""
        assert integration.show_warnings is False
        assert integration.continue_on_error is True
        assert integration.client is not None
        assert integration.error_handler is not None

    def test_get_api_status_success(self, integration: GitHubIntegration) -> None:
        """Test getting API status successfully."""
        integration.client.get_api_status = MagicMock(
            return_value={
                "has_token": True,
                "authenticated": True,
                "api_accessible": True,
            },
        )

        result = integration._get_api_status()

        assert result["has_token"] is True
        assert result["authenticated"] is True
        assert result["api_accessible"] is True

    def test_get_api_status_failure(self, integration: GitHubIntegration) -> None:
        """Test getting API status with failure."""
        integration.client.get_api_status = MagicMock(side_effect=GitHubAPIError("API error"))

        result = integration._get_api_status()

        assert result["has_token"] is False
        assert result["authenticated"] is False
        assert result["api_accessible"] is False

    def test_analyze_security_settings_success(self, integration: GitHubIntegration) -> None:
        """Test analyzing security settings successfully."""
        integration.client.check_security_settings = MagicMock(
            return_value={
                "secret_scanning": True,
                "dependency_graph": True,
            },
        )
        integration.client.check_push_protection = MagicMock(return_value=True)

        result = integration._analyze_security_settings("owner", "repo")

        assert result["security_settings"]["secret_scanning"] is True
        assert result["push_protection"] is True
        assert isinstance(result["recommendations"], list)

    def test_analyze_security_settings_with_error(self, integration: GitHubIntegration) -> None:
        """Test analyzing security settings with error."""
        integration.client.check_security_settings = MagicMock(side_effect=GitHubAPIError("API error"))
        integration.client.check_push_protection = MagicMock(side_effect=GitHubAPIError("API error"))

        result = integration._analyze_security_settings("owner", "repo")

        assert result["security_settings"] == {}
        assert result["push_protection"] is False

    def test_analyze_workflows_success(self, integration: GitHubIntegration) -> None:
        """Test analyzing workflows successfully."""
        workflows = [
            {"name": "Security Check", "path": ".github/workflows/security.yml"},
            {"name": "Quality Check", "path": ".github/workflows/quality.yml"},
            {"name": "Build", "path": ".github/workflows/build.yml"},
        ]
        integration.client.list_workflows = MagicMock(return_value=workflows)

        result = integration._analyze_workflows("owner", "repo")

        assert len(result["workflows"]) == 3
        assert result["has_security_workflows"] is True
        assert result["has_quality_workflows"] is True

    def test_analyze_workflows_no_workflows(self, integration: GitHubIntegration) -> None:
        """Test analyzing workflows when none exist."""
        integration.client.list_workflows = MagicMock(return_value=[])

        result = integration._analyze_workflows("owner", "repo")

        assert len(result["workflows"]) == 0
        assert result["has_security_workflows"] is False
        assert result["has_quality_workflows"] is False
        assert len(result["recommendations"]) > 0

    def test_analyze_workflows_with_error(self, integration: GitHubIntegration) -> None:
        """Test analyzing workflows with error."""
        integration.client.list_workflows = MagicMock(side_effect=GitHubAPIError("API error"))

        result = integration._analyze_workflows("owner", "repo")

        assert len(result["workflows"]) == 0

    def test_analyze_dependency_management_with_renovate(self, integration: GitHubIntegration) -> None:
        """Test analyzing dependency management with Renovate."""
        integration.client.get_renovate_config = MagicMock(
            return_value={
                "enabled": True,
                "config_file_exists": True,
                "config_content": '{"extends": ["config:base"]}',
            },
        )
        integration.client.get_dependabot_config = MagicMock(
            return_value={
                "enabled": False,
                "config_file_exists": False,
                "config_content": "",
            },
        )

        result = integration._analyze_dependency_management("owner", "repo")

        assert result["renovate_config"]["enabled"] is True
        assert result["using_renovate"] is True
        assert result["using_dependabot"] is False

    def test_analyze_dependency_management_with_dependabot(self, integration: GitHubIntegration) -> None:
        """Test analyzing dependency management with Dependabot (should recommend migration)."""
        integration.client.get_renovate_config = MagicMock(
            return_value={
                "enabled": False,
                "config_file_exists": False,
                "config_content": "",
            },
        )
        integration.client.get_dependabot_config = MagicMock(
            return_value={
                "enabled": True,
                "config_file_exists": True,
                "config_content": "version: 2",
            },
        )

        result = integration._analyze_dependency_management("owner", "repo")

        assert result["dependabot_config"]["enabled"] is True
        assert result["using_renovate"] is False
        assert result["using_dependabot"] is True
        assert result["should_migrate"] is True
        assert len(result["recommendations"]) > 0

    def test_is_security_workflow(self, integration: GitHubIntegration) -> None:
        """Test identifying security workflows."""
        assert integration._is_security_workflow("Security Check", ".github/workflows/security.yml") is True
        assert integration._is_security_workflow("Bandit Scan", ".github/workflows/bandit.yml") is True
        assert integration._is_security_workflow("CodeQL", ".github/workflows/codeql.yml") is True
        assert integration._is_security_workflow("Build", ".github/workflows/build.yml") is False

    def test_is_quality_workflow(self, integration: GitHubIntegration) -> None:
        """Test identifying quality workflows."""
        assert integration._is_quality_workflow("Quality Check", ".github/workflows/quality.yml") is True
        assert integration._is_quality_workflow("Test", ".github/workflows/test.yml") is True
        assert integration._is_quality_workflow("Lint", ".github/workflows/lint.yml") is True
        assert integration._is_quality_workflow("Deploy", ".github/workflows/deploy.yml") is False

    def test_get_security_recommendations_no_settings(self, integration: GitHubIntegration) -> None:
        """Test getting security recommendations with no settings."""
        recommendations = integration._get_security_recommendations({}, False)

        assert len(recommendations) > 0
        assert any("check GitHub token" in rec for rec in recommendations)

    def test_get_security_recommendations_missing_features(self, integration: GitHubIntegration) -> None:
        """Test getting security recommendations for missing features."""
        settings = {
            "secret_scanning": False,
            "dependency_graph": False,
            "private_vulnerability_reporting": False,
        }

        recommendations = integration._get_security_recommendations(settings, False)

        assert len(recommendations) > 0
        assert any("secret scanning" in rec for rec in recommendations)
        assert any("push protection" in rec for rec in recommendations)

    def test_get_workflow_recommendations(self, integration: GitHubIntegration) -> None:
        """Test getting workflow recommendations."""
        # No security or quality workflows
        recommendations = integration._get_workflow_recommendations(False, False)
        assert len(recommendations) == 2

        # Has security but no quality
        recommendations = integration._get_workflow_recommendations(True, False)
        assert len(recommendations) == 1

        # Has both
        recommendations = integration._get_workflow_recommendations(True, True)
        assert len(recommendations) == 0

    def test_analyze_repository_comprehensive_success(self, integration: GitHubIntegration) -> None:
        """Test comprehensive repository analysis."""
        integration.client.get_api_status = MagicMock(
            return_value={
                "has_token": True,
                "authenticated": True,
                "api_accessible": True,
            },
        )
        integration.client.check_security_settings = MagicMock(
            return_value={"secret_scanning": True},
        )
        integration.client.check_push_protection = MagicMock(return_value=True)
        integration.client.list_workflows = MagicMock(return_value=[])
        integration.client.get_dependabot_config = MagicMock(
            return_value={"enabled": True, "config_file_exists": True},
        )

        result = integration.analyze_repository_comprehensive("owner", "repo")

        assert result["owner"] == "owner"
        assert result["repo"] == "repo"
        assert result["analysis_complete"] is True
        assert "security_analysis" in result
        assert "workflow_analysis" in result
        assert "dependabot_analysis" in result

    def test_analyze_repository_comprehensive_not_authenticated(self, integration: GitHubIntegration) -> None:
        """Test comprehensive analysis without authentication."""
        integration.client.get_api_status = MagicMock(
            return_value={
                "has_token": False,
                "authenticated": False,
                "api_accessible": False,
            },
        )
        integration.client.check_security_settings = MagicMock(return_value={})
        integration.client.check_push_protection = MagicMock(return_value=False)
        integration.client.list_workflows = MagicMock(return_value=[])
        integration.client.get_dependabot_config = MagicMock(
            return_value={"enabled": False, "config_file_exists": False},
        )

        result = integration.analyze_repository_comprehensive("owner", "repo")

        assert len(result["warnings"]) > 0
        assert any("authentication not available" in w.lower() for w in result["warnings"])

    def test_print_analysis_summary(self, integration: GitHubIntegration) -> None:
        """Test printing analysis summary."""
        analysis_result = {
            "owner": "test-owner",
            "repo": "test-repo",
            "api_status": {
                "has_token": True,
                "authenticated": True,
                "api_accessible": True,
            },
            "security_analysis": {
                "security_settings": {
                    "secret_scanning": True,
                    "dependency_graph": True,
                },
                "push_protection": True,
                "recommendations": ["Enable private vulnerability reporting"],
            },
            "workflow_analysis": {
                "workflows": [{"name": "Test"}],
                "has_security_workflows": True,
                "has_quality_workflows": True,
                "recommendations": [],
            },
            "dependabot_analysis": {
                "recommendations": [],
            },
            "errors": [],
        }

        # Should not raise any exceptions
        integration.print_analysis_summary(analysis_result)

    def test_print_analysis_summary_with_errors(self, integration: GitHubIntegration) -> None:
        """Test printing analysis summary with errors."""
        integration.error_handler.errors_encountered = [
            {"operation": "test", "error": "API error", "type": "github_api_error"},
        ]

        analysis_result = {
            "owner": "test-owner",
            "repo": "test-repo",
            "api_status": {
                "has_token": False,
                "authenticated": False,
                "api_accessible": False,
            },
            "security_analysis": {
                "security_settings": {},
                "push_protection": False,
                "recommendations": [],
            },
            "workflow_analysis": {
                "workflows": [],
                "has_security_workflows": False,
                "has_quality_workflows": False,
                "recommendations": [],
            },
            "dependabot_analysis": {
                "recommendations": [],
            },
            "errors": [{"operation": "test", "error": "API error"}],
        }

        # Should not raise any exceptions
        integration.print_analysis_summary(analysis_result)

    def test_get_setup_instructions(self, integration: GitHubIntegration) -> None:
        """Test getting setup instructions."""
        instructions = integration.get_setup_instructions()

        assert "Personal Access Token" in instructions
        assert "GITHUB_PERSONAL_ACCESS_TOKEN" in instructions
        assert "github.com/settings/tokens" in instructions

    def test_analyze_repository_with_api_errors(self, integration: GitHubIntegration) -> None:
        """Test repository analysis with API errors."""
        integration.client.get_api_status = MagicMock(side_effect=GitHubAPIError("API error"))
        integration.client.check_security_settings = MagicMock(side_effect=GitHubAPIError("API error"))
        integration.client.check_push_protection = MagicMock(side_effect=GitHubAPIError("API error"))
        integration.client.list_workflows = MagicMock(side_effect=GitHubAPIError("API error"))
        integration.client.get_dependabot_config = MagicMock(side_effect=GitHubAPIError("API error"))

        result = integration.analyze_repository_comprehensive("owner", "repo")

        # Should still return a result structure
        assert result["owner"] == "owner"
        assert result["repo"] == "repo"
        assert "security_analysis" in result
        assert "workflow_analysis" in result

    def test_integration_with_warnings_enabled(self) -> None:
        """Test integration with warnings enabled."""
        integration = GitHubIntegration(show_warnings=True, continue_on_error=True)

        assert integration.show_warnings is True
        assert integration.error_handler.show_warnings is True

    def test_integration_continue_on_error_disabled(self) -> None:
        """Test integration with continue_on_error disabled."""
        integration = GitHubIntegration(show_warnings=False, continue_on_error=False)

        assert integration.continue_on_error is False
        assert integration.error_handler.continue_on_error is False
