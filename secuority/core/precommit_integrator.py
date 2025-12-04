"""Pre-commit hooks configuration integration for Secuority."""

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

from ..models.config import ConfigChange, Conflict
from ..models.exceptions import ConfigurationError
from ..models.interfaces import ChangeType


class PreCommitIntegrator:
    """Integrates pre-commit hooks configuration with security tools."""

    def __init__(self) -> None:
        """Initialize pre-commit integrator."""
        # Note: YAML functionality will be limited if PyYAML is not available
        pass

    def integrate_gitleaks_hook(
        self,
        project_path: Path,
        existing_config: dict[str, Any] | None = None,
    ) -> ConfigChange:
        """Integrate gitleaks hook into .pre-commit-config.yaml.

        Args:
            project_path: Path to the project directory
            existing_config: Existing pre-commit configuration

        Returns:
            ConfigChange for gitleaks integration

        Raises:
            ConfigurationError: If integration fails
        """
        precommit_path = project_path / ".pre-commit-config.yaml"

        # Load existing configuration if not provided
        if existing_config is None:
            existing_config = self._load_precommit_config(precommit_path)

        # Default gitleaks hook configuration
        gitleaks_repo = {
            "repo": "https://github.com/gitleaks/gitleaks",
            "rev": "v8.18.0",
            "hooks": [{"id": "gitleaks"}],
        }

        # Check if gitleaks is already configured
        gitleaks_exists = False
        if "repos" in existing_config:
            for repo in existing_config["repos"]:
                if isinstance(repo, dict) and "repo" in repo and "gitleaks" in repo["repo"].lower():
                    gitleaks_exists = True
                    break

        # Add gitleaks if not already present
        if not gitleaks_exists:
            if "repos" not in existing_config:
                existing_config["repos"] = []
            existing_config["repos"].append(gitleaks_repo)

        # Ensure basic pre-commit configuration is present
        if "default_language_version" not in existing_config:
            existing_config["default_language_version"] = {"python": "python3.13"}

        if "fail_fast" not in existing_config:
            existing_config["fail_fast"] = False

        if "minimum_pre_commit_version" not in existing_config:
            existing_config["minimum_pre_commit_version"] = "3.0.0"

        # Generate new content
        new_content = self._generate_yaml_content(existing_config)

        # Read existing content for comparison
        old_content = ""
        if precommit_path.exists():
            try:
                with precommit_path.open(encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {precommit_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if precommit_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=precommit_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Integrate gitleaks secret scanning hook",
            conflicts=[],
        )

    def integrate_security_hooks(self, project_path: Path, hooks: list[str] | None = None) -> ConfigChange:
        """Integrate multiple security hooks into .pre-commit-config.yaml.

        Args:
            project_path: Path to the project directory
            hooks: List of security hooks to integrate (default: ['gitleaks', 'bandit', 'safety'])

        Returns:
            ConfigChange for security hooks integration

        Raises:
            ConfigurationError: If integration fails
        """
        if hooks is None:
            hooks = ["gitleaks", "bandit", "safety"]

        precommit_path = project_path / ".pre-commit-config.yaml"
        existing_config = self._load_precommit_config(precommit_path)

        # Security hooks configurations
        security_repos = {
            "gitleaks": {
                "repo": "https://github.com/gitleaks/gitleaks",
                "rev": "v8.18.0",
                "hooks": [{"id": "gitleaks"}],
            },
            "bandit": {
                "repo": "https://github.com/PyCQA/bandit",
                "rev": "1.7.5",
                "hooks": [
                    {"id": "bandit", "args": ["-c", "pyproject.toml"], "additional_dependencies": ["bandit[toml]"]},
                ],
            },
            "safety": {
                "repo": "https://github.com/Lucas-C/pre-commit-hooks-safety",
                "rev": "v1.3.2",
                "hooks": [
                    {
                        "id": "python-safety-dependencies-check",
                        "args": ["--ignore=70612"],  # Ignore jinja2 vulnerability in dev dependencies
                    },
                ],
            },
            "detect-secrets": {
                "repo": "https://github.com/Yelp/detect-secrets",
                "rev": "v1.4.0",
                "hooks": [
                    {
                        "id": "detect-secrets",
                        "args": ["--baseline", ".secrets.baseline"],
                        "exclude": "package.lock.json",
                    },
                ],
            },
        }

        # Initialize repos if not present
        if "repos" not in existing_config:
            existing_config["repos"] = []

        # Track existing repos to avoid duplicates
        existing_repo_urls = set()
        for repo in existing_config["repos"]:
            if isinstance(repo, dict) and "repo" in repo:
                existing_repo_urls.add(repo["repo"])

        # Add requested security hooks
        for hook_name in hooks:
            if hook_name in security_repos:
                hook_config = security_repos[hook_name]
                # Check if this repo is already configured
                if hook_config["repo"] not in existing_repo_urls:
                    existing_config["repos"].append(hook_config)
                    existing_repo_urls.add(hook_config["repo"])

        # Ensure basic pre-commit configuration is present
        self._ensure_basic_precommit_config(existing_config)

        # Generate new content
        new_content = self._generate_yaml_content(existing_config)

        # Read existing content for comparison
        old_content = ""
        if precommit_path.exists():
            try:
                with precommit_path.open(encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {precommit_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if precommit_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=precommit_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Integrate security hooks (gitleaks, bandit, safety)",
            conflicts=[],
        )

    def merge_with_existing_precommit(self, project_path: Path, template_content: str) -> ConfigChange:
        """Merge security hooks with existing .pre-commit-config.yaml.

        Args:
            project_path: Path to the project directory
            template_content: Template pre-commit configuration content

        Returns:
            ConfigChange for merged pre-commit configuration

        Raises:
            ConfigurationError: If merge fails
        """
        precommit_path = project_path / ".pre-commit-config.yaml"

        # Load existing and template configurations
        existing_config = self._load_precommit_config(precommit_path)
        template_config = self._parse_yaml_content(template_content)

        # Merge configurations
        merged_config, conflicts = self._merge_precommit_configs(existing_config, template_config, precommit_path)

        # Generate new content
        new_content = self._generate_yaml_content(merged_config)

        # Read existing content for comparison
        old_content = ""
        if precommit_path.exists():
            try:
                with precommit_path.open(encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {precommit_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if precommit_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=precommit_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Merge pre-commit configuration with security hooks",
            conflicts=conflicts,
        )

    def _load_precommit_config(self, precommit_path: Path) -> dict[str, Any]:
        """Load existing .pre-commit-config.yaml configuration.

        Args:
            precommit_path: Path to .pre-commit-config.yaml file

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        if not precommit_path.exists():
            return {}

        try:
            with precommit_path.open(encoding="utf-8") as f:
                content = f.read()
            return self._parse_yaml_content(content)
        except Exception as e:
            raise ConfigurationError(f"Failed to load pre-commit config: {e}") from e

    def _parse_yaml_content(self, content: str) -> dict[str, Any]:
        """Parse YAML content into configuration dictionary.

        Args:
            content: YAML content as string

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If YAML parsing fails
        """
        try:
            return yaml.safe_load(content) or {}
        except Exception as e:
            raise ConfigurationError(f"Failed to parse YAML content: {e}") from e

    def _generate_yaml_content(self, config: dict[str, Any]) -> str:
        """Generate YAML content from configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            YAML content as string

        Raises:
            ConfigurationError: If YAML generation fails
        """
        try:
            return str(yaml.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2))
        except Exception as e:
            raise ConfigurationError(f"Failed to generate YAML content: {e}") from e

    def _ensure_basic_precommit_config(self, config: dict[str, Any]) -> None:
        """Ensure basic pre-commit configuration is present.

        Args:
            config: Configuration dictionary to update
        """
        if "default_language_version" not in config:
            config["default_language_version"] = {"python": "python3.13"}

        if "fail_fast" not in config:
            config["fail_fast"] = False

        if "minimum_pre_commit_version" not in config:
            config["minimum_pre_commit_version"] = "3.0.0"

        # Add global excludes if not present
        if "exclude" not in config:
            config["exclude"] = (
                "(?x)^(\n"
                "    \\.git/|\n"
                "    \\.mypy_cache/|\n"
                "    \\.pytest_cache/|\n"
                "    \\.ruff_cache/|\n"
                "    __pycache__/|\n"
                "    build/|\n"
                "    dist/|\n"
                "    \\.egg-info/\n"
                ")"
            )

    def _merge_precommit_configs(
        self,
        existing: dict[str, Any],
        template: dict[str, Any],
        file_path: Path,
    ) -> tuple[dict[str, Any], list[Conflict]]:
        """Merge existing and template pre-commit configurations.

        Args:
            existing: Existing configuration
            template: Template configuration
            file_path: Path to the configuration file

        Returns:
            Tuple of (merged_config, conflicts)
        """
        merged = existing.copy()
        conflicts = []

        # Merge repos (the most complex part)
        if "repos" in template:
            if "repos" not in merged:
                merged["repos"] = []

            # Track existing repos by URL to avoid duplicates
            existing_repo_urls = set()
            for repo in merged["repos"]:
                if isinstance(repo, dict) and "repo" in repo:
                    existing_repo_urls.add(repo["repo"])

            # Add template repos that don't already exist
            for template_repo in template["repos"]:
                if isinstance(template_repo, dict) and "repo" in template_repo:
                    repo_url = template_repo["repo"]
                    if repo_url not in existing_repo_urls:
                        merged["repos"].append(template_repo)
                        existing_repo_urls.add(repo_url)
                    else:
                        # Repo exists, check for hook conflicts
                        for existing_repo in merged["repos"]:
                            if isinstance(existing_repo, dict) and existing_repo.get("repo") == repo_url:
                                # Merge hooks if needed
                                hook_conflicts = self._merge_repo_hooks(existing_repo, template_repo, file_path)
                                conflicts.extend(hook_conflicts)
                                break

        # Merge other top-level configurations
        for key, value in template.items():
            if key == "repos":
                continue  # Already handled above

            if key not in existing:
                merged[key] = value
            elif existing[key] != value:
                # Configuration conflict
                conflict = Conflict(
                    file_path=file_path,
                    section=key,
                    existing_value=existing[key],
                    template_value=value,
                    description=f"Pre-commit configuration conflict in '{key}'",
                )
                conflicts.append(conflict)
                # Keep existing value by default

        return merged, conflicts

    def _merge_repo_hooks(
        self,
        existing_repo: dict[str, Any],
        template_repo: dict[str, Any],
        file_path: Path,
    ) -> list[Conflict]:
        """Merge hooks within a repository configuration.

        Args:
            existing_repo: Existing repository configuration
            template_repo: Template repository configuration
            file_path: Path to the configuration file

        Returns:
            List of conflicts found during merge
        """
        conflicts: list[Conflict] = []

        if "hooks" not in template_repo:
            return conflicts

        if "hooks" not in existing_repo:
            existing_repo["hooks"] = []

        # Track existing hooks by ID
        existing_hook_ids = set()
        for hook in existing_repo["hooks"]:
            if isinstance(hook, dict) and "id" in hook:
                existing_hook_ids.add(hook["id"])

        # Add template hooks that don't already exist
        for template_hook in template_repo["hooks"]:
            if isinstance(template_hook, dict) and "id" in template_hook:
                hook_id = template_hook["id"]
                if hook_id not in existing_hook_ids:
                    existing_repo["hooks"].append(template_hook)
                    existing_hook_ids.add(hook_id)
                else:
                    # Hook exists, potential configuration conflict
                    for existing_hook in existing_repo["hooks"]:
                        if isinstance(existing_hook, dict) and existing_hook.get("id") == hook_id:
                            # Check for configuration differences
                            for key, value in template_hook.items():
                                if key == "id":
                                    continue
                                if key not in existing_hook:
                                    existing_hook[key] = value
                                elif existing_hook[key] != value:
                                    conflict = Conflict(
                                        file_path=file_path,
                                        section=f"repos.{existing_repo['repo']}.hooks.{hook_id}.{key}",
                                        existing_value=existing_hook[key],
                                        template_value=value,
                                        description=f"Hook configuration conflict in {hook_id}.{key}",
                                    )
                                    conflicts.append(conflict)
                            break

        return conflicts

    def check_precommit_security_status(self, project_path: Path) -> dict[str, bool]:
        """Check which security hooks are configured in pre-commit.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary mapping security tool names to configuration status
        """
        status = {"gitleaks": False, "bandit": False, "safety": False, "detect-secrets": False}

        precommit_path = project_path / ".pre-commit-config.yaml"
        if not precommit_path.exists():
            return status

        try:
            config = self._load_precommit_config(precommit_path)

            if "repos" in config:
                for repo in config["repos"]:
                    if isinstance(repo, dict) and "repo" in repo:
                        repo_url = repo["repo"].lower()

                        if "gitleaks" in repo_url:
                            status["gitleaks"] = True
                        elif "bandit" in repo_url:
                            status["bandit"] = True
                        elif "safety" in repo_url:
                            status["safety"] = True
                        elif "detect-secrets" in repo_url:
                            status["detect-secrets"] = True

        except ConfigurationError:
            # If we can't load the config, assume hooks are not configured
            pass

        return status
