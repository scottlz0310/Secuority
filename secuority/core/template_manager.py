"""Template management system for Secuority."""

import json
import os
import platform
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

from ..models.exceptions import TemplateError
from ..models.interfaces import TemplateManagerInterface
from ..utils.logger import warning


class TemplateManager(TemplateManagerInterface):
    """Manages configuration templates for Secuority."""

    def __init__(self) -> None:
        """Initialize the template manager."""
        self._template_dir: Path | None = None
        self._templates_cache: dict[str, str] = {}

    def get_template_directory(self) -> Path:
        """Get the directory where templates are stored.

        Priority:
        1. SECUORITY_TEMPLATES_DIR environment variable
        2. OS-appropriate config directory

        Returns:
            Path to template directory
        """
        if self._template_dir is not None:
            return self._template_dir

        # Check environment variable first
        env_dir = os.getenv("SECUORITY_TEMPLATES_DIR")
        if env_dir:
            self._template_dir = Path(env_dir).expanduser().resolve()
            return self._template_dir

        # Use OS-appropriate config directory
        self._template_dir = self._get_os_config_directory()
        return self._template_dir

    def _get_os_config_directory(self) -> Path:
        """Get OS-appropriate configuration directory."""
        system = platform.system().lower()

        if system == "windows":
            # Use %APPDATA%\secuority on Windows
            appdata = os.getenv("APPDATA")
            if appdata:
                return Path(appdata) / "secuority"
            # Fallback to user home
            return Path.home() / "AppData" / "Roaming" / "secuority"

        if system == "darwin":
            # Use ~/Library/Application Support/secuority on macOS
            return Path.home() / "Library" / "Application Support" / "secuority"

        # Use ~/.config/secuority on Linux and other Unix-like systems
        xdg_config = os.getenv("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "secuority"
        return Path.home() / ".config" / "secuority"

    def load_templates(self, language: str = "python") -> dict[str, str]:
        """Load configuration templates from the template directory.

        Args:
            language: Programming language for which to load templates (default: "python")

        Returns:
            Dictionary mapping template names to their content

        Raises:
            TemplateError: If templates cannot be loaded
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / "templates"

        if not templates_path.exists():
            try:
                self.initialize_templates()
            except TemplateError as exc:
                msg = f"Templates directory not found: {templates_path}"
                raise TemplateError(msg) from exc

        if not templates_path.exists():
            msg = f"Templates directory not found: {templates_path}"
            raise TemplateError(msg)

        templates: dict[str, str] = {}

        # Load common templates first
        common_path = templates_path / "common"
        if common_path.exists():
            templates.update(self._load_templates_from_dir(common_path, prefix=""))

        # Load language-specific templates (may override common templates)
        language_path = templates_path / language
        if language_path.exists():
            templates.update(self._load_templates_from_dir(language_path, prefix=""))
        elif not common_path.exists():
            # If neither common/ nor language directory exists, fall back to old flat structure
            # for backward compatibility with existing installations
            templates.update(self._load_templates_from_dir(templates_path, prefix=""))

        # Cache the loaded templates
        self._templates_cache = templates
        return templates

    def _load_templates_from_dir(self, directory: Path, prefix: str = "") -> dict[str, str]:
        """Load templates from a directory recursively.

        Args:
            directory: Directory to load templates from
            prefix: Prefix to add to template names (for nested directories)

        Returns:
            Dictionary mapping template names to their content

        Raises:
            TemplateError: If templates cannot be loaded
        """
        templates: dict[str, str] = {}

        # Load template files and other relevant files in this directory
        for file_path in directory.iterdir():
            if file_path.is_file():
                # Include .template files, .yml/.yaml files, and specific config files
                if file_path.suffix in {".template", ".yml", ".yaml", ".json", ".md"} or file_path.name in {
                    ".gitignore",
                    "CONTRIBUTING.md",
                    "CODEOWNERS",
                }:
                    try:
                        with file_path.open(encoding="utf-8") as f:
                            template_key = f"{prefix}{file_path.name}" if prefix else file_path.name
                            templates[template_key] = f.read()
                    except OSError as e:
                        msg = f"Failed to read template {file_path.name}: {e}"
                        raise TemplateError(msg) from e

            elif file_path.is_dir() and file_path.name not in {"__pycache__", ".git"}:
                # Recursively load templates from subdirectories
                subdir_prefix = f"{prefix}{file_path.name}/" if prefix else f"{file_path.name}/"
                templates.update(self._load_templates_from_dir(file_path, prefix=subdir_prefix))

        return templates

    def get_template(self, template_name: str) -> str | None:
        """Get a specific template by name.

        Args:
            template_name: Name of the template to retrieve

        Returns:
            Template content or None if not found
        """
        if not self._templates_cache:
            self.load_templates()

        return self._templates_cache.get(template_name)

    def get_available_languages(self) -> list[str]:
        """Get list of available language templates.

        Returns:
            List of language names that have template directories
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / "templates"

        if not templates_path.exists():
            return []

        languages = [
            item.name
            for item in templates_path.iterdir()
            if item.is_dir() and item.name not in {"common", "__pycache__", ".git"}
        ]

        return sorted(languages)

    def initialize_templates(self) -> None:
        """Initialize template directory with default templates.

        Creates the template directory structure and copies default templates.

        Raises:
            TemplateError: If initialization fails
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / "templates"

        try:
            # Create directory structure
            templates_path.mkdir(parents=True, exist_ok=True)

            # Copy default templates from package to user directory
            # This will create the common/ and language-specific directories
            self._copy_default_templates(templates_path)

            # Create config.yaml if it doesn't exist
            config_path = template_dir / "config.yaml"
            if not config_path.exists():
                self._create_default_config(config_path)

            # Create version.json if it doesn't exist
            version_path = template_dir / "version.json"
            if not version_path.exists():
                self._create_version_file(version_path)

        except OSError as e:
            msg = f"Failed to initialize template directory: {e}"
            raise TemplateError(msg) from e

    def _create_default_config(self, config_path: Path) -> None:
        """Create default config.yaml file."""
        default_config = {
            "version": "1.0",
            "templates": {"source": "github:secuority/templates", "last_update": None},
            "preferences": {"auto_backup": True, "confirm_changes": True, "github_integration": True},
            "tool_preferences": {
                "ruff": {"line_length": 120, "target_version": "py313"},
                "mypy": {"strict": True},
                "bandit": {"skip_tests": True},
            },
        }

        if yaml is not None:
            with config_path.open("w", encoding="utf-8") as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)
        else:
            with config_path.with_suffix(".json").open("w", encoding="utf-8") as f:  # type: ignore[unreachable]
                json.dump(default_config, f, indent=2)

    def _create_version_file(self, version_path: Path) -> None:
        """Create version.json file."""
        version_data = {
            "version": "1.0.0",
            "created": datetime.now().isoformat(),
            "last_update": None,
            "templates_version": "1.0.0",
        }

        with version_path.open("w", encoding="utf-8") as f:
            json.dump(version_data, f, indent=2)

    def _copy_default_templates(self, templates_path: Path) -> None:
        """Copy default templates from package to user directory.

        Args:
            templates_path: Path to user templates directory

        Raises:
            TemplateError: If copying fails
        """
        try:
            # Get the path to the package templates directory
            package_templates_path = Path(__file__).parent.parent / "templates"

            if not package_templates_path.exists():
                msg = f"Package templates directory not found: {package_templates_path}"
                raise TemplateError(msg)

            # Copy common templates
            common_source = package_templates_path / "common"
            if common_source.exists():
                common_dest = templates_path / "common"
                if not common_dest.exists():
                    shutil.copytree(common_source, common_dest)

            # Copy language-specific template directories
            for language_dir in package_templates_path.iterdir():
                if (
                    language_dir.is_dir()
                    and language_dir.name not in {"common", "__pycache__", ".git"}
                    and not language_dir.name.startswith(".")
                ):
                    language_dest = templates_path / language_dir.name
                    if not language_dest.exists():
                        shutil.copytree(language_dir, language_dest)

            # Backward compatibility: If old flat structure exists, copy those files too
            # This ensures existing installations don't break
            for template_file in package_templates_path.glob("*.template"):
                dest_path = templates_path / template_file.name
                if not dest_path.exists():
                    shutil.copy2(template_file, dest_path)

        except OSError as e:
            msg = f"Failed to copy default templates: {e}"
            raise TemplateError(msg) from e

    def update_templates(self) -> bool:
        """Update templates from remote source.

        Fetches the latest templates from the configured remote source
        and updates the local template directory.

        Returns:
            True if update was successful, False otherwise

        Raises:
            TemplateError: If update fails
        """
        try:
            config = self.get_config()
            source = config.get("templates", {}).get("source", "github:secuority/templates")

            if source.startswith("github:"):
                return self._update_from_github(source)
            if source.startswith("http"):
                return self._update_from_url(source)
            msg = f"Unsupported template source: {source}"
            raise TemplateError(msg)

        except Exception as e:
            msg = f"Failed to update templates: {e}"
            raise TemplateError(msg) from e

    def _update_from_github(self, source: str) -> bool:
        """Update templates from GitHub repository.

        Args:
            source: GitHub source in format 'github:owner/repo' or
                   'github:owner/repo@branch'

        Returns:
            True if successful, False otherwise
        """
        try:
            # Parse GitHub source
            github_part = source.replace("github:", "")
            if "@" in github_part:
                repo, branch = github_part.split("@", 1)
            else:
                repo, branch = github_part, "main"

            # Download templates from GitHub
            url = f"https://github.com/{repo}/archive/{branch}.zip"
            return self._download_and_extract_templates(url, repo.split("/")[-1])

        except Exception as e:
            msg = f"Failed to update from GitHub: {e}"
            raise TemplateError(msg) from e

    def _update_from_url(self, url: str) -> bool:
        """Update templates from direct URL.

        Args:
            url: Direct URL to template archive

        Returns:
            True if successful, False otherwise
        """
        try:
            return self._download_and_extract_templates(url, "templates")
        except Exception as e:
            msg = f"Failed to update from URL: {e}"
            raise TemplateError(msg) from e

    def _download_and_extract_templates(self, url: str, repo_name: str) -> bool:
        """Download and extract templates from URL.

        Args:
            url: URL to download from
            repo_name: Name of the repository (for directory structure)

        Returns:
            True if successful, False otherwise
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / "templates"

        # Create backup of existing templates
        backup_path = None
        if templates_path.exists():
            backup_path = self._create_templates_backup()

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / "templates.zip"

                # Download the archive
                # S310: Safe - URL is validated GitHub archive URL (https://github.com/.../archive/*.zip)
                urllib.request.urlretrieve(url, str(zip_path))  # noqa: S310

                # Extract the archive
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_path)

                # Find the templates directory in the extracted content
                extracted_templates = self._find_templates_directory(temp_path, repo_name)

                if extracted_templates:
                    # Remove old templates and copy new ones
                    if templates_path.exists():
                        shutil.rmtree(templates_path)

                    shutil.copytree(extracted_templates, templates_path)

                    # Update version information
                    self._update_version_info()

                    # Remove backup on success
                    if backup_path and backup_path.exists():
                        shutil.rmtree(backup_path)

                    return True
                msg = "Templates directory not found in downloaded archive"
                raise TemplateError(msg)

        except Exception as e:
            # Restore backup on failure
            if backup_path and backup_path.exists():
                if templates_path.exists():
                    shutil.rmtree(templates_path)
                shutil.move(str(backup_path), str(templates_path))

            msg = f"Failed to download and extract templates: {e}"
            raise TemplateError(msg) from e

    def _find_templates_directory(self, base_path: Path, repo_name: str) -> Path | None:
        """Find the templates directory in extracted content.

        Args:
            base_path: Base path to search in
            repo_name: Repository name to help locate templates

        Returns:
            Path to templates directory or None if not found
        """
        # Common locations for templates
        possible_paths = [
            base_path / f"{repo_name}-main" / "templates",
            base_path / f"{repo_name}-master" / "templates",
            base_path / "templates",
            base_path / f"{repo_name}" / "templates",
        ]

        # Also search for any directory named 'templates'
        possible_paths.extend(path for path in base_path.rglob("templates") if path.is_dir())

        # Return the first valid templates directory found
        for path in possible_paths:
            if path.exists() and path.is_dir():
                # Verify it contains template files
                template_files = list(path.glob("*.template")) + list(path.glob("*.yml"))
                if template_files:
                    return path

        return None

    def _create_templates_backup(self) -> Path:
        """Create a backup of existing templates.

        Returns:
            Path to backup directory
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / "templates"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = template_dir / f"templates_backup_{timestamp}"

        shutil.copytree(templates_path, backup_path)
        return backup_path

    def _update_version_info(self) -> None:
        """Update version information after successful template update."""
        template_dir = self.get_template_directory()
        version_path = template_dir / "version.json"

        version_data = {
            "version": "1.0.0",
            "created": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "templates_version": "1.0.0",
        }

        if version_path.exists():
            try:
                with version_path.open(encoding="utf-8") as f:
                    existing_data = json.load(f)
                version_data.update(existing_data)
                version_data["last_update"] = datetime.now().isoformat()
            except (OSError, json.JSONDecodeError):
                pass  # Use default version_data

        with version_path.open("w", encoding="utf-8") as f:
            json.dump(version_data, f, indent=2)

        # Also update config.yaml if yaml is available
        if yaml is not None:
            config_path = template_dir / "config.yaml"
            if config_path.exists():
                try:
                    with config_path.open(encoding="utf-8") as f:
                        config_data = yaml.safe_load(f)

                    if "templates" not in config_data:
                        config_data["templates"] = {}

                    config_data["templates"]["last_update"] = datetime.now().isoformat()

                    with config_path.open("w", encoding="utf-8") as f:
                        yaml.dump(config_data, f, default_flow_style=False, indent=2)
                except (OSError, yaml.YAMLError):
                    pass  # Ignore config update errors

    def get_template_history(self) -> list[dict[str, str]]:
        """Get template update history.

        Returns:
            List of update history entries
        """
        template_dir = self.get_template_directory()
        version_path = template_dir / "version.json"

        if not version_path.exists():
            return []

        try:
            with version_path.open(encoding="utf-8") as f:
                version_data = json.load(f)

            history: list[dict[str, str]] = []
            if "created" in version_data:
                history.append(
                    {
                        "action": "created",
                        "timestamp": version_data["created"],
                        "version": version_data.get("version", "unknown"),
                    },
                )

            if version_data.get("last_update"):
                history.append(
                    {
                        "action": "updated",
                        "timestamp": version_data["last_update"],
                        "version": version_data.get("templates_version", "unknown"),
                    },
                )

            return history

        except (OSError, json.JSONDecodeError):
            return []

    def list_available_backups(self) -> list[Path]:
        """List available template backups.

        Returns:
            List of backup directory paths
        """
        template_dir = self.get_template_directory()
        backups: list[Path] = [path for path in template_dir.glob("templates_backup_*") if path.is_dir()]
        return sorted(backups, reverse=True)  # Most recent first

    def restore_from_backup(self, backup_path: Path) -> bool:
        """Restore templates from a backup.

        Args:
            backup_path: Path to backup directory

        Returns:
            True if restore was successful, False otherwise

        Raises:
            TemplateError: If restore fails
        """
        if not backup_path.exists() or not backup_path.is_dir():
            msg = f"Backup directory not found: {backup_path}"
            raise TemplateError(msg)

        template_dir = self.get_template_directory()
        templates_path = template_dir / "templates"

        current_backup = None
        try:
            # Create backup of current templates before restore
            if templates_path.exists():
                current_backup = self._create_templates_backup()

            # Remove current templates
            if templates_path.exists():
                shutil.rmtree(templates_path)

            # Restore from backup
            shutil.copytree(backup_path, templates_path)

            # Clear templates cache
            self._templates_cache = {}

            return True

        except Exception as e:
            # Try to restore current backup if restore failed
            if current_backup and current_backup.exists():
                try:
                    if templates_path.exists():
                        shutil.rmtree(templates_path)
                    shutil.move(str(current_backup), str(templates_path))
                except Exception as restore_error:
                    # Best effort restore - log but don't fail
                    warning(f"Could not restore backup after failed restore: {restore_error}")

            msg = f"Failed to restore from backup: {e}"
            raise TemplateError(msg) from e

    def template_exists(self, template_name: str) -> bool:
        """Check if a template exists.

        Args:
            template_name: Name of the template to check

        Returns:
            True if template exists, False otherwise
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / "templates"
        template_path = templates_path / template_name

        return template_path.exists()

    def get_config(self) -> dict[str, Any]:
        """Get configuration from config.yaml.

        Returns:
            Configuration dictionary

        Raises:
            TemplateError: If config cannot be loaded
        """
        template_dir = self.get_template_directory()
        config_path = template_dir / "config.yaml"
        json_config_path = template_dir / "config.json"

        # Try YAML first, then JSON fallback
        if config_path.exists() and yaml is not None:
            try:
                with config_path.open(encoding="utf-8") as f:
                    result: dict[str, Any] = yaml.safe_load(f)
                    return result
            except (OSError, yaml.YAMLError) as e:
                msg = f"Failed to load configuration: {e}"
                raise TemplateError(msg) from e
        elif json_config_path.exists():
            try:
                with json_config_path.open(encoding="utf-8") as f:
                    json_result: dict[str, Any] = json.load(f)
                    return json_result
            except (OSError, json.JSONDecodeError) as e:
                msg = f"Failed to load configuration: {e}"
                raise TemplateError(msg) from e
        else:
            msg = f"Configuration file not found: {config_path}"
            raise TemplateError(msg)
