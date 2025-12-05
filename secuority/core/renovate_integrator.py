"""Renovate configuration integration for Secuority."""

import json
from pathlib import Path
from typing import Any, TypedDict, cast

from ..models.config import ConfigChange
from ..models.exceptions import ConfigurationError
from ..models.interfaces import ChangeType


class PackageRule(TypedDict, total=False):
    """Subset of Renovate package rule configuration."""

    description: str
    matchManagers: list[str]
    matchDepTypes: list[str]
    matchUpdateTypes: list[str]
    schedule: list[str]
    automerge: bool
    groupName: str


class VulnerabilityAlertsConfig(TypedDict, total=False):
    labels: list[str]
    assignees: list[str]
    reviewers: list[str]


class LockFileMaintenanceConfig(TypedDict, total=False):
    enabled: bool
    schedule: list[str]


RenovateConfig = TypedDict(
    "RenovateConfig",
    {
        "$schema": str,
        "extends": list[str],
        "schedule": list[str],
        "timezone": str,
        "labels": list[str],
        "assignees": list[str],
        "reviewers": list[str],
        "packageRules": list[PackageRule],
        "repos": list[dict[str, Any]],
        "vulnerabilityAlerts": VulnerabilityAlertsConfig,
        "lockFileMaintenance": LockFileMaintenanceConfig,
        "ignoreDeps": list[str],
        "ignorePaths": list[str],
        "prConcurrentLimit": int,
    },
    total=False,
)


class RenovateIntegrator:
    """Integrates Renovate configuration for automated dependency updates."""

    def __init__(self) -> None:
        """Initialize Renovate integrator."""

    def integrate_renovate_config(
        self,
        project_path: Path,
        timezone: str = "UTC",
        assignees: str = "@maintainers",
        reviewers: str = "@maintainers",
        automerge_actions: bool = True,
    ) -> ConfigChange:
        """Integrate Renovate configuration into renovate.json.

        Args:
            project_path: Path to the project directory
            timezone: Timezone for schedule (default: UTC)
            assignees: Assignees for PRs (default: @maintainers)
            reviewers: Reviewers for PRs (default: @maintainers)
            automerge_actions: Whether to auto-merge GitHub Actions updates
                (default: True)

        Returns:
            ConfigChange for Renovate integration

        Raises:
            ConfigurationError: If integration fails
        """
        renovate_path = project_path / "renovate.json"

        # Load existing configuration if present
        existing_config = self._load_renovate_config(renovate_path)

        # Generate new configuration
        new_config = self._generate_renovate_config(
            timezone=timezone,
            assignees=assignees,
            reviewers=reviewers,
            automerge_actions=automerge_actions,
            existing_config=existing_config,
        )

        # Generate new content
        new_content = json.dumps(new_config, indent=2) + "\n"

        # Read existing content for comparison
        old_content = ""
        if renovate_path.exists():
            try:
                with renovate_path.open(encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                msg = f"Failed to read {renovate_path}: {e}"
                raise ConfigurationError(msg) from e

        # Determine change type
        change_type = ChangeType.UPDATE if renovate_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=renovate_path,
            change_type=change_type,
            old_content=(old_content if change_type == ChangeType.UPDATE else None),
            new_content=new_content,
            description="Integrate Renovate for automated dependency updates",
            conflicts=[],
        )

    def _load_renovate_config(self, renovate_path: Path) -> RenovateConfig:
        """Load existing Renovate configuration.

        Args:
            renovate_path: Path to renovate.json file

        Returns:
            Dictionary containing existing Renovate configuration
        """
        if not renovate_path.exists():
            return {}

        try:
            with renovate_path.open(encoding="utf-8") as f:
                raw_config: object = json.load(f)
                return self._coerce_config(raw_config)
        except (OSError, json.JSONDecodeError) as e:
            msg = f"Failed to load {renovate_path}: {e}"
            raise ConfigurationError(msg) from e

    def _generate_renovate_config(
        self,
        timezone: str,
        assignees: str,
        reviewers: str,
        automerge_actions: bool,
        existing_config: RenovateConfig | None = None,
    ) -> RenovateConfig:
        """Generate Renovate configuration.

        Args:
            timezone: Timezone for schedule
            assignees: Assignees for PRs
            reviewers: Reviewers for PRs
            automerge_actions: Whether to auto-merge GitHub Actions updates
            existing_config: Existing configuration to merge with

        Returns:
            Dictionary containing Renovate configuration
        """
        # Base configuration
        config: RenovateConfig = {
            "$schema": "https://docs.renovatebot.com/renovate-schema.json",
            "extends": ["config:recommended"],
            "schedule": ["before 6am on monday"],
            "timezone": timezone,
            "labels": ["dependencies"],
            "assignees": [assignees],
            "reviewers": [reviewers],
            "repos": [],
            "packageRules": [
                {
                    "description": "Pre-commit hooks - weekly updates",
                    "matchManagers": ["pre-commit"],
                    "schedule": ["before 6am on monday"],
                    "automerge": False,
                    "groupName": "pre-commit hooks",
                },
                {
                    "description": "Python dependencies - group by type",
                    "matchManagers": ["pep621"],
                    "matchDepTypes": ["dependencies"],
                    "groupName": "Python production dependencies",
                },
                {
                    "description": "Python dev dependencies",
                    "matchManagers": ["pep621"],
                    "matchDepTypes": ["dev-dependencies"],
                    "groupName": "Python dev dependencies",
                },
                {
                    "description": ("GitHub Actions - minor and patch auto-merge"),
                    "matchManagers": ["github-actions"],
                    "matchUpdateTypes": ["minor", "patch"],
                    "automerge": automerge_actions,
                    "groupName": "GitHub Actions",
                },
            ],
            "vulnerabilityAlerts": {
                "labels": ["security"],
                "assignees": [assignees],
                "reviewers": [reviewers],
            },
            "lockFileMaintenance": {
                "enabled": True,
                "schedule": ["before 6am on monday"],
            },
        }

        # Merge with existing configuration if provided
        if existing_config:
            # Preserve custom settings from existing config
            preserve_keys = [
                "extends",
                "ignoreDeps",
                "ignorePaths",
                "prConcurrentLimit",
            ]
            for key in preserve_keys:
                if key in existing_config and key not in config:
                    config[key] = existing_config[key]

            # Merge packageRules if they exist
            existing_rules = self._coerce_package_rules(existing_config.get("packageRules"))
            if existing_rules:
                default_managers = {
                    "pre-commit",
                    "pep621",
                    "github-actions",
                }
                for rule_item in existing_rules:
                    managers_value = rule_item.get("matchManagers")
                    if managers_value is None:
                        config["packageRules"].append(rule_item)
                        continue

                    rule_managers = set(managers_value)
                    if not rule_managers.intersection(default_managers):
                        config["packageRules"].append(rule_item)

        return config

    def _coerce_config(self, raw: object) -> RenovateConfig:
        sanitized = dict(cast(dict[str, Any], raw)) if isinstance(raw, dict) else {}

        if "packageRules" in sanitized:
            sanitized["packageRules"] = self._coerce_package_rules(sanitized.get("packageRules"))
        if "repos" in sanitized:
            sanitized["repos"] = self._sanitize_repos_field(sanitized.get("repos"))

        vulnerability_alerts = sanitized.get("vulnerabilityAlerts")
        if isinstance(vulnerability_alerts, dict):
            sanitized["vulnerabilityAlerts"] = cast(VulnerabilityAlertsConfig, vulnerability_alerts)

        lock_file_maintenance = sanitized.get("lockFileMaintenance")
        if isinstance(lock_file_maintenance, dict):
            sanitized["lockFileMaintenance"] = cast(LockFileMaintenanceConfig, lock_file_maintenance)

        return cast(RenovateConfig, sanitized)

    def _sanitize_repos_field(self, value: object) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        repo_list = cast(list[object], value)
        sanitized: list[dict[str, Any]] = []
        for repo in repo_list:
            if isinstance(repo, dict):
                repo_dict = cast(dict[str, Any], repo)
                sanitized.append(dict(repo_dict))
        return sanitized

    def _coerce_package_rules(self, value: object) -> list[PackageRule]:
        if not isinstance(value, list):
            return []
        item_list = cast(list[object], value)
        rules: list[PackageRule] = []
        for item in item_list:
            if isinstance(item, dict):
                rule_dict = cast(dict[str, Any], item)
                rules.append(cast(PackageRule, rule_dict))
        return rules

    def get_renovate_status(self, project_path: Path) -> dict[str, Any]:
        """Get the status of Renovate configuration in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary containing Renovate status information
        """
        renovate_path = project_path / "renovate.json"
        renovate5_path = project_path / "renovate.json5"

        status: dict[str, Any] = {
            "enabled": False,
            "config_file": None,
            "valid": False,
            "errors": [],
        }

        # Check for renovate.json
        if renovate_path.exists():
            status["enabled"] = True
            status["config_file"] = str(renovate_path)
            try:
                config = self._load_renovate_config(renovate_path)
                status["valid"] = bool(config)
            except ConfigurationError as e:
                status["errors"].append(str(e))
        # Check for renovate.json5 (alternative format)
        elif renovate5_path.exists():
            status["enabled"] = True
            status["config_file"] = str(renovate5_path)
            status["errors"].append("renovate.json5 detected but not validated (JSON5 support not implemented)")

        return status

    def detect_migration_needs(self, project_path: Path) -> dict[str, Any]:
        """Detect if project needs migration from Dependabot to Renovate.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary with migration status and recommendations
        """
        github_dir = project_path / ".github"
        workflows_dir = github_dir / "workflows"

        # Check for Renovate
        has_renovate = (
            (project_path / "renovate.json").exists()
            or (project_path / "renovate.json5").exists()
            or (github_dir / "renovate.json").exists()
        )

        # Check for Dependabot files
        dependabot_files: list[str] = []
        if (github_dir / "dependabot.yml").exists():
            dependabot_files.append(".github/dependabot.yml")
        if (github_dir / "dependabot.yaml").exists():
            dependabot_files.append(".github/dependabot.yaml")

        # Check for Dependabot-related workflows
        deprecated_workflows: list[str] = []
        if workflows_dir.exists():
            workflow_patterns = [
                "dependabot-automerge.yml",
                "dependabot-automerge.yaml",
                "dependabot-auto-merge.yml",
                "dependabot-auto-merge.yaml",
                "auto-merge-dependabot.yml",
                "auto-merge-dependabot.yaml",
            ]
            deprecated_workflows.extend(
                f".github/workflows/{pattern}" for pattern in workflow_patterns if (workflows_dir / pattern).exists()
            )

        needs_migration = bool(dependabot_files or deprecated_workflows)
        recommendations: list[str] = []

        if needs_migration and not has_renovate:
            recommendations.append("Migrate to Renovate for modern dependency management")
            recommendations.append("Add renovate.json configuration")
            if dependabot_files:
                recommendations.append(f"Remove Dependabot config: {', '.join(dependabot_files)}")
            if deprecated_workflows:
                recommendations.append("Remove Dependabot automerge workflows (Renovate handles this natively)")
        elif needs_migration and has_renovate:
            recommendations.append("Cleanup: Remove old Dependabot files")

        return {
            "needs_migration": needs_migration,
            "has_renovate": has_renovate,
            "dependabot_files": dependabot_files,
            "deprecated_workflows": deprecated_workflows,
            "recommendations": recommendations,
        }
