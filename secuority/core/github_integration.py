"""GitHub integration module with comprehensive error handling."""

import logging
from typing import Any, Dict, List

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
    
    def analyze_repository_comprehensive(
        self, 
        owner: str, 
        repo: str
    ) -> Dict[str, Any]:
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
            "analysis_complete": False
        }
        
        # If not authenticated, provide helpful information
        if not analysis_result["api_status"]["authenticated"]:
            if "warnings" not in analysis_result:
                analysis_result["warnings"] = []
            analysis_result["warnings"].append(
                "GitHub API authentication not available. "
                "Set GITHUB_TOKEN environment variable for full analysis."
            )
            if not self.continue_on_error:
                return analysis_result
        
        # Perform security analysis
        security_result = self._analyze_security_settings(owner, repo)
        analysis_result["security_analysis"] = security_result
        
        # Perform workflow analysis
        workflow_result = self._analyze_workflows(owner, repo)
        analysis_result["workflow_analysis"] = workflow_result
        
        # Perform Dependabot analysis
        dependabot_result = self._analyze_dependabot(owner, repo)
        analysis_result["dependabot_analysis"] = dependabot_result
        
        # Collect all errors from error handler
        error_summary = self.error_handler.get_error_summary()
        analysis_result["errors"] = error_summary["errors"]
        analysis_result["total_errors"] = error_summary["total_errors"]
        
        # Mark analysis as complete if we got some results
        analysis_result["analysis_complete"] = (
            bool(security_result) or 
            bool(workflow_result) or 
            bool(dependabot_result)
        )
        
        return analysis_result
    
    def _get_api_status(self) -> Dict[str, Any]:
        """Get GitHub API status with error handling."""
        result = safe_github_call(
            self.client.get_api_status,
            fallback_value={
                "has_token": False,
                "authenticated": False,
                "api_accessible": False,
                "errors": ["Could not check API status"]
            },
            operation_name="API status check",
            show_warnings=self.show_warnings
        )
        return result or {
            "has_token": False,
            "authenticated": False,
            "api_accessible": False,
            "errors": ["Could not check API status"]
        }
    
    def _analyze_security_settings(self, owner: str, repo: str) -> Dict[str, Any]:
        """Analyze repository security settings with error handling."""
        security_settings = safe_github_call(
            self.client.check_security_settings,
            owner, repo,
            fallback_value={},
            operation_name="security settings check",
            show_warnings=self.show_warnings
        ) or {}
        
        push_protection = safe_github_call(
            self.client.check_push_protection,
            owner, repo,
            fallback_value=False,
            operation_name="push protection check",
            show_warnings=self.show_warnings
        ) or False
        
        return {
            "security_settings": security_settings,
            "push_protection": push_protection,
            "recommendations": self._get_security_recommendations(
                security_settings, push_protection
            )
        }
    
    def _analyze_workflows(self, owner: str, repo: str) -> Dict[str, Any]:
        """Analyze repository workflows with error handling."""
        workflows = safe_github_call(
            self.client.list_workflows,
            owner, repo,
            fallback_value=[],
            operation_name="workflow listing",
            show_warnings=self.show_warnings
        ) or []
        
        if not workflows:
            return {
                "workflows": [],
                "has_security_workflows": False,
                "has_quality_workflows": False,
                "recommendations": [
                    "Consider adding GitHub Actions workflows for automated testing",
                    "Add security scanning workflows (CodeQL, Dependabot)",
                    "Set up quality checks (linting, type checking)"
                ]
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
            "recommendations": self._get_workflow_recommendations(
                bool(security_workflows), bool(quality_workflows)
            )
        }
    
    def _analyze_dependabot(self, owner: str, repo: str) -> Dict[str, Any]:
        """Analyze Dependabot configuration with error handling."""
        dependabot_config = safe_github_call(
            self.client.get_dependabot_config,
            owner, repo,
            fallback_value={
                "enabled": False,
                "config_file_exists": False,
                "config_content": ""
            },
            operation_name="Dependabot configuration check",
            show_warnings=self.show_warnings
        )
        
        recommendations = []
        if not dependabot_config.get("enabled", False):
            recommendations.append("Enable Dependabot for automated dependency updates")
        
        if not dependabot_config.get("config_file_exists", False):
            recommendations.append("Add .github/dependabot.yml configuration file")
        
        return {
            "dependabot_config": dependabot_config,
            "recommendations": recommendations
        }
    
    def _is_security_workflow(self, name: str, path: str) -> bool:
        """Check if a workflow is security-related."""
        security_keywords = [
            "security", "bandit", "safety", "gitleaks", "semgrep",
            "snyk", "codeql", "dependabot", "vulnerability", "audit"
        ]
        return any(keyword in name or keyword in path for keyword in security_keywords)
    
    def _is_quality_workflow(self, name: str, path: str) -> bool:
        """Check if a workflow is quality-related."""
        quality_keywords = [
            "test", "lint", "quality", "ruff", "mypy", "black",
            "flake8", "pylint", "pytest", "coverage", "ci", "check"
        ]
        return any(keyword in name or keyword in path for keyword in quality_keywords)
    
    def _get_security_recommendations(
        self, 
        security_settings: Dict[str, Any], 
        push_protection: bool
    ) -> List[str]:
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
    
    def _get_workflow_recommendations(
        self, 
        has_security: bool, 
        has_quality: bool
    ) -> List[str]:
        """Get workflow recommendations based on current setup."""
        recommendations = []
        
        if not has_security:
            recommendations.append("Add security workflow with Bandit, Safety, and CodeQL")
        
        if not has_quality:
            recommendations.append("Add quality workflow with linting and testing")
        
        return recommendations
    
    def print_analysis_summary(self, analysis_result: Dict[str, Any]) -> None:
        """Print a summary of the GitHub analysis results."""
        print(f"\n📊 GitHub Repository Analysis: {analysis_result['owner']}/{analysis_result['repo']}")
        print("=" * 60)
        
        # API Status
        api_status = analysis_result["api_status"]
        if api_status["authenticated"]:
            print("✅ GitHub API: Authenticated and accessible")
        elif api_status["has_token"]:
            print("⚠️  GitHub API: Token provided but authentication failed")
        else:
            print("ℹ️  GitHub API: No token provided (limited analysis)")
        
        # Security Analysis
        security = analysis_result["security_analysis"]
        if security.get("security_settings"):
            settings = security["security_settings"]
            print(f"\n🔒 Security Settings:")
            print(f"   Secret Scanning: {'✅' if settings.get('secret_scanning') else '❌'}")
            print(f"   Push Protection: {'✅' if security.get('push_protection') else '❌'}")
            print(f"   Dependency Graph: {'✅' if settings.get('dependency_graph') else '❌'}")
        
        # Workflow Analysis
        workflows = analysis_result["workflow_analysis"]
        if workflows.get("workflows"):
            print(f"\n⚙️  GitHub Actions: {len(workflows['workflows'])} workflows found")
            print(f"   Security Workflows: {'✅' if workflows['has_security_workflows'] else '❌'}")
            print(f"   Quality Workflows: {'✅' if workflows['has_quality_workflows'] else '❌'}")
        
        # Recommendations
        all_recommendations = []
        for section in [security, workflows, analysis_result.get("dependabot_analysis", {})]:
            all_recommendations.extend(section.get("recommendations", []))
        
        if all_recommendations:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(all_recommendations[:5], 1):  # Show top 5
                print(f"   {i}. {rec}")
        
        # Errors
        if analysis_result["errors"]:
            print(f"\n⚠️  Encountered {len(analysis_result['errors'])} API errors")
            if self.show_warnings:
                self.error_handler.print_setup_instructions()
        
        print("=" * 60)
    
    def get_setup_instructions(self) -> str:
        """Get setup instructions for GitHub integration."""
        return """
GitHub Integration Setup:

1. Create a Personal Access Token:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: repo, security_events, read:org

2. Set Environment Variable:
   export GITHUB_TOKEN=your_token_here

3. Verify Setup:
   secuority check --verbose

For more information, visit: https://docs.github.com/en/authentication
"""