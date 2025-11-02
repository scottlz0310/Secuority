"""Unit tests for RenovateIntegrator."""

import json
from pathlib import Path
from typing import Any

import pytest

from secuority.core.renovate_integrator import RenovateIntegrator
from secuority.models.exceptions import ConfigurationError
from secuority.models.interfaces import ChangeType


class TestRenovateIntegrator:
    """Test RenovateIntegrator functionality."""

    @pytest.fixture
    def integrator(self) -> RenovateIntegrator:
        """Create RenovateIntegrator instance."""
        return RenovateIntegrator()

    @pytest.fixture
    def sample_renovate_config(self) -> dict[str, Any]:
        """Sample Renovate configuration."""
        return {
            "$schema": "https://docs.renovatebot.com/renovate-schema.json",
            "extends": ["config:recommended"],
            "schedule": ["before 6am on monday"],
            "timezone": "UTC",
            "labels": ["dependencies"],
        }

    def test_integrate_renovate_config_new_file(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test integrating Renovate config into new file."""
        change = integrator.integrate_renovate_config(
            tmp_path,
            timezone="Asia/Tokyo",
            assignees="@team",
            reviewers="@reviewers",
        )

        assert change.file_path == tmp_path / "renovate.json"
        assert change.change_type == ChangeType.CREATE
        assert change.old_content is None
        assert "renovate-schema.json" in change.new_content
        assert "Asia/Tokyo" in change.new_content
        assert "@team" in change.new_content
        assert "@reviewers" in change.new_content

        # Verify JSON is valid
        config = json.loads(change.new_content)
        assert config["timezone"] == "Asia/Tokyo"
        assert config["assignees"] == ["@team"]
        assert config["reviewers"] == ["@reviewers"]

    def test_integrate_renovate_config_existing_file(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
        sample_renovate_config: dict[str, Any],
    ) -> None:
        """Test integrating Renovate config into existing file."""
        # Create existing file
        renovate_path = tmp_path / "renovate.json"
        renovate_path.write_text(json.dumps(sample_renovate_config, indent=2))

        change = integrator.integrate_renovate_config(tmp_path)

        assert change.change_type == ChangeType.UPDATE
        assert change.old_content is not None
        assert "config:recommended" in change.new_content

    def test_integrate_renovate_config_with_automerge_disabled(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test Renovate config with automerge disabled."""
        change = integrator.integrate_renovate_config(
            tmp_path,
            automerge_actions=False,
        )

        config = json.loads(change.new_content)
        # Find GitHub Actions package rule
        gh_actions_rule = next(
            (r for r in config["packageRules"] if r.get("matchManagers") == ["github-actions"]),
            None,
        )
        assert gh_actions_rule is not None
        assert gh_actions_rule["automerge"] is False

    def test_integrate_renovate_config_with_automerge_enabled(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test Renovate config with automerge enabled."""
        change = integrator.integrate_renovate_config(
            tmp_path,
            automerge_actions=True,
        )

        config = json.loads(change.new_content)
        # Find GitHub Actions package rule
        gh_actions_rule = next(
            (r for r in config["packageRules"] if r.get("matchManagers") == ["github-actions"]),
            None,
        )
        assert gh_actions_rule is not None
        assert gh_actions_rule["automerge"] is True

    def test_load_renovate_config_nonexistent(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test loading non-existent Renovate config."""
        renovate_path = tmp_path / "renovate.json"
        config = integrator._load_renovate_config(renovate_path)

        assert config == {}

    def test_load_renovate_config_existing(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
        sample_renovate_config: dict[str, Any],
    ) -> None:
        """Test loading existing Renovate config."""
        renovate_path = tmp_path / "renovate.json"
        renovate_path.write_text(json.dumps(sample_renovate_config))

        config = integrator._load_renovate_config(renovate_path)

        assert config == sample_renovate_config

    def test_load_renovate_config_invalid_json(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test loading Renovate config with invalid JSON."""
        renovate_path = tmp_path / "renovate.json"
        renovate_path.write_text("{invalid json}")

        with pytest.raises(ConfigurationError, match="Failed to load"):
            integrator._load_renovate_config(renovate_path)

    def test_generate_renovate_config_basic(
        self,
        integrator: RenovateIntegrator,
    ) -> None:
        """Test generating basic Renovate config."""
        config = integrator._generate_renovate_config(
            timezone="UTC",
            assignees="@team",
            reviewers="@reviewers",
            automerge_actions=True,
        )

        assert "$schema" in config
        assert config["extends"] == ["config:recommended"]
        assert config["timezone"] == "UTC"
        assert config["assignees"] == ["@team"]
        assert config["reviewers"] == ["@reviewers"]
        assert "packageRules" in config
        assert len(config["packageRules"]) == 4  # pre-commit, pep621 (2x), github-actions

    def test_generate_renovate_config_with_existing_config(
        self,
        integrator: RenovateIntegrator,
    ) -> None:
        """Test generating Renovate config with existing configuration."""
        existing = {
            "extends": ["config:base", "schedule:weekly"],
            "ignoreDeps": ["some-package"],
            "prConcurrentLimit": 5,
        }

        config = integrator._generate_renovate_config(
            timezone="UTC",
            assignees="@team",
            reviewers="@reviewers",
            automerge_actions=True,
            existing_config=existing,
        )

        # Preserved keys from existing config
        assert config["ignoreDeps"] == ["some-package"]
        assert config["prConcurrentLimit"] == 5

    def test_generate_renovate_config_merges_package_rules(
        self,
        integrator: RenovateIntegrator,
    ) -> None:
        """Test that custom package rules are preserved."""
        existing = {
            "packageRules": [
                {
                    "matchManagers": ["npm"],
                    "groupName": "npm dependencies",
                },
                {
                    "description": "Custom rule without matchManagers",
                    "matchPackageNames": ["special-package"],
                },
            ],
        }

        config = integrator._generate_renovate_config(
            timezone="UTC",
            assignees="@team",
            reviewers="@reviewers",
            automerge_actions=True,
            existing_config=existing,
        )

        # Should have default rules + custom npm rule + custom special-package rule
        assert len(config["packageRules"]) == 6  # 4 defaults + 2 custom
        npm_rule = next((r for r in config["packageRules"] if r.get("matchManagers") == ["npm"]), None)
        assert npm_rule is not None
        special_rule = next(
            (r for r in config["packageRules"] if r.get("matchPackageNames") == ["special-package"]),
            None,
        )
        assert special_rule is not None

    def test_generate_renovate_config_skips_conflicting_package_rules(
        self,
        integrator: RenovateIntegrator,
    ) -> None:
        """Test that conflicting package rules are not duplicated."""
        existing = {
            "packageRules": [
                {
                    "description": "Conflicts with default pre-commit rule",
                    "matchManagers": ["pre-commit"],
                    "automerge": True,  # Different from default
                },
            ],
        }

        config = integrator._generate_renovate_config(
            timezone="UTC",
            assignees="@team",
            reviewers="@reviewers",
            automerge_actions=True,
            existing_config=existing,
        )

        # Should only have default rules, not the conflicting one
        assert len(config["packageRules"]) == 4  # Only defaults
        pre_commit_rules = [r for r in config["packageRules"] if r.get("matchManagers") == ["pre-commit"]]
        assert len(pre_commit_rules) == 1  # Only the default

    def test_get_renovate_status_not_enabled(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test getting Renovate status when not enabled."""
        status = integrator.get_renovate_status(tmp_path)

        assert status["enabled"] is False
        assert status["config_file"] is None
        assert status["valid"] is False
        assert len(status["errors"]) == 0

    def test_get_renovate_status_enabled_with_renovate_json(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
        sample_renovate_config: dict[str, Any],
    ) -> None:
        """Test getting Renovate status when enabled with renovate.json."""
        renovate_path = tmp_path / "renovate.json"
        renovate_path.write_text(json.dumps(sample_renovate_config))

        status = integrator.get_renovate_status(tmp_path)

        assert status["enabled"] is True
        assert status["config_file"] == str(renovate_path)
        assert status["valid"] is True
        assert len(status["errors"]) == 0

    def test_get_renovate_status_enabled_with_renovate_json5(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test getting Renovate status when enabled with renovate.json5."""
        renovate5_path = tmp_path / "renovate.json5"
        renovate5_path.write_text("// JSON5 config\n{}")

        status = integrator.get_renovate_status(tmp_path)

        assert status["enabled"] is True
        assert status["config_file"] == str(renovate5_path)
        assert status["valid"] is False
        assert any("JSON5" in err for err in status["errors"])

    def test_get_renovate_status_invalid_json(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test getting Renovate status with invalid JSON."""
        renovate_path = tmp_path / "renovate.json"
        renovate_path.write_text("{invalid}")

        status = integrator.get_renovate_status(tmp_path)

        assert status["enabled"] is True
        assert status["valid"] is False
        assert len(status["errors"]) > 0

    def test_detect_migration_needs_no_migration(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test detecting migration needs when no migration needed."""
        result = integrator.detect_migration_needs(tmp_path)

        assert result["needs_migration"] is False
        assert result["has_renovate"] is False
        assert len(result["dependabot_files"]) == 0
        assert len(result["deprecated_workflows"]) == 0
        assert len(result["recommendations"]) == 0

    def test_detect_migration_needs_with_dependabot(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test detecting migration needs with Dependabot config."""
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        dependabot_path = github_dir / "dependabot.yml"
        dependabot_path.write_text("version: 2\nupdates: []")

        result = integrator.detect_migration_needs(tmp_path)

        assert result["needs_migration"] is True
        assert result["has_renovate"] is False
        assert ".github/dependabot.yml" in result["dependabot_files"]
        assert any("Migrate to Renovate" in rec for rec in result["recommendations"])
        assert any("renovate.json" in rec for rec in result["recommendations"])

    def test_detect_migration_needs_with_dependabot_automerge_workflow(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test detecting Dependabot automerge workflow."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        automerge_path = workflows_dir / "dependabot-automerge.yml"
        automerge_path.write_text("name: Dependabot auto-merge")

        result = integrator.detect_migration_needs(tmp_path)

        assert result["needs_migration"] is True
        assert ".github/workflows/dependabot-automerge.yml" in result["deprecated_workflows"]
        assert any("automerge workflows" in rec for rec in result["recommendations"])

    def test_detect_migration_needs_with_various_automerge_filenames(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test detecting various Dependabot automerge workflow filenames."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        filenames = [
            "dependabot-automerge.yaml",
            "dependabot-auto-merge.yml",
            "auto-merge-dependabot.yml",
        ]

        for filename in filenames:
            workflow_path = workflows_dir / filename
            workflow_path.write_text("name: test")

        result = integrator.detect_migration_needs(tmp_path)

        assert result["needs_migration"] is True
        assert len(result["deprecated_workflows"]) == 3
        for filename in filenames:
            assert any(filename in wf for wf in result["deprecated_workflows"])

    def test_detect_migration_needs_with_renovate_already_present(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
        sample_renovate_config: dict[str, Any],
    ) -> None:
        """Test detecting migration needs when Renovate is already present."""
        # Create Renovate config
        renovate_path = tmp_path / "renovate.json"
        renovate_path.write_text(json.dumps(sample_renovate_config))

        # Create old Dependabot config
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        dependabot_path = github_dir / "dependabot.yml"
        dependabot_path.write_text("version: 2")

        result = integrator.detect_migration_needs(tmp_path)

        assert result["needs_migration"] is True
        assert result["has_renovate"] is True
        assert any("Cleanup" in rec for rec in result["recommendations"])
        assert not any("Add renovate.json" in rec for rec in result["recommendations"])

    def test_detect_migration_needs_renovate_in_github_dir(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
        sample_renovate_config: dict[str, Any],
    ) -> None:
        """Test detecting Renovate config in .github directory."""
        github_dir = tmp_path / ".github"
        github_dir.mkdir()
        renovate_path = github_dir / "renovate.json"
        renovate_path.write_text(json.dumps(sample_renovate_config))

        result = integrator.detect_migration_needs(tmp_path)

        assert result["has_renovate"] is True

    def test_integrate_renovate_config_json_formatting(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test that generated JSON is properly formatted."""
        change = integrator.integrate_renovate_config(tmp_path)

        # Should be valid JSON
        config = json.loads(change.new_content)
        assert isinstance(config, dict)

        # Should have proper indentation
        assert "  " in change.new_content  # 2-space indent

        # Should end with newline
        assert change.new_content.endswith("\n")

    def test_integrate_renovate_config_contains_required_fields(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test that generated config contains all required fields."""
        change = integrator.integrate_renovate_config(tmp_path)
        config = json.loads(change.new_content)

        # Required fields
        assert "$schema" in config
        assert "extends" in config
        assert "schedule" in config
        assert "timezone" in config
        assert "labels" in config
        assert "assignees" in config
        assert "reviewers" in config
        assert "packageRules" in config
        assert "vulnerabilityAlerts" in config
        assert "lockFileMaintenance" in config

    def test_integrate_renovate_config_package_rules_structure(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test that package rules have correct structure."""
        change = integrator.integrate_renovate_config(tmp_path)
        config = json.loads(change.new_content)

        package_rules = config["packageRules"]
        assert isinstance(package_rules, list)
        assert len(package_rules) == 4

        # Check pre-commit rule
        pre_commit_rule = next(
            (r for r in package_rules if r.get("matchManagers") == ["pre-commit"]),
            None,
        )
        assert pre_commit_rule is not None
        assert "description" in pre_commit_rule
        assert pre_commit_rule["automerge"] is False
        assert pre_commit_rule["groupName"] == "pre-commit hooks"

        # Check GitHub Actions rule
        gh_actions_rule = next(
            (r for r in package_rules if r.get("matchManagers") == ["github-actions"]),
            None,
        )
        assert gh_actions_rule is not None
        assert gh_actions_rule["matchUpdateTypes"] == ["minor", "patch"]
        assert gh_actions_rule["groupName"] == "GitHub Actions"

    def test_integrate_renovate_config_vulnerability_alerts_structure(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test that vulnerability alerts have correct structure."""
        change = integrator.integrate_renovate_config(
            tmp_path,
            assignees="@security-team",
        )
        config = json.loads(change.new_content)

        vuln_alerts = config["vulnerabilityAlerts"]
        assert isinstance(vuln_alerts, dict)
        assert vuln_alerts["labels"] == ["security"]
        assert vuln_alerts["assignees"] == ["@security-team"]
        assert vuln_alerts["reviewers"] == ["@maintainers"]

    def test_integrate_renovate_config_lock_file_maintenance(
        self,
        integrator: RenovateIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test that lock file maintenance is configured."""
        change = integrator.integrate_renovate_config(tmp_path)
        config = json.loads(change.new_content)

        lock_file_maint = config["lockFileMaintenance"]
        assert isinstance(lock_file_maint, dict)
        assert lock_file_maint["enabled"] is True
        assert lock_file_maint["schedule"] == ["before 6am on monday"]
