"""Security tools configuration integration for Secuority."""

from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]
    except ImportError:
        tomllib = None  # type: ignore[assignment]

try:
    import tomli_w  # type: ignore[import-not-found]
except ImportError:
    tomli_w = None

from ..models.config import ConfigChange
from ..models.exceptions import ConfigurationError
from ..models.interfaces import ChangeType


class SecurityToolsIntegrator:
    """Integrates security tools configuration into project files."""

    def __init__(self) -> None:
        """Initialize security tools integrator."""
        pass

    def integrate_bandit_config(
        self,
        project_path: Path,
        existing_config: dict[str, Any] | None = None,
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
        bandit_config: dict[str, Any] = {
            "exclude_dirs": ["tests", "test_*"],
            "skips": ["B101", "B601"],  # Skip assert_used and shell_injection_process_args
        }

        # Add assert_used configuration for test files
        bandit_config["assert_used"] = {"skips": ["*_test.py", "test_*.py"]}

        # Merge with existing Bandit configuration if present
        if "tool" in existing_config and "bandit" in existing_config["tool"]:
            existing_bandit = existing_config["tool"]["bandit"]
            # Merge configurations, keeping existing values where they exist
            for key, value in bandit_config.items():
                if key not in existing_bandit:
                    existing_bandit[key] = value
                elif isinstance(value, dict) and isinstance(existing_bandit[key], dict):
                    # Merge nested dictionaries
                    for nested_key, nested_value in value.items():
                        if nested_key not in existing_bandit[key]:
                            existing_bandit[key][nested_key] = nested_value
        else:
            # Add new Bandit configuration
            if "tool" not in existing_config:
                existing_config["tool"] = {}
            existing_config["tool"]["bandit"] = bandit_config

        # Generate new content
        new_content = self._generate_toml_content(existing_config)

        # Read existing content for comparison
        old_content = ""
        if pyproject_path.exists():
            try:
                with open(pyproject_path, encoding="utf-8") as f:
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
        existing_config: dict[str, Any] | None = None,
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
        safety_config = {
            "ignore": [],  # Add CVE IDs to ignore specific vulnerabilities
            "full_report": True,
            "output": "json",
            "continue_on_error": False,
        }

        # Merge with existing Safety configuration if present
        if (
            "tool" in existing_config
            and "secuority" in existing_config["tool"]
            and "safety" in existing_config["tool"]["secuority"]
        ):
            existing_safety = existing_config["tool"]["secuority"]["safety"]
            # Merge configurations, keeping existing values where they exist
            for key, value in safety_config.items():
                if key not in existing_safety:
                    existing_safety[key] = value
        else:
            # Add new Safety configuration under tool.secuority.safety
            if "tool" not in existing_config:
                existing_config["tool"] = {}
            if "secuority" not in existing_config["tool"]:
                existing_config["tool"]["secuority"] = {}
            existing_config["tool"]["secuority"]["safety"] = safety_config

        # Generate new content
        new_content = self._generate_toml_content(existing_config)

        # Read existing content for comparison
        old_content = ""
        if pyproject_path.exists():
            try:
                with open(pyproject_path, encoding="utf-8") as f:
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

        changes = []

        # Load existing pyproject.toml configuration once
        pyproject_path = project_path / "pyproject.toml"
        existing_config = self._load_pyproject_config(pyproject_path)

        # Integrate each requested tool
        for tool in tools:
            if tool == "bandit":
                change = self.integrate_bandit_config(project_path, existing_config.copy())
                changes.append(change)
                # Update existing_config with the changes for next tool
                if change.new_content:
                    try:
                        existing_config = tomllib.loads(change.new_content)
                    except Exception as parse_error:
                        # Continue with original config if parsing fails
                        # This is expected during incremental config building
                        from ..utils.logger import debug

                        debug(f"Could not parse intermediate config after bandit: {parse_error}")
            elif tool == "safety":
                change = self.integrate_safety_config(project_path, existing_config.copy())
                changes.append(change)
                # Update existing_config with the changes for next tool
                if change.new_content:
                    try:
                        existing_config = tomllib.loads(change.new_content)
                    except Exception as parse_error:
                        # Continue with original config if parsing fails
                        # This is expected during incremental config building
                        from ..utils.logger import debug

                        debug(f"Could not parse intermediate config after safety: {parse_error}")

        return changes

    def _load_pyproject_config(self, pyproject_path: Path) -> dict[str, Any]:
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
            with open(pyproject_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            raise ConfigurationError(f"Failed to load pyproject.toml: {e}") from e

    def _generate_toml_content(self, config: dict[str, Any]) -> str:
        """Generate TOML content from configuration dictionary.

        Args:
            config: Configuration dictionary

        Returns:
            TOML content as string

        Raises:
            ConfigurationError: If TOML generation fails
        """
        try:
            import toml  # type: ignore[import-untyped]

            result: str = toml.dumps(config)
            return result
        except ImportError:
            pass

        if tomli_w is not None:
            try:
                tomli_result: str = tomli_w.dumps(config)
                return tomli_result
            except Exception as e:
                raise ConfigurationError(f"Failed to generate TOML content: {e}") from e

        # If no TOML library is available, raise an error
        raise ConfigurationError("No TOML library available for content generation")

    def check_security_tools_status(self, project_path: Path) -> dict[str, bool]:
        """Check which security tools are already configured.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary mapping tool names to configuration status
        """
        status = {"bandit": False, "safety": False}

        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return status

        try:
            config = self._load_pyproject_config(pyproject_path)

            # Check for Bandit configuration
            if "tool" in config and "bandit" in config["tool"]:
                status["bandit"] = True

            # Check for Safety configuration
            if "tool" in config and "secuority" in config["tool"] and "safety" in config["tool"]["secuority"]:
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
        recommendations = []
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
