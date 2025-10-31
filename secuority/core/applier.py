"""Configuration application engine with merge functionality and conflict resolution."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

try:
    import tomli_w
except ImportError:
    tomli_w = None

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

from ..models.config import (
    ApplyResult,
    BackupStrategy,
    ChangeSet,
    ConfigChange,
    Conflict,
    ConflictResolution,
)
from ..models.exceptions import ConfigurationError, ValidationError
from ..models.interfaces import ChangeType, ConfigurationApplierInterface
from ..utils.diff import DiffGenerator
from ..utils.file_ops import FileOperations
from ..utils.user_interface import UserApprovalInterface
from .security_tools import SecurityToolsIntegrator
from .precommit_integrator import PreCommitIntegrator
from .workflow_integrator import WorkflowIntegrator


class ConfigurationMerger:
    """Handles merging of configuration files with conflict detection."""
    
    def __init__(self):
        self.diff_generator = DiffGenerator()
    
    def merge_toml_configs(
        self,
        existing: Dict[str, Any],
        template: Dict[str, Any],
        file_path: Path
    ) -> Tuple[Dict[str, Any], List[Conflict]]:
        """Merge TOML configurations with conflict detection."""
        merged = existing.copy()
        conflicts = []
        
        for section, template_config in template.items():
            if section not in existing:
                # New section, add it directly
                merged[section] = template_config
            elif isinstance(template_config, dict) and isinstance(existing[section], dict):
                # Both are dictionaries, merge recursively
                merged_section, section_conflicts = self._merge_dict_section(
                    existing[section], template_config, f"{section}"
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
                    description=f"Configuration conflict in section '{section}'"
                )
                conflicts.append(conflict)
                # Keep existing value by default
                merged[section] = existing[section]
        
        return merged, conflicts
    
    def _merge_dict_section(
        self,
        existing: Dict[str, Any],
        template: Dict[str, Any],
        section_path: str
    ) -> Tuple[Dict[str, Any], List[Conflict]]:
        """Recursively merge dictionary sections with conflict detection."""
        merged = existing.copy()
        conflicts = []
        
        for key, template_value in template.items():
            full_path = f"{section_path}.{key}"
            
            if key not in existing:
                # New key, add it directly
                merged[key] = template_value
            elif isinstance(template_value, dict) and isinstance(existing[key], dict):
                # Both are dictionaries, merge recursively
                merged_subsection, subsection_conflicts = self._merge_dict_section(
                    existing[key], template_value, full_path
                )
                merged[key] = merged_subsection
                conflicts.extend(subsection_conflicts)
            elif existing[key] != template_value:
                # Value conflict
                conflict = Conflict(
                    file_path=Path(""),  # Will be set by caller
                    section=full_path,
                    existing_value=existing[key],
                    template_value=template_value,
                    description=f"Value conflict in {full_path}"
                )
                conflicts.append(conflict)
                # Keep existing value by default
                merged[key] = existing[key]
            # If values are equal, no conflict - keep existing
        
        return merged, conflicts
    
    def merge_yaml_configs(
        self,
        existing: Dict[str, Any],
        template: Dict[str, Any],
        file_path: Path
    ) -> Tuple[Dict[str, Any], List[Conflict]]:
        """Merge YAML configurations with conflict detection."""
        # YAML merging is similar to TOML
        return self.merge_toml_configs(existing, template, file_path)
    
    def merge_text_configs(
        self,
        existing_content: str,
        template_content: str,
        file_path: Path
    ) -> Tuple[str, List[Conflict]]:
        """Merge text-based configurations like .gitignore."""
        existing_lines = set(existing_content.strip().splitlines())
        template_lines = template_content.strip().splitlines()
        
        # For text files like .gitignore, we typically append new lines
        merged_lines = list(existing_lines)
        conflicts = []
        
        for line in template_lines:
            line = line.strip()
            if line and line not in existing_lines:
                merged_lines.append(line)
        
        # Sort lines for consistency (except for comments)
        comment_lines = [line for line in merged_lines if line.startswith('#')]
        other_lines = sorted([line for line in merged_lines if not line.startswith('#') and line])
        
        result_lines = comment_lines + other_lines
        return '\n'.join(result_lines) + '\n', conflicts


class ConfigurationApplier(ConfigurationApplierInterface):
    """Applies configuration changes with backup and conflict resolution."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        """Initialize configuration applier."""
        self.file_ops = FileOperations(backup_dir)
        self.merger = ConfigurationMerger()
        self.diff_generator = DiffGenerator()
        self.ui = UserApprovalInterface()
        self.security_integrator = SecurityToolsIntegrator()
        self.precommit_integrator = PreCommitIntegrator()
        self.workflow_integrator = WorkflowIntegrator()
    
    def apply_changes(
        self,
        changes: List[ConfigChange],
        dry_run: bool = False
    ) -> ApplyResult:
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
    
    def _apply_single_change(self, change: ConfigChange) -> Optional[Path]:
        """Apply a single configuration change."""
        # Validate file permissions
        if not self.file_ops.validate_file_permissions(change.file_path):
            raise ConfigurationError(
                f"Insufficient permissions for {change.file_path}"
            )
        
        # Apply the change based on type
        if change.change_type == ChangeType.CREATE:
            return self._create_file(change)
        elif change.change_type == ChangeType.UPDATE:
            return self._update_file(change)
        elif change.change_type == ChangeType.MERGE:
            return self._merge_file(change)
        else:
            raise ConfigurationError(f"Unknown change type: {change.change_type}")
    
    def _create_file(self, change: ConfigChange) -> Optional[Path]:
        """Create a new file."""
        if change.file_path.exists():
            raise ConfigurationError(f"File already exists: {change.file_path}")
        
        return self.file_ops.safe_write_file(
            change.file_path,
            change.new_content,
            create_backup=False  # No backup needed for new files
        )
    
    def _update_file(self, change: ConfigChange) -> Optional[Path]:
        """Update an existing file."""
        if not change.file_path.exists():
            raise ConfigurationError(f"File does not exist: {change.file_path}")
        
        return self.file_ops.safe_write_file(
            change.file_path,
            change.new_content,
            create_backup=change.needs_backup()
        )
    
    def _merge_file(self, change: ConfigChange) -> Optional[Path]:
        """Merge configurations in an existing file."""
        if not change.file_path.exists():
            raise ConfigurationError(f"File does not exist: {change.file_path}")
        
        # For merge operations, the new_content should already be the merged result
        return self.file_ops.safe_write_file(
            change.file_path,
            change.new_content,
            create_backup=change.needs_backup()
        )
    
    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of the specified file."""
        return self.file_ops.create_backup(file_path)
    
    def merge_configurations(
        self,
        existing: Dict[str, Any],
        template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge existing configuration with template configuration."""
        merged, conflicts = self.merger.merge_toml_configs(
            existing, template, Path("config")
        )
        
        if conflicts:
            # For this interface method, we'll resolve conflicts automatically
            # by keeping existing values (which is the default behavior)
            pass
        
        return merged 
   
    def merge_file_configurations(
        self,
        file_path: Path,
        template_content: str
    ) -> ConfigChange:
        """Merge configurations for a specific file."""
        if not file_path.exists():
            # File doesn't exist, create it
            return ConfigChange.create_file_change(
                file_path=file_path,
                content=template_content,
                description=f"Create {file_path.name} from template"
            )
        
        # Read existing content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
        except (OSError, IOError) as e:
            raise ConfigurationError(f"Failed to read {file_path}: {e}") from e
        
        # Determine merge strategy based on file type
        if file_path.suffix == '.toml':
            merged_content, conflicts = self._merge_toml_file(
                existing_content, template_content, file_path
            )
        elif file_path.suffix in ['.yaml', '.yml']:
            merged_content, conflicts = self._merge_yaml_file(
                existing_content, template_content, file_path
            )
        else:
            # Text-based merge for files like .gitignore
            merged_content, conflicts = self.merger.merge_text_configs(
                existing_content, template_content, file_path
            )
        
        return ConfigChange.merge_file_change(
            file_path=file_path,
            old_content=existing_content,
            new_content=merged_content,
            description=f"Merge {file_path.name} with template",
            conflicts=conflicts
        )
    
    def _merge_toml_file(
        self,
        existing_content: str,
        template_content: str,
        file_path: Path
    ) -> Tuple[str, List[Conflict]]:
        """Merge TOML file contents."""
        if tomllib is None:
            raise ConfigurationError("TOML support not available")
        
        try:
            existing_data = tomllib.loads(existing_content)
            template_data = tomllib.loads(template_content)
        except Exception as e:
            raise ConfigurationError(f"Failed to parse TOML content: {e}") from e
        
        merged_data, conflicts = self.merger.merge_toml_configs(
            existing_data, template_data, file_path
        )
        
        # Convert back to TOML
        if tomli_w is None:
            raise ConfigurationError("TOML writing support not available")
        
        try:
            merged_content = tomli_w.dumps(merged_data)
        except Exception as e:
            raise ConfigurationError(f"Failed to generate TOML content: {e}") from e
        
        return merged_content, conflicts
    
    def _merge_yaml_file(
        self,
        existing_content: str,
        template_content: str,
        file_path: Path
    ) -> Tuple[str, List[Conflict]]:
        """Merge YAML file contents."""
        try:
            existing_data = yaml.safe_load(existing_content) or {}
            template_data = yaml.safe_load(template_content) or {}
        except Exception as e:
            raise ConfigurationError(f"Failed to parse YAML content: {e}") from e
        
        merged_data, conflicts = self.merger.merge_yaml_configs(
            existing_data, template_data, file_path
        )
        
        try:
            merged_content = yaml.dump(
                merged_data,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to generate YAML content: {e}") from e
        
        return merged_content, conflicts
    
    def apply_changes_interactively(
        self,
        changes: List[ConfigChange],
        dry_run: bool = False,
        batch_mode: bool = False
    ) -> ApplyResult:
        """Apply configuration changes with user interaction."""
        if dry_run:
            self.ui.show_dry_run_results(changes)
            return self.apply_changes(changes, dry_run=True)
        
        # Separate changes by conflict status
        conflicted_changes = [c for c in changes if c.has_conflicts()]
        ready_changes = [c for c in changes if not c.has_conflicts()]
        
        # Resolve conflicts first
        if conflicted_changes:
            print(f"Found {len(conflicted_changes)} changes with conflicts.")
            all_conflicts = []
            for change in conflicted_changes:
                all_conflicts.extend(change.conflicts)
            
            resolved_conflicts = self.ui.resolve_conflicts_interactively(all_conflicts)
            
            # Update changes with resolved conflicts
            for change in conflicted_changes:
                for conflict in resolved_conflicts:
                    if conflict.file_path == change.file_path:
                        # Find and update the corresponding conflict in the change
                        for change_conflict in change.conflicts:
                            if (change_conflict.section == conflict.section and
                                change_conflict.existing_value == conflict.existing_value):
                                change_conflict.resolution = conflict.resolution
            
            # Re-categorize changes after conflict resolution
            ready_changes = [c for c in changes if not c.has_conflicts()]
            conflicted_changes = [c for c in changes if c.has_conflicts()]
        
        # Get user approval for ready changes
        approved_changes = []
        rejected_changes = []
        
        if ready_changes:
            if batch_mode:
                approvals = self.ui.get_batch_approval(ready_changes)
                for change in ready_changes:
                    if approvals.get(change.file_path, False):
                        approved_changes.append(change)
                    else:
                        rejected_changes.append(change)
            else:
                for change in ready_changes:
                    if self.ui.get_change_approval(change):
                        approved_changes.append(change)
                    else:
                        rejected_changes.append(change)
        
        # Show summary
        self.ui.show_apply_summary(approved_changes, rejected_changes, conflicted_changes)
        
        # Get final confirmation
        if approved_changes and self.ui.confirm_final_application(approved_changes):
            return self.apply_changes(approved_changes, dry_run=False)
        else:
            # Return empty result if no changes approved or user cancelled
            return ApplyResult(dry_run=False)
    
    def apply_security_tools_integration(
        self,
        project_path: Path,
        tools: Optional[List[str]] = None,
        dry_run: bool = False
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
            tools = ['bandit', 'safety']
        
        # Generate security tool configuration changes
        changes = self.security_integrator.integrate_security_tools(project_path, tools)
        
        # Apply the changes
        return self.apply_changes(changes, dry_run=dry_run)
    
    def get_security_integration_changes(
        self,
        project_path: Path,
        tools: Optional[List[str]] = None
    ) -> List[ConfigChange]:
        """Get security tools integration changes without applying them.
        
        Args:
            project_path: Path to the project directory
            tools: List of security tools to integrate (default: ['bandit', 'safety'])
            
        Returns:
            List of ConfigChange objects for security tools integration
        """
        if tools is None:
            tools = ['bandit', 'safety']
        
        return self.security_integrator.integrate_security_tools(project_path, tools)
    
    def apply_precommit_security_hooks(
        self,
        project_path: Path,
        hooks: Optional[List[str]] = None,
        dry_run: bool = False
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
            hooks = ['gitleaks', 'bandit', 'safety']
        
        # Generate pre-commit security hooks configuration change
        change = self.precommit_integrator.integrate_security_hooks(project_path, hooks)
        
        # Apply the change
        return self.apply_changes([change], dry_run=dry_run)
    
    def merge_precommit_with_template(
        self,
        project_path: Path,
        template_content: str,
        dry_run: bool = False
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
        change = self.precommit_integrator.merge_with_existing_precommit(
            project_path, template_content
        )
        
        # Apply the change
        return self.apply_changes([change], dry_run=dry_run)
    
    def get_precommit_integration_changes(
        self,
        project_path: Path,
        hooks: Optional[List[str]] = None
    ) -> List[ConfigChange]:
        """Get pre-commit security hooks integration changes without applying them.
        
        Args:
            project_path: Path to the project directory
            hooks: List of security hooks to integrate (default: ['gitleaks', 'bandit', 'safety'])
            
        Returns:
            List of ConfigChange objects for pre-commit hooks integration
        """
        if hooks is None:
            hooks = ['gitleaks', 'bandit', 'safety']
        
        change = self.precommit_integrator.integrate_security_hooks(project_path, hooks)
        return [change]
    
    def apply_ci_workflows(
        self,
        project_path: Path,
        workflows: Optional[List[str]] = None,
        python_versions: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> ApplyResult:
        """Apply CI/CD workflows to the project.
        
        Args:
            project_path: Path to the project directory
            workflows: List of workflows to generate (default: ['security', 'quality'])
            python_versions: List of Python versions to test
            dry_run: Whether to perform a dry run
            
        Returns:
            ApplyResult with workflow generation results
        """
        if workflows is None:
            workflows = ['security', 'quality']
        
        # Generate CI/CD workflow configuration changes
        changes = self.workflow_integrator.generate_workflows(
            project_path, workflows, python_versions
        )
        
        # Apply the changes
        return self.apply_changes(changes, dry_run=dry_run)
    
    def get_workflow_integration_changes(
        self,
        project_path: Path,
        workflows: Optional[List[str]] = None,
        python_versions: Optional[List[str]] = None
    ) -> List[ConfigChange]:
        """Get CI/CD workflow integration changes without applying them.
        
        Args:
            project_path: Path to the project directory
            workflows: List of workflows to generate (default: ['security', 'quality'])
            python_versions: List of Python versions to test
            
        Returns:
            List of ConfigChange objects for workflow integration
        """
        if workflows is None:
            workflows = ['security', 'quality']
        
        return self.workflow_integrator.generate_workflows(
            project_path, workflows, python_versions
        )
    
    def apply_complete_security_integration(
        self,
        project_path: Path,
        security_tools: Optional[List[str]] = None,
        precommit_hooks: Optional[List[str]] = None,
        workflows: Optional[List[str]] = None,
        python_versions: Optional[List[str]] = None,
        dry_run: bool = False
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
        all_changes = []
        
        # Get security tools integration changes
        if security_tools is None:
            security_tools = ['bandit', 'safety']
        security_changes = self.get_security_integration_changes(project_path, security_tools)
        all_changes.extend(security_changes)
        
        # Get pre-commit hooks integration changes
        if precommit_hooks is None:
            precommit_hooks = ['gitleaks', 'bandit', 'safety']
        precommit_changes = self.get_precommit_integration_changes(project_path, precommit_hooks)
        all_changes.extend(precommit_changes)
        
        # Get workflow integration changes
        if workflows is None:
            workflows = ['security', 'quality']
        workflow_changes = self.get_workflow_integration_changes(
            project_path, workflows, python_versions
        )
        all_changes.extend(workflow_changes)
        
        # Apply all changes
        return self.apply_changes(all_changes, dry_run=dry_run)