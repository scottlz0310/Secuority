"""CI/CD workflow integration for Secuority."""

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

    def generate_security_workflow(self, project_path: Path, python_versions: list[str] | None = None) -> ConfigChange:
        """Generate GitHub Actions security workflow.

        Args:
            project_path: Path to the project directory
            python_versions: List of Python versions to test (default: ["3.12", "3.13", "3.14"])

        Returns:
            ConfigChange for security workflow creation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        if python_versions is None:
            python_versions = ["3.12", "3.13", "3.14"]

        workflows_dir = project_path / ".github" / "workflows"
        security_workflow_path = workflows_dir / "security-check.yml"

        # Generate security workflow configuration
        workflow_config = {
            "name": "Security Checks",
            "on": {
                "push": {"branches": ["main", "develop"]},
                "pull_request": {"branches": ["main", "develop"]},
                "schedule": [
                    {
                        "cron": "0 2 * * *",  # Run security checks daily at 2 AM UTC
                    },
                ],
            },
            "jobs": {
                "security": {
                    "runs-on": "ubuntu-latest",
                    "strategy": {"matrix": {"python-version": python_versions}},
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Set up Python ${{ matrix.python-version }}",
                            "uses": "actions/setup-python@v4",
                            "with": {"python-version": "${{ matrix.python-version }}"},
                        },
                        {
                            "name": "Install dependencies",
                            "run": ("python -m pip install --upgrade pip\npip install bandit[toml] safety gitleaks"),
                        },
                        {
                            "name": "Run Bandit security linter",
                            "run": ("bandit -r . -f json -o bandit-report.json || true\nbandit -r . -f txt"),
                        },
                        {
                            "name": "Run Safety dependency vulnerability scanner",
                            "run": ("safety check --json --output safety-report.json || true\nsafety check"),
                        },
                        {
                            "name": "Run Gitleaks secret scanner",
                            "uses": "gitleaks/gitleaks-action@v2",
                            "env": {
                                "GITHUB_PERSONAL_ACCESS_TOKEN": "${{ secrets.GITHUB_PERSONAL_ACCESS_TOKEN }}",
                                "GITLEAKS_LICENSE": "${{ secrets.GITLEAKS_LICENSE }}",
                            },
                        },
                        {
                            "name": "Upload security reports",
                            "uses": "actions/upload-artifact@v3",
                            "if": "always()",
                            "with": {
                                "name": "security-reports-${{ matrix.python-version }}",
                                "path": "bandit-report.json\nsafety-report.json",
                            },
                        },
                        {
                            "name": "Comment PR with security results",
                            "if": "github.event_name == 'pull_request'",
                            "uses": "actions/github-script@v6",
                            "with": {"script": self._get_pr_comment_script()},
                        },
                    ],
                },
                "dependency-review": {
                    "runs-on": "ubuntu-latest",
                    "if": "github.event_name == 'pull_request'",
                    "steps": [
                        {
                            "name": "Dependency Review",
                            "uses": "actions/dependency-review-action@v3",
                            "with": {"fail-on-severity": "moderate"},
                        },
                    ],
                },
            },
        }

        # Generate YAML content
        new_content = self._generate_yaml_content(workflow_config)

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
            python_versions: List of Python versions to test (default: ["3.12", "3.13", "3.14"])

        Returns:
            ConfigChange for quality workflow creation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        if python_versions is None:
            python_versions = ["3.12", "3.13", "3.14"]

        workflows_dir = project_path / ".github" / "workflows"
        quality_workflow_path = workflows_dir / "quality-check.yml"

        # Generate quality workflow configuration
        workflow_config = {
            "name": "Code Quality",
            "on": {"push": {"branches": ["main", "develop"]}, "pull_request": {"branches": ["main", "develop"]}},
            "jobs": {
                "quality": {
                    "runs-on": "ubuntu-latest",
                    "strategy": {"matrix": {"python-version": python_versions}},
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Set up Python ${{ matrix.python-version }}",
                            "uses": "actions/setup-python@v4",
                            "with": {"python-version": "${{ matrix.python-version }}"},
                        },
                        {
                            "name": "Install dependencies",
                            "run": (
                                "python -m pip install --upgrade pip\n"
                                "pip install ruff mypy pytest pytest-cov\n"
                                "if [ -f requirements.txt ]; then pip install -r requirements.txt; fi\n"
                                "if [ -f pyproject.toml ]; then pip install -e .[dev]; fi"
                            ),
                        },
                        {
                            "name": "Lint with Ruff",
                            "run": (
                                "# Stop the build if there are Python syntax errors or undefined names\n"
                                "ruff check . --output-format=github --select=E9,F63,F7,F82 --show-source\n"
                                "# Default set of ruff rules with GitHub Actions annotations\n"
                                "ruff check . --output-format=github"
                            ),
                        },
                        {"name": "Format check with Ruff", "run": "ruff format --check ."},
                        {"name": "Type check with MyPy", "run": "mypy . --show-error-codes --show-error-context"},
                        {
                            "name": "Test with pytest",
                            "run": "pytest --cov=. --cov-report=xml --cov-report=term-missing",
                        },
                        {
                            "name": "Upload coverage reports to Codecov",
                            "uses": "codecov/codecov-action@v3",
                            "with": {
                                "file": "./coverage.xml",
                                "flags": "unittests",
                                "name": "codecov-umbrella",
                                "fail_ci_if_error": False,
                            },
                        },
                    ],
                },
                "pre-commit": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Set up Python",
                            "uses": "actions/setup-python@v4",
                            "with": {"python-version": "3.13"},
                        },
                        {
                            "name": "Install pre-commit",
                            "run": ("python -m pip install --upgrade pip\npip install pre-commit"),
                        },
                        {"name": "Run pre-commit hooks", "run": "pre-commit run --all-files"},
                    ],
                },
                "docs": {
                    "runs-on": "ubuntu-latest",
                    "if": "github.event_name == 'push' && github.ref == 'refs/heads/main'",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "name": "Set up Python",
                            "uses": "actions/setup-python@v4",
                            "with": {"python-version": "3.13"},
                        },
                        {
                            "name": "Install documentation dependencies",
                            "run": ("python -m pip install --upgrade pip\npip install sphinx sphinx-rtd-theme"),
                        },
                        {
                            "name": "Build documentation",
                            "run": ('if [ -d "docs" ]; then\n  cd docs\n  make html\nfi'),
                        },
                        {
                            "name": "Deploy to GitHub Pages",
                            "if": "success()",
                            "uses": "peaceiris/actions-gh-pages@v3",
                            "with": {
                                "GITHUB_PERSONAL_ACCESS_TOKEN": "${{ secrets.GITHUB_PERSONAL_ACCESS_TOKEN }}",
                                "publish_dir": "./docs/_build/html",
                            },
                        },
                    ],
                },
            },
        }

        # Generate YAML content
        new_content = self._generate_yaml_content(workflow_config)

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

    def generate_workflows(
        self,
        project_path: Path,
        workflows: list[str] | None = None,
        python_versions: list[str] | None = None,
    ) -> list[ConfigChange]:
        """Generate multiple CI/CD workflows.

        Args:
            project_path: Path to the project directory
            workflows: List of workflows to generate (default: ['security', 'quality'])
            python_versions: List of Python versions to test

        Returns:
            List of ConfigChange objects for workflow generation

        Raises:
            ConfigurationError: If workflow generation fails
        """
        if workflows is None:
            workflows = ["security", "quality"]

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

        return changes

    def _get_pr_comment_script(self) -> str:
        """Get JavaScript code for PR comment generation.

        Returns:
            JavaScript code as string
        """
        script = """
const fs = require('fs');
let comment = '## Security Scan Results\\n\\n';

try {
  const banditReport = JSON.parse(fs.readFileSync('bandit-report.json', 'utf8'));
  comment += `### Bandit Security Linter\\n`;
  comment += `- **High severity issues**: ${banditReport.metrics._totals.SEVERITY.HIGH || 0}\\n`;
  comment += `- **Medium severity issues**: ${banditReport.metrics._totals.SEVERITY.MEDIUM || 0}\\n`;
  comment += `- **Low severity issues**: ${banditReport.metrics._totals.SEVERITY.LOW || 0}\\n\\n`;
} catch (e) {
  comment += '### Bandit Security Linter\\nReport not available\\n\\n';
}

try {
  const safetyReport = JSON.parse(fs.readFileSync('safety-report.json', 'utf8'));
  comment += `### Safety Dependency Scanner\\n`;
  comment += `- **Vulnerabilities found**: ${safetyReport.vulnerabilities?.length || 0}\\n\\n`;
} catch (e) {
  comment += '### Safety Dependency Scanner\\nReport not available\\n\\n';
}

github.rest.issues.createComment({
  issue_number: context.issue.number,
  owner: context.repo.owner,
  repo: context.repo.repo,
  body: comment
});
        """
        return script.strip()

    def _generate_yaml_content(self, config: dict[str, Any]) -> str:
        """Generate YAML content from configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            YAML content as string with header comment

        Raises:
            ConfigurationError: If YAML generation fails
        """
        try:
            # Add header comment
            header = (
                "# GitHub Actions workflow for security/quality checks\n"
                "# Generated by Secuority - Python security and quality automation tool\n\n"
            )

            yaml_content = yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2)

            return header + str(yaml_content)
        except Exception as e:
            raise ConfigurationError(f"Failed to generate YAML content: {e}") from e

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
