"""User interface utilities for interactive configuration changes."""

import sys
from pathlib import Path

from ..models.config import ConfigChange, Conflict, ConflictResolution
from .diff import DiffGenerator


class UserApprovalInterface:
    """Handles user interaction for approving configuration changes."""

    def __init__(self):
        """Initialize user approval interface."""
        self.diff_generator = DiffGenerator()

    def get_change_approval(self, change: ConfigChange) -> bool:
        """Get user approval for a single configuration change.

        Args:
            change: Configuration change to approve

        Returns:
            True if user approves the change
        """
        print(f"\n{'='*60}")
        print(f"Configuration Change: {change.file_path}")
        print(f"{'='*60}")
        print(f"Description: {change.description}")
        print(f"Change Type: {change.change_type.value.title()}")

        if change.has_conflicts():
            print(f"⚠️  This change has {len(change.conflicts)} unresolved conflicts")
            return False

        # Show diff
        if change.old_content is not None:
            print("\nChanges to be made:")
            diff = self.diff_generator.generate_unified_diff(change.old_content, change.new_content, change.file_path)

            # Highlight the diff for better readability
            highlighted_diff = self.diff_generator.highlight_changes(diff)
            formatted_diff = self.diff_generator.format_diff_for_display(highlighted_diff)
            print(formatted_diff)

            # Show statistics
            stats = self.diff_generator.get_diff_stats(change.old_content, change.new_content)
            print("\nChange Statistics:")
            print(f"  Lines added: {stats['additions']}")
            print(f"  Lines removed: {stats['deletions']}")
            print(f"  Lines modified: {stats['modifications']}")
            print(f"  Similarity: {stats['similarity_ratio']:.1%}")
        else:
            # New file
            lines = change.new_content.splitlines()
            print(f"\nNew file will be created with {len(lines)} lines:")

            # Show preview of content
            preview_lines = lines[:15]  # Show first 15 lines
            for i, line in enumerate(preview_lines, 1):
                print(f"{i:3}: {line}")

            if len(lines) > 15:
                print(f"... ({len(lines) - 15} more lines)")

        # Get user decision
        while True:
            response = input("\nApprove this change? [y]es/[n]o/[s]how full content/[q]uit: ").lower().strip()

            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            elif response in ["s", "show"]:
                self._show_full_content(change)
            elif response in ["q", "quit"]:
                print("Aborting configuration changes.")
                sys.exit(0)
            else:
                print("Please enter 'y', 'n', 's', or 'q'.")

    def get_batch_approval(self, changes: list[ConfigChange]) -> dict[Path, bool]:
        """Get user approval for multiple configuration changes.

        Args:
            changes: List of configuration changes to approve

        Returns:
            Dictionary mapping file paths to approval status
        """
        approvals = {}

        print(f"\n{'='*60}")
        print("Configuration Changes Summary")
        print(f"{'='*60}")
        print(f"Total changes: {len(changes)}")

        # Show summary of all changes
        for i, change in enumerate(changes, 1):
            status = "⚠️ HAS CONFLICTS" if change.has_conflicts() else "✓ Ready"
            print(f"{i:2}. {change.file_path} ({change.change_type.value}) - {status}")

        print(f"\n{'='*60}")

        # Ask for batch decision
        while True:
            response = input("Approve all changes? [y]es/[n]o/[r]eview individually/[q]uit: ").lower().strip()

            if response in ["y", "yes"]:
                # Approve all changes that don't have conflicts
                for change in changes:
                    approvals[change.file_path] = not change.has_conflicts()
                break
            elif response in ["n", "no"]:
                # Reject all changes
                for change in changes:
                    approvals[change.file_path] = False
                break
            elif response in ["r", "review"]:
                # Review each change individually
                for change in changes:
                    approvals[change.file_path] = self.get_change_approval(change)
                break
            elif response in ["q", "quit"]:
                print("Aborting configuration changes.")
                sys.exit(0)
            else:
                print("Please enter 'y', 'n', 'r', or 'q'.")

        return approvals

    def resolve_conflicts_interactively(self, conflicts: list[Conflict]) -> list[Conflict]:
        """Resolve conflicts through user interaction.

        Args:
            conflicts: List of conflicts to resolve

        Returns:
            List of resolved conflicts
        """
        print(f"\n{'='*60}")
        print(f"Configuration Conflicts ({len(conflicts)} found)")
        print(f"{'='*60}")

        resolved_conflicts = []

        for i, conflict in enumerate(conflicts, 1):
            print(f"\nConflict {i}/{len(conflicts)}:")
            print(f"File: {conflict.file_path}")
            print(f"Section: {conflict.section}")
            print(f"Description: {conflict.description}")

            print("\nExisting value:")
            print(f"  {conflict.existing_value}")
            print("Template value:")
            print(f"  {conflict.template_value}")

            # Show diff
            diff = self.diff_generator.generate_conflict_diff(
                str(conflict.existing_value), str(conflict.template_value), conflict.section,
            )

            if diff.strip():
                print("\nDifference:")
                highlighted_diff = self.diff_generator.highlight_changes(diff)
                print(highlighted_diff)

            # Get user choice
            while True:
                choice = input("\nResolve conflict: [k]eep existing/[u]se template/[m]anual/[s]kip: ").lower().strip()

                if choice in ["k", "keep"]:
                    conflict.resolution = ConflictResolution.KEEP_EXISTING
                    print("✓ Keeping existing value")
                    break
                elif choice in ["u", "use"]:
                    conflict.resolution = ConflictResolution.USE_TEMPLATE
                    print("✓ Using template value")
                    break
                elif choice in ["m", "manual"]:
                    conflict.resolution = ConflictResolution.MANUAL
                    print("⚠️  Manual resolution required")
                    break
                elif choice in ["s", "skip"]:
                    print("⏭️  Skipping conflict (will keep existing)")
                    conflict.resolution = ConflictResolution.KEEP_EXISTING
                    break
                else:
                    print("Please enter 'k', 'u', 'm', or 's'.")

            resolved_conflicts.append(conflict)

        return resolved_conflicts

    def _show_full_content(self, change: ConfigChange) -> None:
        """Show full content of a configuration change."""
        print(f"\n{'='*60}")
        print(f"Full Content: {change.file_path}")
        print(f"{'='*60}")

        if change.old_content is not None:
            print("=== ORIGINAL CONTENT ===")
            print(change.old_content)
            print("\n=== NEW CONTENT ===")
        else:
            print("=== NEW FILE CONTENT ===")

        print(change.new_content)
        print(f"{'='*60}")

    def show_apply_summary(
        self,
        approved_changes: list[ConfigChange],
        rejected_changes: list[ConfigChange],
        conflicted_changes: list[ConfigChange],
    ) -> None:
        """Show summary of what will be applied.

        Args:
            approved_changes: Changes that were approved
            rejected_changes: Changes that were rejected
            conflicted_changes: Changes with unresolved conflicts
        """
        print(f"\n{'='*60}")
        print("Application Summary")
        print(f"{'='*60}")

        if approved_changes:
            print(f"✅ Changes to be applied ({len(approved_changes)}):")
            for change in approved_changes:
                backup_note = " (with backup)" if change.needs_backup() else ""
                print(f"  • {change.file_path} ({change.change_type.value}){backup_note}")

        if rejected_changes:
            print(f"\n❌ Changes rejected ({len(rejected_changes)}):")
            for change in rejected_changes:
                print(f"  • {change.file_path} ({change.change_type.value})")

        if conflicted_changes:
            print(f"\n⚠️  Changes with unresolved conflicts ({len(conflicted_changes)}):")
            for change in conflicted_changes:
                print(f"  • {change.file_path} ({len(change.conflicts)} conflicts)")

        print(f"{'='*60}")

    def confirm_final_application(self, approved_changes: list[ConfigChange]) -> bool:
        """Get final confirmation before applying changes.

        Args:
            approved_changes: Changes that will be applied

        Returns:
            True if user confirms application
        """
        if not approved_changes:
            print("No changes to apply.")
            return False

        print(f"\nReady to apply {len(approved_changes)} configuration changes.")

        # Show backup information
        backup_changes = [c for c in approved_changes if c.needs_backup()]
        if backup_changes:
            print(f"Backups will be created for {len(backup_changes)} files.")

        while True:
            response = input("Proceed with applying changes? [y]es/[n]o: ").lower().strip()

            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            else:
                print("Please enter 'y' or 'n'.")

    def show_dry_run_results(self, changes: list[ConfigChange]) -> None:
        """Show results of a dry run.

        Args:
            changes: Changes that would be applied
        """
        print(f"\n{'='*60}")
        print("Dry Run Results")
        print(f"{'='*60}")

        if not changes:
            print("No changes would be applied.")
            return

        print(f"The following {len(changes)} changes would be applied:")

        for change in changes:
            print(f"\n📁 {change.file_path}")
            print(f"   Type: {change.change_type.value.title()}")
            print(f"   Description: {change.description}")

            if change.needs_backup():
                print("   Backup: Yes")

            if change.has_conflicts():
                print(f"   ⚠️  Conflicts: {len(change.conflicts)}")

            # Show brief diff
            if change.old_content is not None:
                stats = self.diff_generator.get_diff_stats(change.old_content, change.new_content)
                print(f"   Changes: +{stats['additions']} -{stats['deletions']} lines")
            else:
                lines = len(change.new_content.splitlines())
                print(f"   New file: {lines} lines")

        print(f"\n{'='*60}")
        print("This was a dry run - no files were modified.")
