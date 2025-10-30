"""Diff generation utilities for displaying configuration changes."""

import difflib
from pathlib import Path
from typing import List, Optional, Tuple

from ..models.config import ConfigChange


class DiffGenerator:
    """Generates and formats diffs for configuration changes."""
    
    def __init__(self, context_lines: int = 3):
        """Initialize diff generator with context lines."""
        self.context_lines = context_lines
    
    def generate_unified_diff(
        self,
        old_content: str,
        new_content: str,
        file_path: Path,
        old_label: Optional[str] = None,
        new_label: Optional[str] = None
    ) -> str:
        """Generate unified diff between old and new content.
        
        Args:
            old_content: Original file content
            new_content: New file content
            file_path: Path to the file being changed
            old_label: Label for old content (defaults to file path)
            new_label: Label for new content (defaults to file path)
            
        Returns:
            Unified diff as string
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        
        if old_label is None:
            old_label = f"a/{file_path.name}"
        if new_label is None:
            new_label = f"b/{file_path.name}"
        
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=old_label,
            tofile=new_label,
            n=self.context_lines,
            lineterm=''
        )
        
        return ''.join(diff)
    
    def generate_side_by_side_diff(
        self,
        old_content: str,
        new_content: str,
        width: int = 80
    ) -> str:
        """Generate side-by-side diff between old and new content.
        
        Args:
            old_content: Original file content
            new_content: New file content
            width: Total width for the diff display
            
        Returns:
            Side-by-side diff as string
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        # Use difflib's HtmlDiff for side-by-side comparison
        # but extract just the text content
        differ = difflib.HtmlDiff(wrapcolumn=width//2)
        html_diff = differ.make_table(
            old_lines,
            new_lines,
            fromdesc="Original",
            todesc="Modified",
            context=True,
            numlines=self.context_lines
        )
        
        # For now, return unified diff as side-by-side is complex in text
        return self.generate_unified_diff(old_content, new_content, Path("file"))
    
    def generate_change_summary(self, change: ConfigChange) -> str:
        """Generate a summary of a configuration change.
        
        Args:
            change: Configuration change to summarize
            
        Returns:
            Summary string
        """
        summary_lines = []
        
        # Header with file and change type
        summary_lines.append(f"File: {change.file_path}")
        summary_lines.append(f"Change Type: {change.change_type.value.title()}")
        summary_lines.append(f"Description: {change.description}")
        
        if change.has_conflicts():
            summary_lines.append(f"Conflicts: {len(change.conflicts)}")
        
        # Add diff if we have old content
        if change.old_content is not None:
            summary_lines.append("")
            summary_lines.append("Changes:")
            diff = self.generate_unified_diff(
                change.old_content,
                change.new_content,
                change.file_path
            )
            summary_lines.append(diff)
        else:
            # For new files, show first few lines
            lines = change.new_content.splitlines()
            preview_lines = lines[:10]  # Show first 10 lines
            
            summary_lines.append("")
            summary_lines.append("New file content (preview):")
            for i, line in enumerate(preview_lines, 1):
                summary_lines.append(f"{i:3}: {line}")
            
            if len(lines) > 10:
                summary_lines.append(f"... ({len(lines) - 10} more lines)")
        
        return "\n".join(summary_lines)
    
    def generate_conflict_diff(
        self,
        existing_value: str,
        template_value: str,
        section: str
    ) -> str:
        """Generate diff for a configuration conflict.
        
        Args:
            existing_value: Current configuration value
            template_value: Template configuration value
            section: Configuration section name
            
        Returns:
            Conflict diff as string
        """
        # Convert values to strings if they aren't already
        existing_str = str(existing_value) if not isinstance(existing_value, str) else existing_value
        template_str = str(template_value) if not isinstance(template_value, str) else template_value
        
        diff = self.generate_unified_diff(
            existing_str,
            template_str,
            Path(f"[{section}]"),
            old_label=f"existing [{section}]",
            new_label=f"template [{section}]"
        )
        
        return diff
    
    def get_diff_stats(self, old_content: str, new_content: str) -> dict:
        """Get statistics about the differences between two contents.
        
        Args:
            old_content: Original content
            new_content: New content
            
        Returns:
            Dictionary with diff statistics
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        # Use SequenceMatcher to get detailed statistics
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        
        # Count different types of changes
        additions = 0
        deletions = 0
        modifications = 0
        
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'insert':
                additions += j2 - j1
            elif tag == 'delete':
                deletions += i2 - i1
            elif tag == 'replace':
                modifications += max(i2 - i1, j2 - j1)
        
        return {
            'total_old_lines': len(old_lines),
            'total_new_lines': len(new_lines),
            'additions': additions,
            'deletions': deletions,
            'modifications': modifications,
            'similarity_ratio': matcher.ratio()
        }
    
    def format_diff_for_display(self, diff: str, max_width: int = 120) -> str:
        """Format diff for terminal display with proper wrapping.
        
        Args:
            diff: Raw diff content
            max_width: Maximum line width for display
            
        Returns:
            Formatted diff string
        """
        lines = diff.splitlines()
        formatted_lines = []
        
        for line in lines:
            if len(line) <= max_width:
                formatted_lines.append(line)
            else:
                # Wrap long lines, preserving diff prefixes
                prefix = ""
                content = line
                
                if line.startswith(('+++', '---', '@@')):
                    # Don't wrap header lines, just truncate
                    formatted_lines.append(line[:max_width] + "...")
                    continue
                elif line.startswith(('+', '-', ' ')):
                    prefix = line[0]
                    content = line[1:]
                
                # Wrap content
                while content:
                    chunk_size = max_width - len(prefix)
                    chunk = content[:chunk_size]
                    formatted_lines.append(prefix + chunk)
                    content = content[chunk_size:]
                    if content:
                        prefix = " "  # Continuation lines use space prefix
        
        return "\n".join(formatted_lines)
    
    def highlight_changes(self, diff: str) -> str:
        """Add basic highlighting to diff output.
        
        Args:
            diff: Raw diff content
            
        Returns:
            Diff with basic ANSI color codes
        """
        lines = diff.splitlines()
        highlighted_lines = []
        
        # ANSI color codes
        RED = '\033[31m'
        GREEN = '\033[32m'
        CYAN = '\033[36m'
        RESET = '\033[0m'
        
        for line in lines:
            if line.startswith('+++') or line.startswith('---'):
                highlighted_lines.append(f"{CYAN}{line}{RESET}")
            elif line.startswith('@@'):
                highlighted_lines.append(f"{CYAN}{line}{RESET}")
            elif line.startswith('+'):
                highlighted_lines.append(f"{GREEN}{line}{RESET}")
            elif line.startswith('-'):
                highlighted_lines.append(f"{RED}{line}{RESET}")
            else:
                highlighted_lines.append(line)
        
        return "\n".join(highlighted_lines)