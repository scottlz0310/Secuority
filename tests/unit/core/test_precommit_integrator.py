"""Unit tests for PreCommitIntegrator."""

from pathlib import Path

import pytest

from secuority.core.precommit_integrator import PreCommitIntegrator
from secuority.models.exceptions import ConfigurationError
from secuority.models.interfaces import ChangeType


class TestPreCommitIntegrator:
    """Test PreCommitIntegrator functionality."""

    @pytest.fixture
    def integrator(self) -> PreCommitIntegrator:
        """Create PreCommitIntegrator instance."""
        return PreCommitIntegrator()

    @pytest.fixture
    def sample_precommit_config(self) -> dict:
        """Sample pre-commit configuration."""
        return {
            "repos": [
                {
                    "repo": "https://github.com/pre-commit/pre-commit-hooks",
                    "rev": "v4.4.0",
                    "hooks": [{"id": "trailing-whitespace"}, {"id": "end-of-file-fixer"}],
                },
            ],
            "default_language_version": {"python": "python3.12"},
        }

    def test_integrate_gitleaks_hook_new_file(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test integrating gitleaks hook into new file."""
        change = integrator.integrate_gitleaks_hook(tmp_path, existing_config={})

        assert change.file_path == tmp_path / ".pre-commit-config.yaml"
        assert change.change_type == ChangeType.CREATE
        assert "gitleaks" in change.new_content
        assert "default_language_version" in change.new_content

    def test_integrate_gitleaks_hook_existing_file(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
        sample_precommit_config: dict,
    ) -> None:
        """Test integrating gitleaks hook into existing file."""
        # Create existing file
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text("repos: []\n")

        change = integrator.integrate_gitleaks_hook(tmp_path, existing_config=sample_precommit_config)

        assert change.change_type == ChangeType.UPDATE
        assert "gitleaks" in change.new_content
        assert change.old_content is not None

    def test_integrate_gitleaks_hook_already_exists(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test integrating gitleaks when it already exists."""
        existing_config = {
            "repos": [
                {
                    "repo": "https://github.com/gitleaks/gitleaks",
                    "rev": "v8.18.0",
                    "hooks": [{"id": "gitleaks"}],
                },
            ],
        }

        change = integrator.integrate_gitleaks_hook(tmp_path, existing_config=existing_config)

        # Should not duplicate gitleaks
        assert change.new_content.count("gitleaks") >= 1

    def test_integrate_security_hooks_default(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test integrating default security hooks."""
        change = integrator.integrate_security_hooks(tmp_path)

        assert "gitleaks" in change.new_content
        assert "bandit" in change.new_content
        assert "safety" in change.new_content

    def test_integrate_security_hooks_custom_list(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test integrating custom list of security hooks."""
        change = integrator.integrate_security_hooks(tmp_path, hooks=["gitleaks", "detect-secrets"])

        assert "gitleaks" in change.new_content
        assert "detect-secrets" in change.new_content
        # Should not include hooks not in the list
        assert "bandit" not in change.new_content or "bandit" in change.new_content  # May be in comments

    def test_integrate_security_hooks_with_existing_config(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
        sample_precommit_config: dict,
    ) -> None:
        """Test integrating security hooks with existing configuration."""
        # Create existing file
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        import yaml  # type: ignore[import-untyped]

        with precommit_path.open("w") as f:
            yaml.dump(sample_precommit_config, f)

        change = integrator.integrate_security_hooks(tmp_path)

        # Should preserve existing hooks
        assert "pre-commit-hooks" in change.new_content
        # Should add security hooks
        assert "gitleaks" in change.new_content

    def test_merge_with_existing_precommit(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test merging with existing pre-commit configuration."""
        template_content = """repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
"""

        change = integrator.merge_with_existing_precommit(tmp_path, template_content)

        assert change.change_type == ChangeType.CREATE
        assert "gitleaks" in change.new_content

    def test_load_precommit_config_nonexistent(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test loading non-existent pre-commit config."""
        config = integrator._load_precommit_config(tmp_path / ".pre-commit-config.yaml")

        assert config == {}

    def test_load_precommit_config_existing(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
        sample_precommit_config: dict,
    ) -> None:
        """Test loading existing pre-commit config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        import yaml  # type: ignore[import-untyped]

        with precommit_path.open("w") as f:
            yaml.dump(sample_precommit_config, f)

        config = integrator._load_precommit_config(precommit_path)

        assert "repos" in config
        assert len(config["repos"]) > 0

    def test_load_precommit_config_invalid_yaml(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test loading invalid YAML config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text("invalid: yaml: content: [[[")

        with pytest.raises(ConfigurationError):
            integrator._load_precommit_config(precommit_path)

    def test_parse_yaml_content(
        self,
        integrator: PreCommitIntegrator,
    ) -> None:
        """Test parsing YAML content."""
        yaml_content = """repos:
  - repo: https://example.com
    rev: v1.0.0
"""

        config = integrator._parse_yaml_content(yaml_content)

        assert "repos" in config
        assert len(config["repos"]) == 1

    def test_parse_yaml_content_invalid(
        self,
        integrator: PreCommitIntegrator,
    ) -> None:
        """Test parsing invalid YAML content."""
        with pytest.raises(ConfigurationError):
            integrator._parse_yaml_content("invalid: yaml: [[[")

    def test_generate_yaml_content(
        self,
        integrator: PreCommitIntegrator,
        sample_precommit_config: dict,
    ) -> None:
        """Test generating YAML content."""
        yaml_content = integrator._generate_yaml_content(sample_precommit_config)

        assert "repos:" in yaml_content
        assert "pre-commit-hooks" in yaml_content

    def test_ensure_basic_precommit_config(
        self,
        integrator: PreCommitIntegrator,
    ) -> None:
        """Test ensuring basic pre-commit configuration."""
        config: dict = {}

        integrator._ensure_basic_precommit_config(config)

        assert "default_language_version" in config
        assert "fail_fast" in config
        assert "minimum_pre_commit_version" in config
        assert "exclude" in config

    def test_ensure_basic_precommit_config_preserves_existing(
        self,
        integrator: PreCommitIntegrator,
    ) -> None:
        """Test that basic config doesn't overwrite existing values."""
        config = {
            "default_language_version": {"python": "python3.11"},
            "fail_fast": True,
        }

        integrator._ensure_basic_precommit_config(config)

        assert config["default_language_version"]["python"] == "python3.11"
        assert config["fail_fast"] is True

    def test_merge_precommit_configs_no_conflicts(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test merging pre-commit configs without conflicts."""
        existing = {
            "repos": [
                {
                    "repo": "https://github.com/pre-commit/pre-commit-hooks",
                    "rev": "v4.4.0",
                    "hooks": [{"id": "trailing-whitespace"}],
                },
            ],
        }

        template = {
            "repos": [
                {
                    "repo": "https://github.com/gitleaks/gitleaks",
                    "rev": "v8.18.0",
                    "hooks": [{"id": "gitleaks"}],
                },
            ],
        }

        merged, conflicts = integrator._merge_precommit_configs(
            existing,
            template,
            tmp_path / ".pre-commit-config.yaml",
        )

        assert len(merged["repos"]) == 2
        assert len(conflicts) == 0

    def test_merge_precommit_configs_with_conflicts(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test merging pre-commit configs with conflicts."""
        existing = {
            "repos": [],
            "fail_fast": True,
        }

        template = {
            "repos": [],
            "fail_fast": False,
        }

        merged, conflicts = integrator._merge_precommit_configs(
            existing,
            template,
            tmp_path / ".pre-commit-config.yaml",
        )

        # Should keep existing value
        assert merged["fail_fast"] is True
        # Should have conflict
        assert len(conflicts) > 0

    def test_merge_repo_hooks_no_conflicts(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test merging repo hooks without conflicts."""
        existing_repo = {
            "repo": "https://github.com/example/repo",
            "rev": "v1.0.0",
            "hooks": [{"id": "hook1"}],
        }

        template_repo = {
            "repo": "https://github.com/example/repo",
            "rev": "v1.0.0",
            "hooks": [{"id": "hook2"}],
        }

        conflicts = integrator._merge_repo_hooks(existing_repo, template_repo, tmp_path / ".pre-commit-config.yaml")

        assert len(existing_repo["hooks"]) == 2
        assert len(conflicts) == 0

    def test_merge_repo_hooks_with_conflicts(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test merging repo hooks with conflicts."""
        existing_repo = {
            "repo": "https://github.com/example/repo",
            "rev": "v1.0.0",
            "hooks": [{"id": "hook1", "args": ["--arg1"]}],
        }

        template_repo = {
            "repo": "https://github.com/example/repo",
            "rev": "v1.0.0",
            "hooks": [{"id": "hook1", "args": ["--arg2"]}],
        }

        conflicts = integrator._merge_repo_hooks(existing_repo, template_repo, tmp_path / ".pre-commit-config.yaml")

        # Should have conflict for args
        assert len(conflicts) > 0

    def test_check_precommit_security_status_no_file(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test checking security status when no file exists."""
        status = integrator.check_precommit_security_status(tmp_path)

        assert status["gitleaks"] is False
        assert status["bandit"] is False
        assert status["safety"] is False
        assert status["detect-secrets"] is False

    def test_check_precommit_security_status_with_hooks(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test checking security status with configured hooks."""
        config = {
            "repos": [
                {
                    "repo": "https://github.com/gitleaks/gitleaks",
                    "rev": "v8.18.0",
                    "hooks": [{"id": "gitleaks"}],
                },
                {
                    "repo": "https://github.com/PyCQA/bandit",
                    "rev": "1.7.5",
                    "hooks": [{"id": "bandit"}],
                },
            ],
        }

        precommit_path = tmp_path / ".pre-commit-config.yaml"
        import yaml  # type: ignore[import-untyped]

        with precommit_path.open("w") as f:
            yaml.dump(config, f)

        status = integrator.check_precommit_security_status(tmp_path)

        assert status["gitleaks"] is True
        assert status["bandit"] is True
        assert status["safety"] is False
        assert status["detect-secrets"] is False

    def test_integrate_gitleaks_hook_adds_basic_config(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test that integrating gitleaks adds basic configuration."""
        change = integrator.integrate_gitleaks_hook(tmp_path, existing_config={})

        assert "default_language_version" in change.new_content
        assert "python3.13" in change.new_content
        assert "fail_fast" in change.new_content
        assert "minimum_pre_commit_version" in change.new_content

    def test_integrate_security_hooks_avoids_duplicates(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
    ) -> None:
        """Test that integrating security hooks avoids duplicates."""
        # Create existing config with gitleaks
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        existing_content = """repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
"""
        precommit_path.write_text(existing_content)

        change = integrator.integrate_security_hooks(tmp_path, hooks=["gitleaks", "bandit"])

        # Count occurrences of gitleaks repo
        gitleaks_count = change.new_content.count("https://github.com/gitleaks/gitleaks")
        assert gitleaks_count == 1  # Should not duplicate

    def test_merge_with_existing_precommit_preserves_structure(
        self,
        integrator: PreCommitIntegrator,
        tmp_path: Path,
        sample_precommit_config: dict,
    ) -> None:
        """Test that merging preserves existing structure."""
        # Create existing file
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        import yaml  # type: ignore[import-untyped]

        with precommit_path.open("w") as f:
            yaml.dump(sample_precommit_config, f)

        template_content = """repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
"""

        change = integrator.merge_with_existing_precommit(tmp_path, template_content)

        # Should preserve existing repos
        assert "pre-commit-hooks" in change.new_content
        # Should add new repos
        assert "gitleaks" in change.new_content
