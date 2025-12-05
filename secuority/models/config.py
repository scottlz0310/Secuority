"""Configuration change models with validation and conflict resolution."""

import difflib
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .exceptions import ValidationError
from .interfaces import ChangeType, validate_file_path


class ConflictResolution(Enum):
    """Strategies for resolving configuration conflicts."""

    KEEP_EXISTING = "keep_existing"
    USE_TEMPLATE = "use_template"
    MERGE = "merge"
    MANUAL = "manual"


class BackupStrategy(Enum):
    """Backup strategies for configuration changes."""

    ALWAYS = "always"
    ON_CONFLICT = "on_conflict"
    NEVER = "never"


@dataclass
class Conflict:
    """Represents a configuration conflict."""

    file_path: Path
    section: str
    existing_value: Any
    template_value: Any
    description: str
    resolution: ConflictResolution | None = None

    def __post_init__(self) -> None:
        """Validate conflict data."""
        if not self.file_path:
            raise ValidationError("Conflict file_path cannot be empty")
        if not self.section:
            raise ValidationError("Conflict section cannot be empty")

    def to_dict(self) -> dict[str, Any]:
        """Convert conflict to dictionary."""
        return {
            "file_path": str(self.file_path),
            "section": self.section,
            "existing_value": self.existing_value,
            "template_value": self.template_value,
            "description": self.description,
            "resolution": self.resolution.value if self.resolution else None,
        }


@dataclass
class ConfigChange:
    """Enhanced configuration change model with validation and conflict handling."""

    file_path: Path
    change_type: ChangeType
    new_content: str
    description: str
    old_content: str | None = None
    requires_backup: bool = True
    backup_strategy: BackupStrategy = BackupStrategy.ALWAYS
    conflicts: list[Conflict] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Validate configuration change data."""
        if not self.file_path:
            raise ValidationError("ConfigChange file_path cannot be empty")
        if not self.new_content and self.change_type != ChangeType.CREATE:
            msg = "ConfigChange new_content cannot be empty for non-CREATE changes"
            raise ValidationError(msg)
        if not self.description:
            raise ValidationError("ConfigChange description cannot be empty")

    def validate(self) -> bool:
        """Validate the configuration change."""
        try:
            # Validate file path for existing files
            if self.change_type == ChangeType.UPDATE and not validate_file_path(self.file_path):
                return False

            # Validate that old_content exists for UPDATE operations
            # Conflicts and metadata are validated by type hints
            return not (self.change_type == ChangeType.UPDATE and self.old_content is None)
        except Exception:
            return False

    def has_conflicts(self) -> bool:
        """Check if this change has unresolved conflicts."""
        return any(conflict.resolution is None for conflict in self.conflicts)

    def get_unresolved_conflicts(self) -> list[Conflict]:
        """Get list of unresolved conflicts."""
        return [conflict for conflict in self.conflicts if conflict.resolution is None]

    def resolve_conflict(self, section: str, resolution: ConflictResolution) -> bool:
        """Resolve a specific conflict."""
        for conflict in self.conflicts:
            if conflict.section == section:
                conflict.resolution = resolution
                return True
        return False

    def resolve_all_conflicts(self, resolution: ConflictResolution) -> None:
        """Resolve all conflicts with the same resolution strategy."""
        for conflict in self.conflicts:
            conflict.resolution = resolution

    def generate_diff(self) -> str:
        """Generate unified diff for the change."""
        if not self.old_content:
            # For new files, show the entire content as additions
            lines = self.new_content.splitlines(keepends=True)
            return "".join(f"+ {line}" for line in lines)

        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{self.file_path.name}",
            tofile=f"b/{self.file_path.name}",
            lineterm="",
        )

        return "".join(diff)

    def get_content_hash(self) -> str:
        """Get hash of the new content for change tracking."""
        content_bytes = self.new_content.encode("utf-8")
        return hashlib.sha256(content_bytes).hexdigest()[:8]

    def needs_backup(self) -> bool:
        """Determine if this change needs a backup based on strategy."""
        if self.backup_strategy == BackupStrategy.NEVER:
            return False
        if self.backup_strategy == BackupStrategy.ALWAYS:
            return self.requires_backup
        # BackupStrategy.ON_CONFLICT
        return self.requires_backup and self.has_conflicts()

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration change to dictionary."""
        return {
            "file_path": str(self.file_path),
            "change_type": self.change_type.value,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "description": self.description,
            "requires_backup": self.requires_backup,
            "backup_strategy": self.backup_strategy.value,
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "content_hash": self.get_content_hash(),
        }

    @classmethod
    def create_file_change(
        cls,
        file_path: Path,
        content: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> "ConfigChange":
        """Create a ConfigChange for creating a new file."""
        return cls(
            file_path=file_path,
            change_type=ChangeType.CREATE,
            new_content=content,
            description=description,
            old_content=None,
            requires_backup=False,
            metadata=metadata or {},
        )

    @classmethod
    def update_file_change(
        cls,
        file_path: Path,
        old_content: str,
        new_content: str,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> "ConfigChange":
        """Create a ConfigChange for updating an existing file."""
        return cls(
            file_path=file_path,
            change_type=ChangeType.UPDATE,
            old_content=old_content,
            new_content=new_content,
            description=description,
            requires_backup=True,
            metadata=metadata or {},
        )

    @classmethod
    def merge_file_change(
        cls,
        file_path: Path,
        old_content: str,
        new_content: str,
        description: str,
        conflicts: list[Conflict] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "ConfigChange":
        """Create a ConfigChange for merging configurations."""
        return cls(
            file_path=file_path,
            change_type=ChangeType.MERGE,
            old_content=old_content,
            new_content=new_content,
            description=description,
            requires_backup=True,
            conflicts=conflicts or [],
            backup_strategy=BackupStrategy.ON_CONFLICT,
            metadata=metadata or {},
        )


@dataclass
class ApplyResult:
    """Enhanced result of applying configuration changes."""

    successful_changes: list[ConfigChange] = field(default_factory=list)
    failed_changes: list[tuple[ConfigChange, Exception]] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    backups_created: list[Path] = field(default_factory=list)
    dry_run: bool = False
    total_changes: int = 0
    applied_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        """Calculate total changes if not provided."""
        if self.total_changes == 0:
            total = len(self.successful_changes) + len(self.failed_changes)
            self.total_changes = total

    def is_successful(self) -> bool:
        """Check if all changes were applied successfully."""
        return len(self.failed_changes) == 0 and len(self.conflicts) == 0

    def has_failures(self) -> bool:
        """Check if any changes failed to apply."""
        return len(self.failed_changes) > 0

    def has_unresolved_conflicts(self) -> bool:
        """Check if there are unresolved conflicts."""
        return any(conflict.resolution is None for conflict in self.conflicts)

    def get_success_rate(self) -> float:
        """Get the success rate as a percentage."""
        if self.total_changes == 0:
            return 100.0
        return (len(self.successful_changes) / self.total_changes) * 100.0

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the apply result."""
        return {
            "total_changes": self.total_changes,
            "successful": len(self.successful_changes),
            "failed": len(self.failed_changes),
            "conflicts": len(self.conflicts),
            "backups_created": len(self.backups_created),
            "success_rate": self.get_success_rate(),
            "dry_run": self.dry_run,
            "applied_at": self.applied_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert apply result to dictionary."""
        return {
            "successful_changes": [change.to_dict() for change in self.successful_changes],
            "failed_changes": [
                {"change": change.to_dict(), "error": str(error)} for change, error in self.failed_changes
            ],
            "conflicts": [conflict.to_dict() for conflict in self.conflicts],
            "backups_created": [str(path) for path in self.backups_created],
            "summary": self.get_summary(),
        }


@dataclass
class ChangeSet:
    """Collection of configuration changes to be applied together."""

    changes: list[ConfigChange] = field(default_factory=list)
    name: str = ""
    description: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def add_change(self, change: object) -> None:
        """Add a configuration change to the set."""
        if not isinstance(change, ConfigChange):
            raise ValidationError("Can only add ConfigChange instances")
        self.changes.append(change)

    def remove_change(self, file_path: Path) -> bool:
        """Remove a configuration change by file path."""
        for i, change in enumerate(self.changes):
            if change.file_path == file_path:
                del self.changes[i]
                return True
        return False

    def get_change_by_path(self, file_path: Path) -> ConfigChange | None:
        """Get a configuration change by file path."""
        for change in self.changes:
            if change.file_path == file_path:
                return change
        return None

    def has_conflicts(self) -> bool:
        """Check if any changes in the set have conflicts."""
        return any(change.has_conflicts() for change in self.changes)

    def get_all_conflicts(self) -> list[Conflict]:
        """Get all conflicts from all changes."""
        conflicts: list[Conflict] = []
        for change in self.changes:
            conflicts.extend(change.conflicts)
        return conflicts

    def validate_all(self) -> bool:
        """Validate all changes in the set."""
        return all(change.validate() for change in self.changes)

    def to_dict(self) -> dict[str, Any]:
        """Convert change set to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "changes": [change.to_dict() for change in self.changes],
            "has_conflicts": self.has_conflicts(),
            "total_changes": len(self.changes),
        }
