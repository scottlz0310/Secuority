"""Template management system for Secuority."""

import json
import os
import platform
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from ..models.exceptions import TemplateError
from ..models.interfaces import TemplateManagerInterface


class TemplateManager(TemplateManagerInterface):
    """Manages configuration templates for Secuority."""
    
    def __init__(self) -> None:
        """Initialize the template manager."""
        self._template_dir: Optional[Path] = None
        self._templates_cache: Dict[str, str] = {}
    
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
        env_dir = os.getenv('SECUORITY_TEMPLATES_DIR')
        if env_dir:
            self._template_dir = Path(env_dir).expanduser().resolve()
            return self._template_dir

        # Use OS-appropriate config directory
        self._template_dir = self._get_os_config_directory()
        return self._template_dir
    
    def _get_os_config_directory(self) -> Path:
        """Get OS-appropriate configuration directory."""
        system = platform.system().lower()

        if system == 'windows':
            # Use %APPDATA%\secuority on Windows
            appdata = os.getenv('APPDATA')
            if appdata:
                return Path(appdata) / 'secuority'
            else:
                # Fallback to user home
                return Path.home() / 'AppData' / 'Roaming' / 'secuority'

        elif system == 'darwin':
            # Use ~/Library/Application Support/secuority on macOS
            return Path.home() / 'Library' / 'Application Support' / 'secuority'

        else:
            # Use ~/.config/secuority on Linux and other Unix-like systems
            xdg_config = os.getenv('XDG_CONFIG_HOME')
            if xdg_config:
                return Path(xdg_config) / 'secuority'
            else:
                return Path.home() / '.config' / 'secuority'
    
    def load_templates(self) -> Dict[str, str]:
        """Load configuration templates from the template directory.

        Returns:
            Dictionary mapping template names to their content

        Raises:
            TemplateError: If templates cannot be loaded
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / 'templates'

        if not templates_path.exists():
            msg = f"Templates directory not found: {templates_path}"
            raise TemplateError(msg)

        templates = {}

        # Load template files
        template_files = [
            'pyproject.toml.template',
            '.gitignore.template',
            '.pre-commit-config.yaml.template'
        ]

        for template_file in template_files:
            template_path = templates_path / template_file
            if template_path.exists():
                try:
                    with open(template_path, encoding='utf-8') as f:
                        templates[template_file] = f.read()
                except OSError as e:
                    msg = f"Failed to read template {template_file}: {e}"
                    raise TemplateError(msg) from e

        # Load workflow templates
        workflows_dir = templates_path / 'workflows'
        if workflows_dir.exists():
            for workflow_file in workflows_dir.glob('*.yml'):
                try:
                    with open(workflow_file, encoding='utf-8') as f:
                        templates[f"workflows/{workflow_file.name}"] = f.read()
                except OSError as e:
                    msg = f"Failed to read workflow template {workflow_file.name}: {e}"
                    raise TemplateError(msg) from e

        self._templates_cache = templates
        return templates
    
    def get_template(self, template_name: str) -> Optional[str]:
        """Get a specific template by name.

        Args:
            template_name: Name of the template to retrieve

        Returns:
            Template content or None if not found
        """
        if not self._templates_cache:
            self.load_templates()

        return self._templates_cache.get(template_name)
    
    def initialize_templates(self) -> None:
        """Initialize template directory with default templates.

        Creates the template directory structure and copies default templates.

        Raises:
            TemplateError: If initialization fails
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / 'templates'
        workflows_path = templates_path / 'workflows'

        try:
            # Create directory structure
            templates_path.mkdir(parents=True, exist_ok=True)
            workflows_path.mkdir(parents=True, exist_ok=True)

            # Copy default templates from package to user directory
            self._copy_default_templates(templates_path)

            # Create config.yaml if it doesn't exist
            config_path = template_dir / 'config.yaml'
            if not config_path.exists():
                self._create_default_config(config_path)

            # Create version.json if it doesn't exist
            version_path = template_dir / 'version.json'
            if not version_path.exists():
                self._create_version_file(version_path)

        except OSError as e:
            msg = f"Failed to initialize template directory: {e}"
            raise TemplateError(msg) from e
    
    def _create_default_config(self, config_path: Path) -> None:
        """Create default config.yaml file."""
        default_config = {
            'version': '1.0',
            'templates': {
                'source': 'github:secuority/templates',
                'last_update': None
            },
            'preferences': {
                'auto_backup': True,
                'confirm_changes': True,
                'github_integration': True
            },
            'tool_preferences': {
                'ruff': {
                    'line_length': 88,
                    'target_version': 'py38'
                },
                'mypy': {
                    'strict': True
                },
                'bandit': {
                    'skip_tests': True
                }
            }
        }

        if yaml is not None:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, indent=2)
        else:
            # Fallback to JSON if yaml is not available
            with open(config_path.with_suffix('.json'), 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2)
    
    def _create_version_file(self, version_path: Path) -> None:
        """Create version.json file."""
        version_data = {
            'version': '1.0.0',
            'created': datetime.now().isoformat(),
            'last_update': None,
            'templates_version': '1.0.0'
        }

        with open(version_path, 'w', encoding='utf-8') as f:
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
            package_templates_path = Path(__file__).parent.parent / 'templates'
            
            if not package_templates_path.exists():
                msg = f"Package templates directory not found: {package_templates_path}"
                raise TemplateError(msg)
            
            # Template files to copy
            template_files = [
                'pyproject.toml.template',
                '.gitignore.template', 
                '.pre-commit-config.yaml.template'
            ]
            
            # Copy template files
            for template_file in template_files:
                source_path = package_templates_path / template_file
                dest_path = templates_path / template_file
                
                if source_path.exists() and not dest_path.exists():
                    shutil.copy2(source_path, dest_path)
            
            # Copy workflow templates
            workflows_source = package_templates_path / 'workflows'
            workflows_dest = templates_path / 'workflows'
            
            if workflows_source.exists():
                workflows_dest.mkdir(exist_ok=True)
                
                for workflow_file in workflows_source.glob('*.yml'):
                    dest_workflow = workflows_dest / workflow_file.name
                    if not dest_workflow.exists():
                        shutil.copy2(workflow_file, dest_workflow)
            
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
            source = config.get('templates', {}).get(
                'source', 'github:secuority/templates'
            )

            if source.startswith('github:'):
                return self._update_from_github(source)
            elif source.startswith('http'):
                return self._update_from_url(source)
            else:
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
            github_part = source.replace('github:', '')
            if '@' in github_part:
                repo, branch = github_part.split('@', 1)
            else:
                repo, branch = github_part, 'main'

            # Download templates from GitHub
            url = f"https://github.com/{repo}/archive/{branch}.zip"
            return self._download_and_extract_templates(url, repo.split('/')[-1])

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
            return self._download_and_extract_templates(url, 'templates')
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
        templates_path = template_dir / 'templates'

        # Create backup of existing templates
        backup_path = None
        if templates_path.exists():
            backup_path = self._create_templates_backup()

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                zip_path = temp_path / 'templates.zip'

                # Download the archive
                urllib.request.urlretrieve(url, str(zip_path))

                # Extract the archive
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_path)

                # Find the templates directory in the extracted content
                extracted_templates = self._find_templates_directory(
                    temp_path, repo_name
                )

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
                else:
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
    
    def _find_templates_directory(
        self, base_path: Path, repo_name: str
    ) -> Optional[Path]:
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
        for path in base_path.rglob("templates"):
            if path.is_dir():
                possible_paths.append(path)

        # Return the first valid templates directory found
        for path in possible_paths:
            if path.exists() and path.is_dir():
                # Verify it contains template files
                template_files = (
                    list(path.glob("*.template")) + list(path.glob("*.yml"))
                )
                if template_files:
                    return path

        return None
    
    def _create_templates_backup(self) -> Path:
        """Create a backup of existing templates.

        Returns:
            Path to backup directory
        """
        template_dir = self.get_template_directory()
        templates_path = template_dir / 'templates'
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = template_dir / f"templates_backup_{timestamp}"

        shutil.copytree(templates_path, backup_path)
        return backup_path
    
    def _update_version_info(self) -> None:
        """Update version information after successful template update."""
        template_dir = self.get_template_directory()
        version_path = template_dir / 'version.json'

        version_data = {
            'version': '1.0.0',
            'created': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat(),
            'templates_version': '1.0.0'
        }

        if version_path.exists():
            try:
                with open(version_path, encoding='utf-8') as f:
                    existing_data = json.load(f)
                version_data.update(existing_data)
                version_data['last_update'] = datetime.now().isoformat()
            except (OSError, json.JSONDecodeError):
                pass  # Use default version_data

        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, indent=2)

        # Also update config.yaml if yaml is available
        if yaml is not None:
            config_path = template_dir / 'config.yaml'
            if config_path.exists():
                try:
                    with open(config_path, encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)

                    if 'templates' not in config_data:
                        config_data['templates'] = {}

                    config_data['templates']['last_update'] = (
                        datetime.now().isoformat()
                    )

                    with open(config_path, 'w', encoding='utf-8') as f:
                        yaml.dump(
                            config_data, f, default_flow_style=False, indent=2
                        )
                except (OSError, yaml.YAMLError):
                    pass  # Ignore config update errors
    
    def get_template_history(self) -> List[Dict[str, str]]:
        """Get template update history.

        Returns:
            List of update history entries
        """
        template_dir = self.get_template_directory()
        version_path = template_dir / 'version.json'

        if not version_path.exists():
            return []

        try:
            with open(version_path, encoding='utf-8') as f:
                version_data = json.load(f)

            history = []
            if 'created' in version_data:
                history.append({
                    'action': 'created',
                    'timestamp': version_data['created'],
                    'version': version_data.get('version', 'unknown')
                })

            if 'last_update' in version_data and version_data['last_update']:
                history.append({
                    'action': 'updated',
                    'timestamp': version_data['last_update'],
                    'version': version_data.get('templates_version', 'unknown')
                })

            return history

        except (OSError, json.JSONDecodeError):
            return []
    
    def list_available_backups(self) -> List[Path]:
        """List available template backups.

        Returns:
            List of backup directory paths
        """
        template_dir = self.get_template_directory()
        backups = []

        for path in template_dir.glob("templates_backup_*"):
            if path.is_dir():
                backups.append(path)

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
        templates_path = template_dir / 'templates'

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
                except Exception:
                    pass  # Best effort restore

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
        templates_path = template_dir / 'templates'
        template_path = templates_path / template_name

        return template_path.exists()
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration from config.yaml.

        Returns:
            Configuration dictionary

        Raises:
            TemplateError: If config cannot be loaded
        """
        template_dir = self.get_template_directory()
        config_path = template_dir / 'config.yaml'
        json_config_path = template_dir / 'config.json'

        # Try YAML first, then JSON fallback
        if config_path.exists() and yaml is not None:
            try:
                with open(config_path, encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except (OSError, yaml.YAMLError) as e:
                msg = f"Failed to load configuration: {e}"
                raise TemplateError(msg) from e
        elif json_config_path.exists():
            try:
                with open(json_config_path, encoding='utf-8') as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                msg = f"Failed to load configuration: {e}"
                raise TemplateError(msg) from e
        else:
            msg = f"Configuration file not found: {config_path}"
            raise TemplateError(msg)