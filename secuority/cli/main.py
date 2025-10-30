"""Main CLI entry point for Secuority."""

from pathlib import Path
from typing import Optional

from ..core.engine import CoreEngine
from ..models.interfaces import CLIInterface


class SecuorityCLI(CLIInterface):
    """Main CLI interface for Secuority."""

    def __init__(self, core_engine: Optional[CoreEngine] = None):
        """Initialize CLI with core engine."""
        self.core_engine = core_engine or CoreEngine()

    def check(self, project_path: Path, verbose: bool = False) -> None:
        """Execute the check command to analyze project configuration."""
        try:
            project_state = self.core_engine.analyze_project(project_path)
            self._display_analysis_results(project_state, verbose)
        except Exception as e:
            self._handle_error(f"Failed to analyze project: {e}")

    def apply(
        self, project_path: Path, dry_run: bool = False, force: bool = False
    ) -> None:
        """Execute the apply command to apply configuration changes."""
        try:
            if not dry_run and not force:
                if not self._confirm_apply():
                    return

            result = self.core_engine.apply_configurations(project_path, dry_run)
            self._display_apply_results(result, dry_run)
        except Exception as e:
            self._handle_error(f"Failed to apply configurations: {e}")

    def template_list(self) -> None:
        """List available templates."""
        try:
            templates = self.core_engine.template_manager.load_templates()
            self._display_templates(templates)
        except Exception as e:
            self._handle_error(f"Failed to list templates: {e}")

    def template_update(self) -> None:
        """Update templates from remote source."""
        try:
            self.core_engine.update_templates()
        except Exception as e:
            self._handle_error(f"Failed to update templates: {e}")

    def init(self) -> None:
        """Initialize Secuority configuration."""
        try:
            self.core_engine.initialize_templates()
        except Exception as e:
            self._handle_error(f"Failed to initialize Secuority: {e}")

    def _display_analysis_results(self, project_state: object, verbose: bool) -> None:
        """Display project analysis results."""
        # Implementation will be completed in later tasks
        pass

    def _display_apply_results(self, result: object, dry_run: bool) -> None:
        """Display configuration apply results."""
        # Implementation will be completed in later tasks
        pass

    def _display_templates(self, templates: dict) -> None:
        """Display available templates."""
        # Implementation will be completed in later tasks
        pass

    def _confirm_apply(self) -> bool:
        """Prompt user for confirmation before applying changes."""
        response = (
            input("Apply configuration changes? [y/N]: ").strip().lower()
        )
        return response in ("y", "yes")

    def _handle_error(self, message: str) -> None:
        """Handle and display error messages."""
        # Implementation will be completed in later tasks
        pass


def main() -> None:
    """Main entry point for the CLI application."""
    # This will be implemented with proper argument parsing in later tasks
    pass


if __name__ == "__main__":
    main()