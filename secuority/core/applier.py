"""Configuration application engine with merge functionality and conflict resolution."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from rich.console import Console

from ..models.config import ApplyResult, ConfigChange, Conflict
from ..models.exceptions import ConfigurationError, ValidationError
from ..models.interfaces import (
    ChangeType,
    ConfigurationApplierInterface,
    DependencyAnalysis,
    Package,
)
from ..types.configuration import ConfigMap, TomlLoader, TomlWriter, YamlModule
from ..utils.diff import DiffGenerator
from ..utils.file_ops import FileOperations
from ..utils.user_interface import UserApprovalInterface
from .precommit_integrator import PreCommitIntegrator
from .security_tools import SecurityToolsIntegrator
from .workflow_integrator import WorkflowIntegrator

try:
    import tomllib as _tomllib
except ImportError:  # pragma: no cover - python<3.11 fallback
    try:
        import tomli as _tomllib  # type: ignore[import-untyped,no-redef]
    except ImportError:
        _tomllib = None

try:
    import tomli_w as _tomli_w  # type: ignore[import-untyped]
except ImportError:
    _tomli_w = None

try:
    import yaml as _yaml  # type: ignore[import-untyped]
except ImportError:
    _yaml = None

tomllib: TomlLoader | None = cast("TomlLoader | None", _tomllib)
tomli_w: TomlWriter | None = cast("TomlWriter | None", _tomli_w)
yaml: YamlModule | None = cast("YamlModule | None", _yaml)


def _ensure_config_map(value: object, *, context: str) -> ConfigMap:
    """Validate that vendor parsers produced a mapping."""
    if not isinstance(value, dict):
        raise ConfigurationError(f"{context} must be a mapping.")
    return cast(ConfigMap, value)


def _require_tomllib() -> TomlLoader:
    """Return an active TOML parser or raise a configuration error."""
    if tomllib is None:
        raise ConfigurationError("TOML parsing support is not available.")
    return tomllib


def _require_toml_writer() -> TomlWriter:
    """Return an active TOML writer (tomli_w) or raise."""
    if tomli_w is None:
        raise ConfigurationError("TOML writing support is not available.")
    return tomli_w


def _require_yaml() -> YamlModule:
    """Return the PyYAML module or raise."""
    if yaml is None:
        raise ConfigurationError("PyYAML is required for YAML merge operations.")
    return yaml


def _safe_load_yaml(content: str, *, context: str) -> ConfigMap:
    """Load YAML content and ensure it results in a mapping."""
    yaml_module = _require_yaml()
    loaded: object = yaml_module.safe_load(content) or {}
    return _ensure_config_map(loaded, context=context)


class ConfigurationMerger:
    """Handles merging of configuration files with conflict detection."""

    def __init__(self) -> None:
        self.diff_generator = DiffGenerator()

    def merge_toml_configs(
        self,
        existing: ConfigMap,
        template: ConfigMap,
        file_path: Path,
    ) -> tuple[ConfigMap, list[Conflict]]:
        """Merge TOML configurations with conflict detection."""
        merged: ConfigMap = existing.copy()
        conflicts: list[Conflict] = []

        for section, template_config in template.items():
            if section not in existing:
                # New section, add it directly
                merged[section] = template_config
            elif isinstance(template_config, dict) and isinstance(existing[section], dict):
                # Both are dictionaries, merge recursively
                merged_section, section_conflicts = self._merge_dict_section(
                    cast(ConfigMap, existing[section]),
                    cast(ConfigMap, template_config),
                    f"{section}",
                )
                merged[section] = merged_section

                # Add file path context to conflicts
                for conflict in section_conflicts:
                    conflict.file_path = file_path
                    conflicts.append(conflict)
            else:
                # Type mismatch or simple value conflict
                conflict = Conflict(
                    file_path=file_path,
                    section=section,
                    existing_value=existing[section],
                    template_value=template_config,
                    description=f"Configuration conflict in section '{section}'",
                )
                conflicts.append(conflict)
                # Keep existing value by default
                merged[section] = existing[section]

        return merged, conflicts

    def _merge_dict_section(
        self,
        existing: ConfigMap,
        template: ConfigMap,
        section_path: str,
    ) -> tuple[ConfigMap, list[Conflict]]:
        """Recursively merge dictionary sections with conflict detection."""
        merged: ConfigMap = existing.copy()
        conflicts: list[Conflict] = []

        for key, template_value in template.items():
            full_path = f"{section_path}.{key}"

            if key not in existing:
                # New key, add it directly
                merged[key] = template_value
            elif isinstance(template_value, dict) and isinstance(existing[key], dict):
                # Both are dictionaries, merge recursively
                merged_subsection, subsection_conflicts = self._merge_dict_section(
                    cast(ConfigMap, existing[key]),
                    cast(ConfigMap, template_value),
                    full_path,
                )
                merged[key] = merged_subsection
                conflicts.extend(subsection_conflicts)
            elif existing[key] != template_value:
                # Value conflict
                conflict = Conflict(
                    file_path=Path(),  # Will be set by caller
                    section=full_path,
                    existing_value=existing[key],
                    template_value=template_value,
                    description=f"Value conflict in {full_path}",
                )
                conflicts.append(conflict)
                # Keep existing value by default
                merged[key] = existing[key]
            # If values are equal, no conflict - keep existing

        return merged, conflicts

    def merge_yaml_configs(
        self,
        existing: ConfigMap,
        template: ConfigMap,
        file_path: Path,
    ) -> tuple[ConfigMap, list[Conflict]]:
        """Merge YAML configurations with conflict detection."""
        # YAML merging is similar to TOML
        return self.merge_toml_configs(existing, template, file_path)

    def merge_text_configs(
        self,
        existing_content: str,
        template_content: str,
        _file_path: Path,
    ) -> tuple[str, list[Conflict]]:
        """Merge text-based configurations like .gitignore."""
        existing_lines = set(existing_content.strip().splitlines())
        template_lines = template_content.strip().splitlines()

        # For text files like .gitignore, we typically append new lines
        merged_lines: list[str] = list(existing_lines)
        conflicts: list[Conflict] = []

        for raw_line in template_lines:
            line = raw_line.strip()
            if line and line not in existing_lines:
                merged_lines.append(line)

        # Sort lines for consistency (except for comments)
        comment_lines: list[str] = [line for line in merged_lines if line.startswith("#")]
        other_lines: list[str] = sorted([line for line in merged_lines if not line.startswith("#") and line])

        result_lines = comment_lines + other_lines
        return "\n".join(result_lines) + "\n", conflicts


class ConfigurationApplier(ConfigurationApplierInterface):
    """Applies configuration changes with backup and conflict resolution."""

    def __init__(self, backup_dir: Path | None = None):
        """Initialize configuration applier."""
        self.file_ops = FileOperations(backup_dir)
        self.merger = ConfigurationMerger()
        self.diff_generator = DiffGenerator()
        self.ui = UserApprovalInterface()
        self.security_integrator = SecurityToolsIntegrator()
        self.precommit_integrator = PreCommitIntegrator()
        self.workflow_integrator = WorkflowIntegrator()
        self.console = Console()

    def apply_changes(self, changes: list[ConfigChange], dry_run: bool = False) -> ApplyResult:
        """Apply configuration changes with backup and conflict resolution."""
        result = ApplyResult(dry_run=dry_run)

        for change in changes:
            try:
                if change.has_conflicts():
                    # Skip changes with unresolved conflicts
                    unresolved = change.get_unresolved_conflicts()
                    result.conflicts.extend(unresolved)
                    continue

                if dry_run:
                    # For dry run, just validate the change
                    if change.validate():
                        result.successful_changes.append(change)
                    else:
                        error = ValidationError(f"Invalid change for {change.file_path}")
                        result.failed_changes.append((change, error))
                else:
                    # Apply the actual change
                    backup_path = self._apply_single_change(change)
                    if backup_path:
                        result.backups_created.append(backup_path)
                    result.successful_changes.append(change)

            except Exception as e:
                result.failed_changes.append((change, e))

        return result

    def _apply_single_change(self, change: ConfigChange) -> Path | None:
        """Apply a single configuration change."""
        # Validate file permissions
        if not self.file_ops.validate_file_permissions(change.file_path):
            raise ConfigurationError(f"Insufficient permissions for {change.file_path}")

        # Apply the change based on type
        if change.change_type == ChangeType.CREATE:
            return self._create_file(change)
        if change.change_type == ChangeType.UPDATE:
            return self._update_file(change)
        if change.change_type == ChangeType.MERGE:
            return self._merge_file(change)
        raise ConfigurationError(f"Unknown change type: {change.change_type}")

    def _create_file(self, change: ConfigChange) -> Path | None:
        """Create a new file."""
        if change.file_path.exists():
            raise ConfigurationError(f"File already exists: {change.file_path}")

        return self.file_ops.safe_write_file(
            change.file_path,
            change.new_content,
            create_backup=False,  # No backup needed for new files
        )

    def _update_file(self, change: ConfigChange) -> Path | None:
        """Update an existing file."""
        if not change.file_path.exists():
            raise ConfigurationError(f"File does not exist: {change.file_path}")

        return self.file_ops.safe_write_file(change.file_path, change.new_content, create_backup=change.needs_backup())

    def _merge_file(self, change: ConfigChange) -> Path | None:
        """Merge configurations in an existing file."""
        if not change.file_path.exists():
            raise ConfigurationError(f"File does not exist: {change.file_path}")

        # For merge operations, the new_content should already be the merged result
        return self.file_ops.safe_write_file(change.file_path, change.new_content, create_backup=change.needs_backup())

    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of the specified file."""
        return self.file_ops.create_backup(file_path)

    def merge_configurations(self, existing: ConfigMap, template: ConfigMap) -> ConfigMap:
        """Merge existing configuration with template configuration."""
        merged, conflicts = self.merger.merge_toml_configs(existing, template, Path("config"))

        if conflicts:
            # For this interface method, we'll resolve conflicts automatically
            # by keeping existing values (which is the default behavior)
            pass

        return merged

    def merge_file_configurations(self, file_path: Path, template_content: str) -> ConfigChange:
        """Merge configurations for a specific file."""
        # Process template variables before merging
        processed_content = self._process_template_variables(template_content, file_path)

        if not file_path.exists():
            # File doesn't exist, create it
            return ConfigChange.create_file_change(
                file_path=file_path,
                content=processed_content,
                description=f"Create {file_path.name} from template",
            )

        # Read existing content
        try:
            with file_path.open(encoding="utf-8") as f:
                existing_content = f.read()
        except OSError as e:
            raise ConfigurationError(f"Failed to read {file_path}: {e}") from e

        # Determine merge strategy based on file type
        if file_path.suffix == ".toml":
            merged_content, conflicts = self._merge_toml_file(existing_content, processed_content, file_path)
        elif file_path.suffix in [".yaml", ".yml"]:
            merged_content, conflicts = self._merge_yaml_file(existing_content, processed_content, file_path)
        else:
            # Text-based merge for files like .gitignore
            merged_content, conflicts = self.merger.merge_text_configs(existing_content, processed_content, file_path)

        return ConfigChange.merge_file_change(
            file_path=file_path,
            old_content=existing_content,
            new_content=merged_content,
            description=f"Merge {file_path.name} with template",
            conflicts=conflicts,
        )

    def _merge_toml_file(
        self,
        existing_content: str,
        template_content: str,
        file_path: Path,
    ) -> tuple[str, list[Conflict]]:
        """Merge TOML file contents."""
        try:
            toml_module = _require_tomllib()
            existing_data = _ensure_config_map(toml_module.loads(existing_content), context="Existing TOML content")
            template_data = _ensure_config_map(toml_module.loads(template_content), context="Template TOML content")
        except Exception as e:  # pragma: no cover - tomllib errors are environment dependent
            raise ConfigurationError(f"Failed to parse TOML content: {e}") from e

        merged_data, conflicts = self.merger.merge_toml_configs(existing_data, template_data, file_path)

        return self._format_toml_content(merged_data), conflicts

    def _process_template_variables(self, template_content: str, file_path: Path) -> str:
        """Process template variables in content."""
        # Extract project information from existing pyproject.toml if available
        project_info = self._extract_project_info(file_path)

        # Resolve absolute path to get proper directory name
        abs_path = file_path.resolve()
        if file_path.name in ["pyproject.toml", ".gitignore", ".pre-commit-config.yaml"]:
            project_dir_name = abs_path.parent.name
        else:
            project_dir_name = (
                abs_path.parent.parent.name if abs_path.parent.name == "workflows" else abs_path.parent.name
            )

        project_name = project_info.get("name") or project_dir_name or "my-project"

        variables: dict[str, str] = {
            "project_name": project_name,
            "project_version": project_info.get("version", "0.1.0"),
            "project_description": project_info.get("description", f"A Python project: {project_name}"),
            "project_license": project_info.get("license", "MIT"),
            "author_name": project_info.get("author_name", "Your Name"),
            "author_email": project_info.get("author_email", "your.email@example.com"),
            "project_homepage": project_info.get("homepage", f"https://github.com/yourusername/{project_name}"),
            "project_repository": project_info.get("repository", f"https://github.com/yourusername/{project_name}"),
            "project_issues": project_info.get("issues", f"https://github.com/yourusername/{project_name}/issues"),
            "package_name": project_name.replace("-", "_"),
        }

        # Process template variables with default values
        def replace_variable(match: re.Match[str]) -> str:
            # Check if this is a GitHub Actions variable (preceded by $)
            # If so, return it unchanged
            if match.group(0).startswith("${{"):
                return match.group(0)

            var_expr = match.group(1).strip()

            # Handle default values: {{ var | default('value') }}
            if "|" in var_expr:
                var_name, default_part = var_expr.split("|", 1)
                var_name = var_name.strip()

                # Extract default value
                default_match = re.search(r"default\(['\"]([^'\"]*)['\"]", default_part)
                default_value = default_match.group(1) if default_match else ""

                return variables.get(var_name, default_value)
            return variables.get(var_expr, "")

        # Replace template variables (but not GitHub Actions variables like ${{ }})
        # Match {{ }} that are NOT preceded by $
        return re.sub(r"(?<!\$)\{\{\s*([^}]+)\s*\}\}", replace_variable, template_content)

    def _extract_project_info(self, file_path: Path) -> dict[str, str]:
        """Extract project information from existing pyproject.toml."""
        project_info: dict[str, str] = {}
        project_section = self._load_project_section(file_path)
        if project_section is None:
            return project_info

        self._populate_basic_project_fields(project_section, project_info)
        self._populate_license_info(project_section, project_info)
        self._populate_author_info(project_section, project_info)
        self._populate_project_urls(project_section, project_info)
        return project_info

    def _load_project_section(self, file_path: Path) -> ConfigMap | None:
        if file_path.name != "pyproject.toml" or not file_path.exists():
            return None

        try:
            toml_module = _require_tomllib()
            with file_path.open("rb") as f:
                existing_data = _ensure_config_map(
                    toml_module.load(f),
                    context=f"{file_path} content",
                )
        except Exception:
            return None

        project_section_raw = existing_data.get("project", {})
        if isinstance(project_section_raw, dict):
            return cast(ConfigMap, project_section_raw)
        return None

    def _populate_basic_project_fields(self, project_section: ConfigMap, project_info: dict[str, str]) -> None:
        for key in ("name", "version", "description"):
            value = project_section.get(key)
            if isinstance(value, str) and value:
                project_info[key] = value

    def _populate_license_info(self, project_section: ConfigMap, project_info: dict[str, str]) -> None:
        license_info = project_section.get("license")
        if isinstance(license_info, dict):
            license_map = cast(ConfigMap, license_info)
            text_value = license_map.get("text")
            if isinstance(text_value, str):
                project_info["license"] = text_value or "MIT"
        elif isinstance(license_info, str):
            project_info["license"] = license_info

    def _populate_author_info(self, project_section: ConfigMap, project_info: dict[str, str]) -> None:
        authors_value = project_section.get("authors")
        if not isinstance(authors_value, list):
            return
        author_candidates = cast(list[object], authors_value)
        author_entries: list[ConfigMap] = [
            cast(ConfigMap, author) for author in author_candidates if isinstance(author, dict)
        ]
        if not author_entries:
            return

        author_map = author_entries[0]
        name_value = author_map.get("name")
        email_value = author_map.get("email")
        if isinstance(name_value, str) and name_value:
            project_info["author_name"] = name_value
        if isinstance(email_value, str) and email_value:
            project_info["author_email"] = email_value

    def _populate_project_urls(self, project_section: ConfigMap, project_info: dict[str, str]) -> None:
        urls = project_section.get("urls")
        if not isinstance(urls, dict):
            return
        urls_map = cast(ConfigMap, urls)
        homepage = urls_map.get("Homepage")
        repository = urls_map.get("Repository")
        issues = urls_map.get("Issues") or urls_map.get("Bug Tracker")
        if isinstance(homepage, str) and homepage:
            project_info["homepage"] = homepage
        if isinstance(repository, str) and repository:
            project_info["repository"] = repository
        if isinstance(issues, str) and issues:
            project_info["issues"] = issues

    def _format_toml_content(self, data: ConfigMap) -> str:
        """Format TOML data as string."""
        try:
            writer = _require_toml_writer()
            result: str = writer.dumps(data)
            return result
        except Exception as e:
            raise ConfigurationError(f"Failed to format TOML content: {e}") from e

    def _merge_yaml_file(
        self,
        existing_content: str,
        template_content: str,
        file_path: Path,
    ) -> tuple[str, list[Conflict]]:
        """Merge YAML file contents."""
        try:
            existing_data = _safe_load_yaml(existing_content, context="Existing YAML content")
            template_data = _safe_load_yaml(template_content, context="Template YAML content")
        except Exception as e:
            raise ConfigurationError(f"Failed to parse YAML content: {e}") from e

        merged_data, conflicts = self.merger.merge_yaml_configs(existing_data, template_data, file_path)

        try:
            yaml_module = _require_yaml()
            merged_content = yaml_module.dump(
                merged_data,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to generate YAML content: {e}") from e

        return merged_content, conflicts

    def apply_changes_interactively(
        self,
        changes: list[ConfigChange],
        dry_run: bool = False,
        batch_mode: bool = False,
    ) -> ApplyResult:
        """Apply configuration changes with user interaction."""
        if dry_run:
            self.ui.show_dry_run_results(changes)
            return self.apply_changes(changes, dry_run=True)

        ready_changes, conflicted_changes = self._split_changes_by_conflict(changes)
        ready_changes = self._resolve_conflicts_interactively(changes, ready_changes, conflicted_changes)
        conflicted_changes = [c for c in changes if c.has_conflicts()]

        approved_changes, rejected_changes = self._gather_change_approvals(ready_changes, batch_mode)

        self.ui.show_apply_summary(approved_changes, rejected_changes, conflicted_changes)

        # Get final confirmation
        if approved_changes and self.ui.confirm_final_application(approved_changes):
            return self.apply_changes(approved_changes, dry_run=False)
        # Return empty result if no changes approved or user cancelled
        return ApplyResult(dry_run=False)

    @staticmethod
    def _split_changes_by_conflict(changes: list[ConfigChange]) -> tuple[list[ConfigChange], list[ConfigChange]]:
        ready_changes = [change for change in changes if not change.has_conflicts()]
        conflicted_changes = [change for change in changes if change.has_conflicts()]
        return ready_changes, conflicted_changes

    def _resolve_conflicts_interactively(
        self,
        changes: list[ConfigChange],
        ready_changes: list[ConfigChange],
        conflicted_changes: list[ConfigChange],
    ) -> list[ConfigChange]:
        if not conflicted_changes:
            return ready_changes

        self.console.print(f"Found {len(conflicted_changes)} changes with conflicts.")
        all_conflicts = [conflict for change in conflicted_changes for conflict in change.conflicts]
        resolved_conflicts = self.ui.resolve_conflicts_interactively(all_conflicts)

        for change in conflicted_changes:
            for resolved in resolved_conflicts:
                if resolved.file_path != change.file_path:
                    continue
                for change_conflict in change.conflicts:
                    if (
                        change_conflict.section == resolved.section
                        and change_conflict.existing_value == resolved.existing_value
                    ):
                        change_conflict.resolution = resolved.resolution

        return [change for change in changes if not change.has_conflicts()]

    def _gather_change_approvals(
        self,
        ready_changes: list[ConfigChange],
        batch_mode: bool,
    ) -> tuple[list[ConfigChange], list[ConfigChange]]:
        approved_changes: list[ConfigChange] = []
        rejected_changes: list[ConfigChange] = []

        if not ready_changes:
            return approved_changes, rejected_changes

        if batch_mode:
            approvals = self.ui.get_batch_approval(ready_changes)
            for change in ready_changes:
                if approvals.get(change.file_path, False):
                    approved_changes.append(change)
                else:
                    rejected_changes.append(change)
            return approved_changes, rejected_changes

        for change in ready_changes:
            if self.ui.get_change_approval(change):
                approved_changes.append(change)
            else:
                rejected_changes.append(change)

        return approved_changes, rejected_changes

    def apply_security_tools_integration(
        self,
        project_path: Path,
        tools: list[str] | None = None,
        dry_run: bool = False,
    ) -> ApplyResult:
        """Apply security tools integration to the project.

        Args:
            project_path: Path to the project directory
            tools: List of security tools to integrate (default: ['bandit', 'safety'])
            dry_run: Whether to perform a dry run

        Returns:
            ApplyResult with integration results
        """
        if tools is None:
            tools = ["bandit", "safety"]

        # Generate security tool configuration changes
        changes = self.security_integrator.integrate_security_tools(project_path, tools)

        # Apply the changes
        return self.apply_changes(changes, dry_run=dry_run)

    def get_security_integration_changes(
        self,
        project_path: Path,
        tools: list[str] | None = None,
    ) -> list[ConfigChange]:
        """Get security tools integration changes without applying them.

        Args:
            project_path: Path to the project directory
            tools: List of security tools to integrate (default: ['bandit', 'safety'])

        Returns:
            List of ConfigChange objects for security tools integration
        """
        if tools is None:
            tools = ["bandit", "safety"]

        return self.security_integrator.integrate_security_tools(project_path, tools)

    def get_quality_integration_changes(self, project_path: Path, tools: list[str] | None = None) -> list[ConfigChange]:
        """Get quality tools integration changes without applying them.

        Args:
            project_path: Path to the project directory
            tools: List of quality tools to integrate (default: ['ruff', 'mypy'])

        Returns:
            List of ConfigChange objects for quality tools integration
        """
        if tools is None:
            tools = ["ruff", "mypy"]

        changes: list[ConfigChange] = []
        pyproject_path = project_path / "pyproject.toml"

        # Generate quality tools configuration for pyproject.toml
        existing_data = self._load_pyproject_data(pyproject_path)

        modified = False
        if "ruff" in tools:
            modified |= self._ensure_ruff_config(existing_data)
        if "mypy" in tools:
            modified |= self._ensure_mypy_config(existing_data)

        if modified:
            # Convert back to TOML using the existing format method
            try:
                new_content = self._format_toml_content(existing_data)

                change = ConfigChange.merge_file_change(
                    file_path=pyproject_path,
                    old_content=pyproject_path.read_text() if pyproject_path.exists() else "",
                    new_content=new_content,
                    description=f"Add quality tools configuration: {', '.join(tools)}",
                    conflicts=[],
                )
                changes.append(change)

            except Exception as e:
                raise ConfigurationError(f"Failed to generate quality tools configuration: {e}") from e

        return changes

    def _get_tool_section(self, existing_data: ConfigMap) -> ConfigMap:
        tool_section = existing_data.get("tool")
        if isinstance(tool_section, dict):
            return cast(ConfigMap, tool_section)
        new_section: ConfigMap = {}
        existing_data["tool"] = new_section
        return new_section

    def _ensure_ruff_config(self, existing_data: ConfigMap) -> bool:
        tool_config = self._get_tool_section(existing_data)
        if "ruff" in tool_config:
            return False

        tool_config["ruff"] = {
            "line-length": 120,
            "target-version": "py313",
            "select": [
                "E",
                "F",
                "W",
                "C90",
                "I",
                "N",
                "UP",
                "YTT",
                "S",
                "BLE",
                "FBT",
                "B",
                "A",
                "COM",
                "C4",
                "DTZ",
                "T10",
                "EM",
                "EXE",
                "ISC",
                "ICN",
                "G",
                "INP",
                "PIE",
                "T20",
                "PYI",
                "PT",
                "Q",
                "RSE",
                "RET",
                "SLF",
                "SIM",
                "TID",
                "TCH",
                "ARG",
                "PTH",
                "ERA",
                "PD",
                "PGH",
                "PL",
                "TRY",
                "NPY",
                "RUF",
            ],
            "ignore": ["E501", "S101"],
            "fixable": ["ALL"],
            "unfixable": [],
            "exclude": [
                ".bzr",
                ".direnv",
                ".eggs",
                ".git",
                ".hg",
                ".mypy_cache",
                ".nox",
                ".pants.d",
                ".pytype",
                ".ruff_cache",
                ".svn",
                ".tox",
                ".venv",
                "__pypackages__",
                "_build",
                "buck-out",
                "build",
                "dist",
                "node_modules",
                "venv",
            ],
        }
        return True

    def _ensure_mypy_config(self, existing_data: ConfigMap) -> bool:
        tool_config = self._get_tool_section(existing_data)
        if "mypy" in tool_config:
            return False

        tool_config["mypy"] = {
            "python_version": "3.13",
            "warn_return_any": True,
            "warn_unused_configs": True,
            "disallow_untyped_defs": True,
            "disallow_incomplete_defs": True,
            "check_untyped_defs": True,
            "disallow_untyped_decorators": True,
            "no_implicit_optional": True,
            "warn_redundant_casts": True,
            "warn_unused_ignores": True,
            "warn_no_return": True,
            "warn_unreachable": True,
            "strict_equality": True,
        }
        return True

    def get_dependency_migration_change(
        self,
        project_path: Path,
        dependency_analysis: DependencyAnalysis,
    ) -> ConfigChange | None:
        """Get dependency migration change from requirements.txt to pyproject.toml.

        Args:
            project_path: Path to the project directory
            dependency_analysis: Analysis of current dependencies

        Returns:
            ConfigChange for dependency migration, or None if not needed
        """
        if not dependency_analysis.migration_needed:
            return None

        pyproject_path = project_path / "pyproject.toml"
        requirements_path = project_path / "requirements.txt"
        if not requirements_path.exists():
            return None

        existing_data = self._load_pyproject_data(pyproject_path)
        project_section = existing_data.get("project")
        if not isinstance(project_section, dict):
            project_section = {}
            existing_data["project"] = project_section
        project_section["dependencies"] = self._build_dependency_specs(
            dependency_analysis.requirements_packages,
        )

        return self._create_pyproject_change(
            pyproject_path=pyproject_path,
            existing_data=existing_data,
            description="Migrate dependencies from requirements.txt to pyproject.toml",
        )

    def _load_pyproject_data(self, pyproject_path: Path) -> ConfigMap:
        if not pyproject_path.exists():
            return {}
        try:
            toml_module = _require_tomllib()
            with pyproject_path.open("rb") as f:
                return _ensure_config_map(
                    toml_module.load(f),
                    context=f"{pyproject_path} content",
                )
        except Exception:
            return {}

    def _build_dependency_specs(self, packages: list[Package]) -> list[str]:
        dependencies: list[str] = []
        for package in packages:
            extras_part = f"[{','.join(package.extras)}]" if package.extras else ""
            version_part = f">={package.version}" if package.version else ""
            dep_spec = f"{package.name}{extras_part}{version_part}"
            if package.markers:
                dep_spec += f"; {package.markers}"
            dependencies.append(dep_spec)
        return dependencies

    def _create_pyproject_change(
        self,
        pyproject_path: Path,
        existing_data: ConfigMap,
        description: str,
    ) -> ConfigChange | None:
        try:
            writer = _require_toml_writer()
            new_content = writer.dumps(existing_data)
        except Exception as exc:
            raise ConfigurationError(f"Failed to generate dependency migration: {exc}") from exc

        return ConfigChange.merge_file_change(
            file_path=pyproject_path,
            old_content=pyproject_path.read_text() if pyproject_path.exists() else "",
            new_content=new_content,
            description=description,
            conflicts=[],
        )

    def apply_precommit_security_hooks(
        self,
        project_path: Path,
        hooks: list[str] | None = None,
        dry_run: bool = False,
    ) -> ApplyResult:
        """Apply pre-commit security hooks to the project.

        Args:
            project_path: Path to the project directory
            hooks: List of security hooks to integrate (default: ['gitleaks', 'bandit', 'safety'])
            dry_run: Whether to perform a dry run

        Returns:
            ApplyResult with integration results
        """
        if hooks is None:
            hooks = ["gitleaks", "bandit", "safety"]

        # Generate pre-commit security hooks configuration change
        change = self.precommit_integrator.integrate_security_hooks(project_path, hooks)

        # Apply the change
        return self.apply_changes([change], dry_run=dry_run)

    def merge_precommit_with_template(
        self,
        project_path: Path,
        template_content: str,
        dry_run: bool = False,
    ) -> ApplyResult:
        """Merge existing pre-commit configuration with template.

        Args:
            project_path: Path to the project directory
            template_content: Template pre-commit configuration content
            dry_run: Whether to perform a dry run

        Returns:
            ApplyResult with merge results
        """
        # Generate merged pre-commit configuration change
        change = self.precommit_integrator.merge_with_existing_precommit(project_path, template_content)

        # Apply the change
        return self.apply_changes([change], dry_run=dry_run)

    def get_precommit_integration_changes(
        self,
        project_path: Path,
        hooks: list[str] | None = None,
    ) -> list[ConfigChange]:
        """Get pre-commit security hooks integration changes without applying them.

        Args:
            project_path: Path to the project directory
            hooks: List of security hooks to integrate (default: ['gitleaks', 'bandit', 'safety'])

        Returns:
            List of ConfigChange objects for pre-commit hooks integration
        """
        if hooks is None:
            hooks = ["gitleaks", "bandit", "safety"]

        change = self.precommit_integrator.integrate_security_hooks(project_path, hooks)
        return [change]

    def apply_ci_workflows(
        self,
        project_path: Path,
        workflows: list[str] | None = None,
        python_versions: list[str] | None = None,
        dry_run: bool = False,
    ) -> ApplyResult:
        """Apply CI/CD workflows to the project.

        Args:
            project_path: Path to the project directory
            workflows: List of workflows to generate (default: ['security', 'quality', 'cicd'])
            python_versions: List of Python versions to test
            dry_run: Whether to perform a dry run

        Returns:
            ApplyResult with workflow generation results
        """
        if workflows is None:
            workflows = ["security", "quality", "cicd"]

        # Generate CI/CD workflow configuration changes
        changes = self.workflow_integrator.generate_workflows(project_path, workflows, python_versions)

        # Apply the changes
        return self.apply_changes(changes, dry_run=dry_run)

    def get_workflow_integration_changes(
        self,
        project_path: Path,
        workflows: list[str] | None = None,
        python_versions: list[str] | None = None,
    ) -> list[ConfigChange]:
        """Get CI/CD workflow integration changes without applying them.

        Args:
            project_path: Path to the project directory
            workflows: List of workflows to generate (default: ['security', 'quality', 'cicd'])
            python_versions: List of Python versions to test

        Returns:
            List of ConfigChange objects for workflow integration
        """
        if workflows is None:
            workflows = ["security", "quality", "cicd"]

        return self.workflow_integrator.generate_workflows(project_path, workflows, python_versions)

    def apply_complete_security_integration(
        self,
        project_path: Path,
        security_tools: list[str] | None = None,
        precommit_hooks: list[str] | None = None,
        workflows: list[str] | None = None,
        python_versions: list[str] | None = None,
        dry_run: bool = False,
    ) -> ApplyResult:
        """Apply complete security integration (tools + hooks + workflows).

        Args:
            project_path: Path to the project directory
            security_tools: List of security tools to integrate
            precommit_hooks: List of pre-commit hooks to integrate
            workflows: List of workflows to generate
            python_versions: List of Python versions to test
            dry_run: Whether to perform a dry run

        Returns:
            ApplyResult with complete integration results
        """
        all_changes: list[ConfigChange] = []

        # Get security tools integration changes
        if security_tools is None:
            security_tools = ["bandit", "safety"]
        security_changes = self.get_security_integration_changes(project_path, security_tools)
        all_changes.extend(security_changes)

        # Get pre-commit hooks integration changes
        if precommit_hooks is None:
            precommit_hooks = ["gitleaks", "bandit", "safety"]
        precommit_changes = self.get_precommit_integration_changes(project_path, precommit_hooks)
        all_changes.extend(precommit_changes)

        # Get workflow integration changes
        if workflows is None:
            workflows = ["security", "quality", "cicd"]
        workflow_changes = self.get_workflow_integration_changes(project_path, workflows, python_versions)
        all_changes.extend(workflow_changes)

        # Apply all changes
        return self.apply_changes(all_changes, dry_run=dry_run)
