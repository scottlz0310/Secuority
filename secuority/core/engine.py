"""Core engine that coordinates all Secuority components."""

from pathlib import Path

from ..models.interfaces import (
    ApplyResult,
    ConfigurationApplierInterface,
    GitHubClientInterface,
    ProjectAnalyzerInterface,
    ProjectState,
    TemplateManagerInterface,
)


class CoreEngine:
    """
    Core engine that coordinates project analysis, template management,
    configuration application, and GitHub integration.
    """

    def __init__(
        self,
        analyzer: ProjectAnalyzerInterface | None = None,
        template_manager: TemplateManagerInterface | None = None,
        applier: ConfigurationApplierInterface | None = None,
        github_client: GitHubClientInterface | None = None,
    ):
        """Initialize the core engine with component implementations."""
        self._analyzer = analyzer
        self._template_manager = template_manager
        self._applier = applier
        self._github_client = github_client

    @property
    def analyzer(self) -> ProjectAnalyzerInterface:
        """Get the project analyzer instance."""
        if self._analyzer is None:
            raise RuntimeError("Project analyzer not initialized")
        return self._analyzer

    @property
    def template_manager(self) -> TemplateManagerInterface:
        """Get the template manager instance."""
        if self._template_manager is None:
            raise RuntimeError("Template manager not initialized")
        return self._template_manager

    @property
    def applier(self) -> ConfigurationApplierInterface:
        """Get the configuration applier instance."""
        if self._applier is None:
            raise RuntimeError("Configuration applier not initialized")
        return self._applier

    @property
    def github_client(self) -> GitHubClientInterface | None:
        """Get the GitHub client instance (optional)."""
        return self._github_client

    def analyze_project(self, project_path: Path) -> ProjectState:
        """Analyze the project and return its current state."""
        return self.analyzer.analyze_project(project_path)

    def generate_recommendations(self, project_state: ProjectState) -> list:
        """Generate configuration recommendations based on project state."""
        # This will be implemented in later tasks
        return []

    def apply_configurations(self, project_path: Path, dry_run: bool = False) -> ApplyResult:
        """Apply recommended configurations to the project."""
        # This will be implemented in later tasks
        project_state = self.analyze_project(project_path)
        recommendations = self.generate_recommendations(project_state)
        return self.applier.apply_changes(recommendations, dry_run)

    def check_github_integration(self, repo: str) -> dict:
        """Check GitHub repository settings if client is available.

        Args:
            repo: Repository in format "owner/repo"
        """
        if self.github_client is None:
            return {
                "available": False,
                "message": "GitHub integration not configured",
            }

        try:
            # Parse owner/repo format
            if "/" not in repo:
                return {"available": False, "error": "Repository must be in 'owner/repo' format"}
            owner, repo_name = repo.split("/", 1)

            return {
                "available": True,
                "push_protection": self.github_client.check_push_protection(owner, repo_name),
                "dependabot": self.github_client.get_dependabot_config(owner, repo_name),
                "workflows": self.github_client.list_workflows(owner, repo_name),
                "security_settings": self.github_client.check_security_settings(owner, repo_name),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}

    def initialize_templates(self) -> None:
        """Initialize template system."""
        self.template_manager.initialize_templates()

    def update_templates(self) -> bool:
        """Update templates from remote source."""
        return self.template_manager.update_templates()
