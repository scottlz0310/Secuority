"""Security tools configuration integration for Secuority."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

try:
    import tomllib as _stdlib_tomllib  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - fallback for older Python
    _stdlib_tomllib = None

if _stdlib_tomllib is None:  # pragma: no cover - executed only without tomllib
    try:
        import tomli as _stdlib_tomllib  # type: ignore[import-not-found]
    except ImportError:
        _stdlib_tomllib = None

try:
    import tomli_w as _tomli_w
except ImportError:
    _tomli_w = None

from ..models.config import ConfigChange
from ..models.exceptions import ConfigurationError
from ..models.interfaces import ChangeType
from ..types import ConfigMap, TomlLoader, TomlWriter
from ..utils.logger import debug

tomllib: TomlLoader | None = cast(TomlLoader | None, _stdlib_tomllib)
tomli_w: TomlWriter | None = cast(TomlWriter | None, _tomli_w)


class SecurityToolsIntegrator:
    """Integrates security tools configuration into project files."""

    def __init__(self) -> None:
        """Initialize security tools integrator."""
        pass

    def integrate_bandit_config(
        self,
        project_path: Path,
        existing_config: ConfigMap | None = None,
    ) -> ConfigChange:
        """Integrate Bandit security linter configuration into pyproject.toml.

        Args:
            project_path: Path to the project directory
            existing_config: Existing pyproject.toml configuration

        Returns:
            ConfigChange for Bandit integration

        Raises:
            ConfigurationError: If integration fails
        """
        pyproject_path = project_path / "pyproject.toml"

        # Load existing configuration if not provided
        if existing_config is None:
            existing_config = self._load_pyproject_config(pyproject_path)

        # Default Bandit configuration
        bandit_config: ConfigMap = {
            "exclude_dirs": ["tests", "test_*"],
            "skips": ["B101", "B601"],  # Skip assert_used and shell_injection_process_args
        }

        # Add assert_used configuration for test files
        bandit_config["assert_used"] = {"skips": ["*_test.py", "test_*.py"]}

        # Merge with existing Bandit configuration if present
        tool_section = self._ensure_section(existing_config, "tool")
        bandit_section_value = tool_section.get("bandit")
        if isinstance(bandit_section_value, dict):
            existing_bandit = cast(ConfigMap, bandit_section_value)
            self._merge_missing_values(existing_bandit, bandit_config)
        else:
            tool_section["bandit"] = bandit_config

        # Generate new content
        new_content = self._generate_toml_content(existing_config)

        # Read existing content for comparison
        old_content = ""
        if pyproject_path.exists():
            try:
                with pyproject_path.open(encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {pyproject_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if pyproject_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=pyproject_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Integrate Bandit security linter configuration",
            conflicts=[],
        )

    def integrate_safety_config(
        self,
        project_path: Path,
        existing_config: ConfigMap | None = None,
    ) -> ConfigChange:
        """Integrate Safety dependency vulnerability scanner configuration.

        Args:
            project_path: Path to the project directory
            existing_config: Existing pyproject.toml configuration

        Returns:
            ConfigChange for Safety integration

        Raises:
            ConfigurationError: If integration fails
        """
        pyproject_path = project_path / "pyproject.toml"

        # Load existing configuration if not provided
        if existing_config is None:
            existing_config = self._load_pyproject_config(pyproject_path)

        # Default Safety configuration
        safety_config: ConfigMap = {
            "ignore": [],  # Add CVE IDs to ignore specific vulnerabilities
            "full_report": True,
            "output": "json",
            "continue_on_error": False,
        }

        # Merge with existing Safety configuration if present
        tool_section = self._ensure_section(existing_config, "tool")
        secuority_section = self._ensure_section(tool_section, "secuority")

        safety_section_value = secuority_section.get("safety")
        if isinstance(safety_section_value, dict):
            existing_safety = cast(ConfigMap, safety_section_value)
            self._merge_missing_values(existing_safety, safety_config)
        else:
            secuority_section["safety"] = safety_config

        # Generate new content
        new_content = self._generate_toml_content(existing_config)

        # Read existing content for comparison
        old_content = ""
        if pyproject_path.exists():
            try:
                with pyproject_path.open(encoding="utf-8") as f:
                    old_content = f.read()
            except OSError as e:
                raise ConfigurationError(f"Failed to read {pyproject_path}: {e}") from e

        # Determine change type
        change_type = ChangeType.UPDATE if pyproject_path.exists() else ChangeType.CREATE

        return ConfigChange(
            file_path=pyproject_path,
            change_type=change_type,
            old_content=old_content if change_type == ChangeType.UPDATE else None,
            new_content=new_content,
            description="Integrate Safety dependency vulnerability scanner configuration",
            conflicts=[],
        )

    def integrate_security_tools(self, project_path: Path, tools: list[str] | None = None) -> list[ConfigChange]:
        """Integrate multiple security tools configurations.

        Args:
            project_path: Path to the project directory
            tools: List of tools to integrate (default: ['bandit', 'safety'])

        Returns:
            List of ConfigChange objects for security tools integration

        Raises:
            ConfigurationError: If integration fails
        """
        if tools is None:
            tools = ["bandit", "safety"]

        changes: list[ConfigChange] = []

        # Load existing pyproject.toml configuration once
        pyproject_path = project_path / "pyproject.toml"
        existing_config = self._load_pyproject_config(pyproject_path)

        # Integrate each requested tool
        for tool in tools:
            if tool == "bandit":
                change = self.integrate_bandit_config(project_path, existing_config.copy())
                changes.append(change)
                if change.new_content:
                    try:
                        existing_config = self._loads_toml(change.new_content)
                    except ConfigurationError as parse_error:
                        debug(f"Could not parse intermediate config after bandit: {parse_error}")
            elif tool == "safety":
                change = self.integrate_safety_config(project_path, existing_config.copy())
                changes.append(change)
                if change.new_content:
                    try:
                        existing_config = self._loads_toml(change.new_content)
                    except ConfigurationError as parse_error:
                        debug(f"Could not parse intermediate config after safety: {parse_error}")

        return changes

    def _load_pyproject_config(self, pyproject_path: Path) -> ConfigMap:
        """Load existing pyproject.toml configuration.

        Args:
            pyproject_path: Path to pyproject.toml file

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        if not pyproject_path.exists():
            return {}

        if tomllib is None:
            raise ConfigurationError("TOML support not available")

        try:
            with pyproject_path.open("rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise ConfigurationError(f"Failed to load pyproject.toml: {e}") from e

    def _generate_toml_content(self, config: ConfigMap) -> str:
        """Generate TOML content from configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            TOML content as string

        Raises:
            ConfigurationError: If TOML generation fails
        """
        if tomli_w is None:
            raise ConfigurationError("tomli_w not available for TOML content generation")

        try:
            result: str = tomli_w.dumps(config)
            return result
        except Exception as e:
            raise ConfigurationError(f"Failed to generate TOML content: {e}") from e

    def check_security_tools_status(self, project_path: Path) -> dict[str, bool]:
        """Check which security tools are already configured.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary mapping tool names to configuration status
        """
        status: dict[str, bool] = {"bandit": False, "safety": False}

        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return status

        try:
            config = self._load_pyproject_config(pyproject_path)

            tool_section_value = config.get("tool")
            if isinstance(tool_section_value, dict):
                tool_section = cast(ConfigMap, tool_section_value)

                # Check for Bandit configuration
                if "bandit" in tool_section:
                    status["bandit"] = True

                # Check for Safety configuration
                sec_section_value = tool_section.get("secuority")
                if isinstance(sec_section_value, dict) and "safety" in sec_section_value:
                    status["safety"] = True

        except ConfigurationError:
            # If we can't load the config, assume tools are not configured
            pass

        return status

    def get_security_recommendations(self, project_path: Path) -> list[str]:
        """Get security tool configuration recommendations.

        Args:
            project_path: Path to the project directory

        Returns:
            List of recommendation strings
        """
        recommendations: list[str] = []
        status = self.check_security_tools_status(project_path)

        if not status["bandit"]:
            recommendations.append("Configure Bandit security linter in pyproject.toml for static security analysis")

        if not status["safety"]:
            recommendations.append("Configure Safety dependency vulnerability scanner for dependency security checks")

        # Check for pre-commit configuration
        precommit_path = project_path / ".pre-commit-config.yaml"
        if not precommit_path.exists():
            recommendations.append("Set up pre-commit hooks with security tools (gitleaks, bandit, safety)")

        return recommendations

    def _loads_toml(self, content: str) -> ConfigMap:
        if tomllib is None:
            raise ConfigurationError("TOML support not available")
        try:
            return tomllib.loads(content)
        except Exception as exc:  # pragma: no cover - tomli errors contain internal context
            raise ConfigurationError(f"Failed to parse generated TOML content: {exc}") from exc

    def _ensure_section(self, container: ConfigMap, key: str) -> ConfigMap:
        section = container.get(key)
        if not isinstance(section, dict):
            section = {}
            container[key] = section
        return cast(ConfigMap, section)

    def _merge_missing_values(self, target: ConfigMap, defaults: Mapping[str, Any]) -> None:
        for key, value in defaults.items():
            if key not in target:
                target[key] = value
                continue
            existing_value = target.get(key)
            if isinstance(existing_value, dict) and isinstance(value, dict):
                self._merge_missing_values(cast(ConfigMap, existing_value), cast(dict[str, Any], value))
            elif isinstance(value, dict):
                value_dict = cast(ConfigMap, value)
                target[key] = value_dict.copy()
