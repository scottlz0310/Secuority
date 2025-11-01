"""CI/CD workflow integration for Secuority."""

import importlib.resources
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from ..models.config import ConfigChange
from ..models.exceptions import ConfigurationError
from ..models.interfaces import ChangeType


class WorkflowIntegrator:
    """Integrates CI/CD workflows with security checks."""

    def __init__(self) -> None:
        """Initialize workflow integrator."""
        # Note: YAML functionality will be limited if PyYAML is not available
        pass

    def _load_pyproject_config(self, project_path: Path) -> dict[str, Any]:
        """Load pyproject.toml configuration."""
        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return {}

        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                return {}

        try:
            with open(pyproject_path, "rb") as f:
                return tomllib.load(f)
        except Exception:
            return {}

    def _get_python_versions_from_pyproject(self, project_path: Path) -> list[str]:
        """Extract Python versions from pyproject.toml classifiers."""
        data = self._load_pyproject_config(project_path)
        if not data:
            return ["3.12", "3.13", "3.14"]

        classifiers = data.get("project", {}).get("classifiers", [])
        versions = []
        for classifier in classifiers:
            if classifier.startswith("Programming Language :: Python :: 3."):
                version = classifier.split(" :: ")[-1]
                if version.count(".") == 1:
                    versions.append(version)

        return sorted(set(versions)) if versions else ["3.12", "3.13", "3.14"]

    def _get_package_name_from_pyproject(self, project_path: Path) -> str:
        """Extract package name from pyproject.toml."""
        data = self._load_pyproject_config(project_path)
        return data.get("project", {}).get("name", "").replace("-", "_") or "src"

    def generate_security_workflow(self, project_path: Path, python_versions: list[str] | None = None) -> ConfigChange:
        """Generate GitHub Actions security workflow.

        Args:
            project_path: Path to the project directory
            python_versions: List of Python versions to test (default: read from pyproject.toml)

        Returns:
            ConfigChange for security workflow creation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        if python_versions is None:
            python_versions = self._get_python_versions_from_pyproject(project_path)

        workflows_dir = project_path / ".github" / "workflows"
        security_workflow_path = workflows_dir / "security-check.yml"

        # Load template from package resources
        try:
            template_content = (
                importlib.resources.files("secuority.templates.workflows")
                .joinpath("security-check.yml")
                .read_text(encoding="utf-8")
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load security workflow template: {e}") from e

        # Replace placeholders in template
        import json

        versions_json = json.dumps(python_versions)
        new_content = template_content.replace('["3.12", "3.13", "3.14"]', versions_json)

        # Read existing content for comparison
        old_content = ""
        if security_workflow_path.exists():
            try:
                with open(security_workflow_path, encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {security_workflow_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if security_workflow_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=security_workflow_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Generate GitHub Actions security workflow",
            conflicts=[],
        )

    def generate_quality_workflow(self, project_path: Path, python_versions: list[str] | None = None) -> ConfigChange:
        """Generate GitHub Actions code quality workflow.

        Args:
            project_path: Path to the project directory
            python_versions: List of Python versions to test (default: read from pyproject.toml)

        Returns:
            ConfigChange for quality workflow creation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        if python_versions is None:
            python_versions = self._get_python_versions_from_pyproject(project_path)

        workflows_dir = project_path / ".github" / "workflows"
        quality_workflow_path = workflows_dir / "quality-check.yml"

        # Load template from package resources
        try:
            template_content = (
                importlib.resources.files("secuority.templates.workflows")
                .joinpath("quality-check.yml")
                .read_text(encoding="utf-8")
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load quality workflow template: {e}") from e

        # Replace placeholders in template
        import json

        versions_json = json.dumps(python_versions)
        package_name = self._get_package_name_from_pyproject(project_path)

        new_content = template_content.replace('["3.12", "3.13", "3.14"]', versions_json)
        new_content = new_content.replace('"$PACKAGE_NAME"', f'"{package_name}"')

        # Read existing content for comparison
        old_content = ""
        if quality_workflow_path.exists():
            try:
                with open(quality_workflow_path, encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {quality_workflow_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if quality_workflow_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=quality_workflow_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Generate GitHub Actions code quality workflow",
            conflicts=[],
        )

    def generate_cicd_workflow(self, project_path: Path, python_versions: list[str] | None = None) -> ConfigChange:
        """Generate GitHub Actions CI/CD workflow.

        Args:
            project_path: Path to the project directory
            python_versions: List of Python versions to test (default: read from pyproject.toml)

        Returns:
            ConfigChange for CI/CD workflow creation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        if python_versions is None:
            python_versions = self._get_python_versions_from_pyproject(project_path)

        workflows_dir = project_path / ".github" / "workflows"
        cicd_workflow_path = workflows_dir / "ci-cd.yml"

        # Load template from package resources
        try:
            template_content = (
                importlib.resources.files("secuority.templates.workflows")
                .joinpath("ci-cd.yml")
                .read_text(encoding="utf-8")
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load CI/CD workflow template: {e}") from e

        # Replace placeholders in template
        import json

        versions_json = json.dumps(python_versions)
        package_name = self._get_package_name_from_pyproject(project_path)

        new_content = template_content.replace('["3.12", "3.13", "3.14"]', versions_json)
        new_content = new_content.replace("$PACKAGE_NAME", package_name)

        # Read existing content for comparison
        old_content = ""
        if cicd_workflow_path.exists():
            try:
                with open(cicd_workflow_path, encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {cicd_workflow_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if cicd_workflow_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=cicd_workflow_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Generate GitHub Actions CI/CD workflow",
            conflicts=[],
        )

    def generate_dependency_workflow(
        self,
        project_path: Path,
        python_versions: list[str] | None = None,
    ) -> ConfigChange:
        """Generate GitHub Actions dependency update workflow.

        Args:
            project_path: Path to the project directory
            python_versions: List of Python versions to test (default: ["3.12", "3.13", "3.14"])

        Returns:
            ConfigChange for dependency workflow creation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        workflows_dir = project_path / ".github" / "workflows"
        dependency_workflow_path = workflows_dir / "dependency-update.yml"

        # Load template from package resources
        try:
            template_content = (
                importlib.resources.files("secuority.templates.workflows")
                .joinpath("dependency-update.yml")
                .read_text(encoding="utf-8")
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load dependency workflow template: {e}") from e

        new_content = template_content

        # Read existing content for comparison
        old_content = ""
        if dependency_workflow_path.exists():
            try:
                with open(dependency_workflow_path, encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {dependency_workflow_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if dependency_workflow_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=dependency_workflow_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Generate GitHub Actions dependency update workflow",
            conflicts=[],
        )

    def generate_workflows(
        self,
        project_path: Path,
        workflows: list[str] | None = None,
        python_versions: list[str] | None = None,
    ) -> list[ConfigChange]:
        """Generate multiple CI/CD workflows.

        Args:
            project_path: Path to the project directory
            workflows: List of workflows to generate (default: ['security', 'quality', 'cicd', 'dependency'])
            python_versions: List of Python versions to test

        Returns:
            List of ConfigChange objects for workflow generation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        if workflows is None:
            workflows = ["security", "quality", "cicd", "dependency"]

        changes = []

        # Ensure .github/workflows directory exists
        workflows_dir = project_path / ".github" / "workflows"
        if not workflows_dir.exists():
            # Create a change to create the directory structure
            # This will be handled by the file operations when applying changes
            pass

        # Generate requested workflows
        for workflow_type in workflows:
            if workflow_type == "security":
                change = self.generate_security_workflow(project_path, python_versions)
                changes.append(change)
            elif workflow_type == "quality":
                change = self.generate_quality_workflow(project_path, python_versions)
                changes.append(change)
            elif workflow_type == "cicd":
                change = self.generate_cicd_workflow(project_path, python_versions)
                changes.append(change)
            elif workflow_type == "dependency":
                change = self.generate_dependency_workflow(project_path, python_versions)
                changes.append(change)

        return changes

    def check_existing_workflows(self, project_path: Path) -> dict[str, bool]:
        """Check which workflows already exist in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary mapping workflow types to existence status
        """
        workflows_dir = project_path / ".github" / "workflows"

        status = {"security": False, "quality": False, "has_workflows_dir": workflows_dir.exists()}

        if not workflows_dir.exists():
            return status

        # Check for security workflow
        security_files = ["security-check.yml", "security-check.yaml", "security.yml", "security.yaml"]

        for filename in security_files:
            if (workflows_dir / filename).exists():
                status["security"] = True
                break

        # Check for quality workflow
        quality_files = [
            "quality-check.yml",
            "quality-check.yaml",
            "quality.yml",
            "quality.yaml",
            "ci.yml",
            "ci.yaml",
            "test.yml",
            "test.yaml",
        ]

        for filename in quality_files:
            if (workflows_dir / filename).exists():
                status["quality"] = True
                break

        return status

    def get_workflow_recommendations(self, project_path: Path) -> list[str]:
        """Get workflow setup recommendations.

        Args:
            project_path: Path to the project directory

        Returns:
            List of recommendation strings
        """
        recommendations = []
        status = self.check_existing_workflows(project_path)

        if not status["has_workflows_dir"]:
            recommendations.append("Create .github/workflows directory for GitHub Actions workflows")

        if not status["security"]:
            recommendations.append("Add security workflow with Bandit, Safety, and gitleaks checks")

        if not status["quality"]:
            recommendations.append("Add quality workflow with linting, type checking, and testing")

        if not status["security"] and not status["quality"]:
            recommendations.append("Consider enabling GitHub's built-in security features like Dependabot and CodeQL")

        return recommendations
