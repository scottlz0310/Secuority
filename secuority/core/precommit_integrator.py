"""Pre-commit hooks configuration integration for Secuority."""

from pathlib import Path
from typing import Any, cast

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

from ..models.config import ConfigChange, Conflict
from ..models.exceptions import ConfigurationError
from ..models.interfaces import ChangeType


def _require_yaml_module() -> Any:
    """Ensure PyYAML is available and return the module."""
    if yaml is None:
        raise ConfigurationError("PyYAML is required to manage pre-commit configurations.")
    return yaml


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
        else:
            existing_config = self._coerce_config(existing_config)

        # Default gitleaks hook configuration
        gitleaks_repo = {
            "repo": "https://github.com/gitleaks/gitleaks",
            "rev": "v8.18.0",
            "hooks": [{"id": "gitleaks"}],
        }

        # Check if gitleaks is already configured
        gitleaks_exists = False
        repos = self._ensure_repos(existing_config)
        for repo in repos:
            repo_url = self._get_repo_url(repo)
            if repo_url and "gitleaks" in repo_url.lower():
                gitleaks_exists = True
                break

        # Add gitleaks if not already present
        if not gitleaks_exists:
            repos.append(self._clone_repo(gitleaks_repo))

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

        repos = self._ensure_repos(existing_config)

        # Track existing repos to avoid duplicates
        existing_repo_urls: set[str] = set()
        for repo in repos:
            repo_url = self._get_repo_url(repo)
            if repo_url:
                existing_repo_urls.add(repo_url)

        # Add requested security hooks
        for hook_name in hooks:
            if hook_name in security_repos:
                hook_config = security_repos[hook_name]
                repo_url = str(hook_config["repo"])
                if repo_url not in existing_repo_urls:
                    repos.append(self._clone_repo(hook_config))
                    existing_repo_urls.add(repo_url)

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

        parser = _require_yaml_module()
        try:
            with precommit_path.open(encoding="utf-8") as f:
                content = f.read()
            raw_config: object = parser.safe_load(content) or {}
            return self._coerce_config(raw_config)
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
        parser = _require_yaml_module()
        try:
            data: object = parser.safe_load(content) or {}
            return self._coerce_config(data)
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
        dumper = _require_yaml_module()
        try:
            return str(dumper.dump(config, default_flow_style=False, sort_keys=False, allow_unicode=True, indent=2))
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
        existing_sanitized = self._coerce_config(existing)
        template_sanitized = self._coerce_config(template)

        merged: dict[str, Any] = {key: value for key, value in existing_sanitized.items() if key != "repos"}
        merged_repos = [self._clone_repo(repo) for repo in existing_sanitized.get("repos", [])]
        merged["repos"] = merged_repos
        conflicts: list[Conflict] = []

        conflicts.extend(
            self._merge_repos_section(
                merged_repos=merged_repos,
                template_repos=template_sanitized.get("repos", []),
                file_path=file_path,
            ),
        )

        conflicts.extend(self._merge_top_level_settings(existing_sanitized, merged, template_sanitized, file_path))

        return merged, conflicts

    def _merge_repos_section(
        self,
        merged_repos: list[Any],
        template_repos: list[Any],
        file_path: Path,
    ) -> list[Conflict]:
        """Merge the 'repos' section while tracking conflicts."""
        conflicts: list[Conflict] = []
        if not template_repos:
            return conflicts

        repo_lookup: dict[str, dict[str, Any]] = {}
        for repo in merged_repos:
            repo_url = self._get_repo_url(repo)
            if repo_url:
                repo_lookup[repo_url] = repo

        for template_repo in template_repos:
            if not isinstance(template_repo, dict):
                continue

            repo_url = self._get_repo_url(template_repo)
            if not repo_url:
                continue

            if repo_url not in repo_lookup:
                cloned_repo = self._clone_repo(template_repo)
                merged_repos.append(cloned_repo)
                repo_lookup[repo_url] = cloned_repo
                continue

            existing_repo = repo_lookup[repo_url]
            conflicts.extend(self._merge_repo_hooks(existing_repo, template_repo, file_path))

        return conflicts

    def _merge_top_level_settings(
        self,
        existing: dict[str, Any],
        merged: dict[str, Any],
        template: dict[str, Any],
        file_path: Path,
    ) -> list[Conflict]:
        """Merge non-repo settings while tracking conflicts."""
        conflicts: list[Conflict] = []
        for key, value in template.items():
            if key == "repos":
                continue

            if key not in existing:
                merged[key] = value
                continue

            if existing[key] == value:
                continue

            conflict = Conflict(
                file_path=file_path,
                section=key,
                existing_value=existing[key],
                template_value=value,
                description=f"Pre-commit configuration conflict in '{key}'",
            )
            conflicts.append(conflict)

        return conflicts

    def _merge_repo_hooks(
        self,
        existing_repo: dict[str, Any],
        template_repo: dict[str, Any],
        file_path: Path,
    ) -> list[Conflict]:
        """Merge hooks within a repository configuration."""
        hooks_value = template_repo.get("hooks")
        if not isinstance(hooks_value, list):
            return []

        sanitized_hooks = [hook for hook in hooks_value if isinstance(hook, dict)]

        existing_hooks = self._ensure_hook_collection(existing_repo)
        hook_lookup = self._build_hook_lookup(existing_hooks)

        repo_name_value = self._get_repo_url(existing_repo) or "unknown"

        conflicts: list[Conflict] = []
        for template_hook in sanitized_hooks:
            hook_id = self._extract_hook_id(template_hook)
            if hook_id is None:
                continue

            if hook_id not in hook_lookup:
                cloned_hook = self._clone_hook(template_hook)
                existing_hooks.append(cloned_hook)
                hook_lookup[hook_id] = cloned_hook
                continue

            existing_hook = hook_lookup[hook_id]
            conflicts.extend(
                self._merge_hook_settings(
                    repo_name=repo_name_value,
                    hook_id=hook_id,
                    existing_hook=existing_hook,
                    template_hook=template_hook,
                    file_path=file_path,
                ),
            )

        return conflicts

    def _ensure_hook_collection(self, repo: dict[str, Any]) -> list[dict[str, Any]]:
        """Return the mutable hook list for a repo."""
        hooks = self._sanitize_hook_list(repo.get("hooks"))
        repo["hooks"] = hooks
        return hooks

    def _build_hook_lookup(self, hooks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Map hook IDs to their dicts for quick access."""
        lookup: dict[str, dict[str, Any]] = {}
        for hook in hooks:
            hook_id = self._extract_hook_id(hook)
            if hook_id:
                lookup[hook_id] = hook
        return lookup

    @staticmethod
    def _is_valid_hook(hook: Any) -> bool:
        """Ensure hook data has the expected structure."""
        return isinstance(hook, dict) and isinstance(hook.get("id"), str)

    def _merge_hook_settings(
        self,
        repo_name: str,
        hook_id: str,
        existing_hook: dict[str, Any],
        template_hook: dict[str, Any],
        file_path: Path,
    ) -> list[Conflict]:
        """Merge non-ID settings for a hook."""
        conflicts: list[Conflict] = []
        for key, value in template_hook.items():
            if key == "id":
                continue
            if key not in existing_hook:
                existing_hook[key] = value
                continue
            if existing_hook[key] == value:
                continue

            conflict = Conflict(
                file_path=file_path,
                section=f"repos.{repo_name}.hooks.{hook_id}.{key}",
                existing_value=existing_hook[key],
                template_value=value,
                description=f"Hook configuration conflict in {hook_id}.{key}",
            )
            conflicts.append(conflict)

        return conflicts

    def _coerce_config(self, raw: object) -> dict[str, Any]:
        config: dict[str, Any] = {str(key): value for key, value in raw.items()} if isinstance(raw, dict) else {}
        config["repos"] = self._sanitize_repo_list(config.get("repos"))
        return config

    def _sanitize_repo_list(self, repos_value: object) -> list[dict[str, Any]]:
        if not isinstance(repos_value, list):
            return []
        repos: list[dict[str, Any]] = []
        for repo in repos_value:
            if isinstance(repo, dict):
                sanitized = dict(cast(dict[str, Any], repo))
                sanitized["hooks"] = self._sanitize_hook_list(sanitized.get("hooks"))
                repos.append(sanitized)
        return repos

    def _sanitize_hook_list(self, hooks_value: object) -> list[dict[str, Any]]:
        if not isinstance(hooks_value, list):
            return []
        return [dict(cast(dict[str, Any], hook)) for hook in hooks_value if isinstance(hook, dict)]

    def _ensure_repos(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        repos_value = config.get("repos")
        sanitized = self._sanitize_repo_list(repos_value)
        config["repos"] = sanitized
        return sanitized

    @staticmethod
    def _get_repo_url(repo: dict[str, Any]) -> str | None:
        repo_value = repo.get("repo")
        if isinstance(repo_value, str) and repo_value:
            return repo_value
        return None

    @staticmethod
    def _extract_hook_id(hook: dict[str, Any]) -> str | None:
        hook_value = hook.get("id")
        if isinstance(hook_value, str) and hook_value:
            return hook_value
        return None

    def _clone_repo(self, repo: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_repo_list([repo])
        return sanitized[0] if sanitized else {}

    def _clone_hook(self, hook: dict[str, Any]) -> dict[str, Any]:
        sanitized = self._sanitize_hook_list([hook])
        return sanitized[0] if sanitized else {}

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
            repos = config.get("repos", [])
            for repo in repos:
                repo_url = self._get_repo_url(repo)
                if not repo_url:
                    continue
                repo_url_lower = repo_url.lower()
                if "gitleaks" in repo_url_lower:
                    status["gitleaks"] = True
                elif "bandit" in repo_url_lower:
                    status["bandit"] = True
                elif "safety" in repo_url_lower:
                    status["safety"] = True
                elif "detect-secrets" in repo_url_lower:
                    status["detect-secrets"] = True
        except ConfigurationError:
            pass

        return status
