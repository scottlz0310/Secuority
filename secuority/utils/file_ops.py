"""File operations utilities for safe file handling and backup management."""

import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.exceptions import ConfigurationError


class FileOperations:
    """Handles safe file operations with backup support."""
    
    def __init__(self, backup_dir: Optional[Path] = None):
        """Initialize file operations with optional backup directory."""
        self.backup_dir = backup_dir or Path.home() / ".secuority" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of the specified file.
        
        Args:
            file_path: Path to the file to backup
            
        Returns:
            Path to the created backup file
            
        Raises:
            ConfigurationError: If backup creation fails
        """
        if not file_path.exists():
            raise ConfigurationError(f"Cannot backup non-existent file: {file_path}")
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{file_path.name}.{timestamp}.backup"
        backup_path = self.backup_dir / backup_name
        
        try:
            # Ensure backup directory exists
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file to backup location
            shutil.copy2(file_path, backup_path)
            
            # Verify backup was created successfully
            if not backup_path.exists():
                raise ConfigurationError(f"Backup file was not created: {backup_path}")
            
            return backup_path
            
        except (OSError, IOError) as e:
            raise ConfigurationError(f"Failed to create backup of {file_path}: {e}")
    
    def safe_write_file(self, file_path: Path, content: str, create_backup: bool = True) -> Optional[Path]:
        """Safely write content to a file with optional backup.
        
        Args:
            file_path: Path to the file to write
            content: Content to write to the file
            create_backup: Whether to create a backup before writing
            
        Returns:
            Path to backup file if created, None otherwise
            
        Raises:
            ConfigurationError: If file writing fails
        """
        backup_path = None
        
        try:
            # Create backup if file exists and backup is requested
            if file_path.exists() and create_backup:
                backup_path = self.create_backup(file_path)
            
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first for atomic operation
            temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
            
            try:
                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # Atomic move to final location
                temp_path.replace(file_path)
                
            except Exception as e:
                # Clean up temporary file if it exists
                if temp_path.exists():
                    temp_path.unlink()
                raise e
            
            # Verify file was written successfully
            if not file_path.exists():
                raise ConfigurationError(f"File was not created: {file_path}")
            
            return backup_path
            
        except (OSError, IOError) as e:
            # If backup was created but write failed, we should note this
            error_msg = f"Failed to write file {file_path}: {e}"
            if backup_path:
                error_msg += f" (backup created at {backup_path})"
            raise ConfigurationError(error_msg)
    
    def restore_from_backup(self, backup_path: Path, target_path: Path) -> None:
        """Restore a file from backup.
        
        Args:
            backup_path: Path to the backup file
            target_path: Path where the file should be restored
            
        Raises:
            ConfigurationError: If restoration fails
        """
        if not backup_path.exists():
            raise ConfigurationError(f"Backup file does not exist: {backup_path}")
        
        try:
            # Ensure target directory exists
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy backup to target location
            shutil.copy2(backup_path, target_path)
            
            # Verify restoration was successful
            if not target_path.exists():
                raise ConfigurationError(f"File was not restored: {target_path}")
                
        except (OSError, IOError) as e:
            raise ConfigurationError(f"Failed to restore from backup {backup_path}: {e}")
    
    def cleanup_old_backups(self, days_to_keep: int = 30) -> int:
        """Clean up old backup files.
        
        Args:
            days_to_keep: Number of days to keep backups
            
        Returns:
            Number of backup files removed
        """
        if not self.backup_dir.exists():
            return 0
        
        cutoff_time = datetime.now().timestamp() - (days_to_keep * 24 * 60 * 60)
        removed_count = 0
        
        try:
            for backup_file in self.backup_dir.glob("*.backup"):
                if backup_file.stat().st_mtime < cutoff_time:
                    backup_file.unlink()
                    removed_count += 1
        except (OSError, IOError):
            # Continue cleanup even if some files fail
            pass
        
        return removed_count
    
    def get_backup_info(self, file_path: Path) -> list:
        """Get information about available backups for a file.
        
        Args:
            file_path: Path to the original file
            
        Returns:
            List of backup information dictionaries
        """
        backups = []
        pattern = f"{file_path.name}.*.backup"
        
        for backup_file in self.backup_dir.glob(pattern):
            try:
                stat = backup_file.stat()
                backups.append({
                    'path': backup_file,
                    'created': datetime.fromtimestamp(stat.st_mtime),
                    'size': stat.st_size
                })
            except (OSError, IOError):
                continue
        
        # Sort by creation time, newest first
        backups.sort(key=lambda x: x['created'], reverse=True)
        return backups
    
    def validate_file_permissions(self, file_path: Path) -> bool:
        """Validate that we have necessary permissions for file operations.
        
        Args:
            file_path: Path to check permissions for
            
        Returns:
            True if we have necessary permissions
        """
        try:
            # Check if file exists and is readable/writable
            if file_path.exists():
                return os.access(file_path, os.R_OK | os.W_OK)
            
            # Check if parent directory is writable (for new files)
            parent = file_path.parent
            return parent.exists() and os.access(parent, os.W_OK)
            
        except (OSError, IOError):
            return False