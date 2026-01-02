"""Main CLI entry point for Secuority."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.analyzer import ProjectAnalyzer
from ..core.applier import ConfigurationApplier
from ..core.engine import CoreEngine
from ..core.github_client import GitHubClient
from ..core.languages import LanguageAnalysisResult, get_global_registry
from ..core.template_manager import TemplateManager
from ..models.config import ConfigChange
from ..models.exceptions import ConfigurationError, ProjectAnalysisError, TemplateError
from ..models.interfaces import GitHubAnalysisResult, ProjectState
from ..utils.logger import configure_logging, get_logger

console = Console()

app = typer.Typer(
    name="secuority",
    help="Automate and standardize Python project security and quality configurations.",
    add_completion=False,
)


def _get_core_engine() -> CoreEngine:
    """Get a configured core engine instance."""
    analyzer = ProjectAnalyzer()
    template_manager = TemplateManager()
    applier = ConfigurationApplier()
    github_client = GitHubClient()

    return CoreEngine(
        analyzer=analyzer,
        template_manager=template_manager,
        applier=applier,
        github_client=github_client if github_client.is_authenticated() else None,
    )


@app.command()
def check(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed analysis information"),
    project_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--project-path",
        "-p",
        help="Path to the project directory",
    ),
    structured_output: bool = typer.Option(False, "--structured", help="Output structured JSON logs"),
    language: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--language",
        "-l",
        help="Specific language(s) to analyze (auto-detect if not specified)",
    ),
) -> None:
    """Analyze project configuration and show recommendations."""
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    project_path = _resolve_project_path(project_path)
    requested_languages = list(language) if language else []
    detected_languages = _determine_target_languages(project_path, language)

    try:
        logger.info("Starting project analysis", project_path=str(project_path))
        logger.debug("Analysis configuration", verbose=verbose, structured_output=structured_output)
        logger.info("Detected languages", languages=detected_languages)

        core_engine = _get_core_engine()
        project_state = core_engine.analyze_project(project_path)
        language_results, detected_languages = _resolve_cli_languages(
            project_state=project_state,
            project_path=project_path,
            requested_languages=requested_languages,
            detected_languages=detected_languages,
            logger=logger,
        )
        python_project = _is_python_project(project_state, language_results)
        config_files_info = _build_config_file_info(project_state, python_project)

        if not structured_output:
            _render_analysis_header(project_path, detected_languages)
            _render_language_summary(language_results)
            _render_config_table(config_files_info)

        _log_config_file_info(logger, project_path, config_files_info)
        _log_language_summary(logger, project_path, language_results)

        if not structured_output:
            _render_dependency_manager(project_state)
            _render_current_tools(project_state)
            if python_project:
                _render_security_tools(project_state)
                _render_quality_tools(project_state)
            _render_workflows(project_state)

        github_analysis = _perform_github_analysis(core_engine, project_path, logger)

        if not structured_output:
            _render_github_section(github_analysis)

        recommendations = _build_recommendations(project_state, github_analysis, python_project)
        _log_recommendations(logger, recommendations)

        python_files_count = _log_project_statistics(logger, project_path)

        if not structured_output:
            _render_recommendation_panel(recommendations)
            if verbose:
                _render_verbose_details(
                    project_path=project_path,
                    project_state=project_state,
                    github_analysis=github_analysis,
                    python_files_count=python_files_count,
                    core_engine=core_engine,
                )

        logger.info(
            "Analysis completed successfully",
            recommendations_count=len(recommendations),
            python_files=python_files_count,
        )

    except ProjectAnalysisError as e:
        logger.exception("Project analysis failed", error=str(e), project_path=str(project_path))
        if not structured_output:
            console.print(f"[red]Error:[/red] Failed to analyze project: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        logger.exception("Unexpected error during analysis", error=str(e), project_path=str(project_path))
        if not structured_output:
            console.print(f"[red]Error:[/red] Unexpected error: {e}")
        raise typer.Exit(1) from e


@app.command()
def apply(
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show changes without applying them"),
    force: bool = typer.Option(False, "--force", "-f", help="Apply changes without confirmation"),
    project_path: Path | None = typer.Option(  # noqa: B008
        None,
        "--project-path",
        "-p",
        help="Path to the project directory",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    structured_output: bool = typer.Option(False, "--structured", help="Output structured JSON logs"),
    security_only: bool = typer.Option(False, "--security-only", help="Apply only security-related configurations"),
    templates_only: bool = typer.Option(False, "--templates-only", help="Apply only template-based configurations"),
    language: list[str] | None = typer.Option(  # noqa: B008
        None,
        "--language",
        "-l",
        help="Specific language(s) to apply templates for (auto-detect if not specified)",
    ),
) -> None:
    """Apply configuration changes to the project."""
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    project_path = _resolve_project_path(project_path)
    requested_languages = list(language) if language else []
    detected_languages = _determine_target_languages(project_path, language)

    try:
        logger.info("Starting configuration application", project_path=str(project_path), dry_run=dry_run, force=force)
        logger.info("Target languages for template application", languages=detected_languages)

        if not structured_output:
            _render_apply_intro(project_path, detected_languages, dry_run, force)

        core_engine = _get_core_engine()
        project_state = core_engine.analyze_project(project_path)
        language_results, detected_languages = _resolve_cli_languages(
            project_state=project_state,
            project_path=project_path,
            requested_languages=requested_languages,
            detected_languages=detected_languages,
            logger=logger,
        )
        _log_language_summary(logger, project_path, language_results)

        templates = _load_all_templates(
            core_engine=core_engine,
            detected_languages=detected_languages,
            project_path=project_path,
            project_state=project_state,
            structured_output=structured_output,
            logger=logger,
        )

        changes = _generate_apply_changes(
            core_engine=core_engine,
            project_state=project_state,
            project_path=project_path,
            templates=templates,
            apply_security=not templates_only,
            apply_templates=not security_only,
            logger=logger,
        )

        if not changes:
            _notify_no_changes(structured_output, logger, project_path)
            return

        if not structured_output:
            _render_planned_changes(changes)

        if not _confirm_apply_execution(changes, dry_run, force, structured_output, logger):
            return

        resolved_changes = _apply_conflict_resolution(
            changes=changes,
            dry_run=dry_run,
            force=force,
            structured_output=structured_output,
            logger=logger,
        )
        if not resolved_changes:
            return

        result = _execute_apply_changes(
            core_engine=core_engine,
            changes=resolved_changes,
            dry_run=dry_run,
            structured_output=structured_output,
            force=force,
        )

        _log_apply_result(logger, result)

        if not structured_output:
            _render_apply_results_console(
                result=result,
                dry_run=dry_run,
                verbose=verbose,
                changes=resolved_changes,
            )

        logger.log_operation(
            operation="configuration_apply",
            status="completed" if not dry_run else "dry_run_completed",
            details={
                "changes_count": len(resolved_changes),
                "successful_changes": len(result.successful_changes),
                "failed_changes": len(result.failed_changes),
                "conflicts": len(result.conflicts),
                "dry_run": dry_run,
                "force": force,
            },
        )

    except (ProjectAnalysisError, ConfigurationError) as e:
        logger.exception("Configuration application failed", error=str(e), project_path=str(project_path))
        if not structured_output:
            console.print(f"[red]Error:[/red] Failed to apply configurations: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        logger.exception(
            "Unexpected error during configuration application",
            error=str(e),
            project_path=str(project_path),
        )
        if not structured_output:
            console.print(f"[red]Error:[/red] Unexpected error: {e}")
        raise typer.Exit(1) from e


def _render_apply_intro(project_path: Path, detected_languages: list[str], dry_run: bool, force: bool) -> None:
    """Render the introductory banner for the apply command."""
    if dry_run:
        console.print("\n[bold blue]Dry Run - Configuration Changes Preview[/bold blue]\n")
    else:
        console.print("\n[bold green]Applying Configuration Changes[/bold green]\n")

    console.print(f"[dim]Project: {project_path}[/dim]")
    console.print(f"[dim]Languages: {', '.join(detected_languages)}[/dim]")
    console.print(f"[dim]Dry run: {dry_run}, Force: {force}[/dim]\n")


def _load_all_templates(
    core_engine: CoreEngine,
    detected_languages: list[str],
    project_path: Path,
    project_state: Any,
    structured_output: bool,
    logger: Any,
) -> dict[str, str]:
    """Load templates for all detected languages, handling warnings gracefully."""
    templates: dict[str, str] = {}
    try:
        for lang in detected_languages:
            try:
                variant = core_engine.template_manager.select_variant(
                    language=lang,
                    project_path=project_path,
                    project_state=project_state,
                )
                lang_templates = core_engine.template_manager.load_templates(language=lang, variant=variant)
                if len(detected_languages) > 1:
                    templates.update({f"{lang}:{k}": v for k, v in lang_templates.items()})
                else:
                    templates.update(lang_templates)
                logger.debug("Loaded language templates", language=lang, variant=variant, count=len(lang_templates))
            except TemplateError as exc:
                logger.warning("Could not load templates for language", language=lang, error=str(exc))
    except Exception as exc:
        if not structured_output:
            console.print(f"[yellow]Warning:[/yellow] Could not load templates: {exc}")
            console.print("[dim]Run 'secuority init' to initialize templates.[/dim]")
        logger.warning("Templates not available", error=str(exc))

    return templates


def _generate_apply_changes(
    *,
    core_engine: CoreEngine,
    project_state: Any,
    project_path: Path,
    templates: dict[str, str],
    apply_security: bool,
    apply_templates: bool,
    logger: Any,
) -> list[ConfigChange]:
    """Generate the list of changes to apply based on analysis."""
    changes: list[ConfigChange] = []

    if apply_templates:
        changes.extend(
            _generate_template_file_changes(
                core_engine=core_engine,
                project_state=project_state,
                project_path=project_path,
                templates=templates,
                logger=logger,
            ),
        )
        changes.extend(
            _generate_quality_integration_changes(
                core_engine=core_engine,
                project_state=project_state,
                project_path=project_path,
                logger=logger,
            ),
        )
        changes.extend(
            _generate_dependency_and_workflow_changes(
                core_engine=core_engine,
                project_state=project_state,
                project_path=project_path,
                logger=logger,
            ),
        )

    if apply_security:
        changes.extend(
            _generate_security_integration_changes(
                core_engine=core_engine,
                project_state=project_state,
                project_path=project_path,
                logger=logger,
            ),
        )

    return changes


def _generate_template_file_changes(
    *,
    core_engine: CoreEngine,
    project_state: Any,
    project_path: Path,
    templates: dict[str, str],
    logger: Any,
) -> list[ConfigChange]:
    """Generate template file changes for all detected languages.

    Supports templates from multiple languages with language-prefixed keys
    (e.g., 'python:pyproject.toml.template') or unprefixed keys.
    """
    cpp_profile = core_engine.template_manager.select_cpp_clang_tidy_profile(project_path)
    # Define template mappings for each language
    # Format: template_name -> (target_file, project_state_attribute)
    language_template_maps: dict[str, dict[str, tuple[str, str]]] = {
        "python": {
            "pyproject.toml.template": ("pyproject.toml", "has_pyproject_toml"),
            ".pre-commit-config.yaml.template": (".pre-commit-config.yaml", "has_pre_commit_config"),
        },
        "nodejs": {
            "biome.json.template": ("biome.json", "has_biome_config"),
            "tsconfig.json.template": ("tsconfig.json", "has_tsconfig"),
        },
        "rust": {
            "Cargo.toml.template": ("Cargo.toml", "has_cargo_toml"),
            "rustfmt.toml": ("rustfmt.toml", "has_rustfmt"),
            "deny.toml": ("deny.toml", "has_cargo_deny"),
        },
        "go": {
            ".golangci.yml": (".golangci.yml", "has_golangci"),
        },
        "cpp": {
            ".clang-format": (".clang-format", "has_clang_format"),
            ".clang-tidy": (".clang-tidy", "has_clang_tidy"),
            "CMakeLists.txt.template": ("CMakeLists.txt", "has_cmake"),
        },
        "csharp": {
            ".editorconfig": (".editorconfig", "has_editorconfig"),
            "Directory.Build.props": ("Directory.Build.props", "has_directory_build_props"),
            "Directory.Packages.props.template": ("Directory.Packages.props", "has_directory_packages_props"),
        },
        "common": {
            ".gitignore.template": (".gitignore", "has_gitignore"),
            "SECURITY.md.template": ("SECURITY.md", "has_security_md"),
            "CONTRIBUTING.md": ("CONTRIBUTING.md", "has_contributing"),
        },
    }

    template_changes: list[ConfigChange] = []

    for language, template_map in language_template_maps.items():
        for template_name, (target, state_attr) in template_map.items():
            # Check if file already exists
            already_exists = getattr(project_state, state_attr, False) or (project_path / target).exists()
            if already_exists:
                continue

            # Try to find template (with or without language prefix)
            template_content = None
            key_variants = [f"{language}:{template_name}", template_name]
            if language == "cpp" and template_name == ".clang-tidy" and cpp_profile:
                profile_key = f"clang-tidy/{cpp_profile}/.clang-tidy"
                key_variants = [f"{language}:{profile_key}", profile_key, *key_variants]
            for key_variant in key_variants:
                if key_variant in templates:
                    template_content = templates[key_variant]
                    break

            if template_content is None:
                continue

            try:
                change = core_engine.applier.merge_file_configurations(
                    project_path / target,
                    template_content,
                )
                template_changes.append(change)
                logger.debug("Added template change", template=template_name, target=target, language=language)
            except Exception as exc:
                logger.warning(
                    "Failed to generate template change",
                    template=template_name,
                    language=language,
                    error=str(exc),
                )

    return template_changes


def _generate_security_integration_changes(
    *,
    core_engine: CoreEngine,
    project_state: Any,
    project_path: Path,
    logger: Any,
) -> list[ConfigChange]:
    if not project_state.security_tools:
        return []

    missing_security = [tool.value for tool, configured in project_state.security_tools.items() if not configured]
    if not missing_security:
        return []

    try:
        changes = core_engine.applier.get_security_integration_changes(project_path, missing_security)
        logger.debug("Added security integration changes", count=len(changes))
        return changes
    except Exception as exc:
        logger.warning("Failed to generate security integration changes", error=str(exc))
    return []


def _generate_quality_integration_changes(
    *,
    core_engine: CoreEngine,
    project_state: Any,
    project_path: Path,
    logger: Any,
) -> list[ConfigChange]:
    if not project_state.quality_tools:
        return []

    missing_quality = [tool.value for tool, configured in project_state.quality_tools.items() if not configured]
    if not missing_quality:
        return []

    try:
        changes = core_engine.applier.get_quality_integration_changes(project_path, missing_quality)
        logger.debug("Added quality integration changes", count=len(changes))
        return changes
    except Exception as exc:
        logger.warning("Failed to generate quality integration changes", error=str(exc))
    return []


def _generate_dependency_and_workflow_changes(
    *,
    core_engine: CoreEngine,
    project_state: Any,
    project_path: Path,
    logger: Any,
) -> list[ConfigChange]:
    changes: list[ConfigChange] = []

    dep_analysis = project_state.dependency_analysis
    if dep_analysis and getattr(dep_analysis, "migration_needed", False):
        try:
            migration_change = core_engine.applier.get_dependency_migration_change(project_path, dep_analysis)
            if migration_change:
                changes.append(migration_change)
                logger.debug("Added dependency migration change")
        except Exception as exc:
            logger.warning("Failed to generate dependency migration change", error=str(exc))

    try:
        workflow_changes = core_engine.applier.get_workflow_integration_changes(
            project_path,
            ["security", "quality", "cicd", "dependency"],
        )
        changes.extend(workflow_changes)
        logger.debug("Added workflow integration changes", count=len(workflow_changes))
    except Exception as exc:
        logger.warning("Failed to generate workflow changes", error=str(exc))

    return changes


def _notify_no_changes(structured_output: bool, logger: Any, project_path: Path) -> None:
    if not structured_output:
        console.print("[green]✓ No configuration changes needed![/green]")
        console.print("[dim]Project configuration is already up to date.[/dim]")
    logger.info("No configuration changes needed", project_path=str(project_path))


def _render_planned_changes(changes: list[ConfigChange]) -> None:
    changes_table = Table(title="Planned Changes", show_header=True, header_style="bold green")
    changes_table.add_column("File", style="cyan")
    changes_table.add_column("Action", justify="center")
    changes_table.add_column("Description", style="dim")

    for change in changes:
        action_color = {
            "CREATE": "[green]CREATE[/green]",
            "UPDATE": "[yellow]UPDATE[/yellow]",
            "MERGE": "[blue]MERGE[/blue]",
        }.get(change.change_type.value, f"[white]{change.change_type.value}[/white]")
        changes_table.add_row(change.file_path.name, action_color, change.description)

    console.print(changes_table)
    console.print()


def _confirm_apply_execution(
    changes: list[ConfigChange],
    dry_run: bool,
    force: bool,
    structured_output: bool,
    logger: Any,
) -> bool:
    if dry_run or force:
        return True

    if structured_output:
        logger.error("Interactive confirmation required - use --force flag for non-interactive operation")
        raise typer.Exit(1) from None

    console.print("[bold yellow]⚠️  This will modify your project files![/bold yellow]")
    console.print("[dim]Backups will be created for existing files.[/dim]")

    file_changes: dict[str, list[str]] = {}
    for change in changes:
        action = change.change_type.value
        file_changes.setdefault(action, []).append(change.file_path.name)

    console.print("\n[bold]Summary of changes:[/bold]")
    for action, files in file_changes.items():
        action_color = {"CREATE": "[green]", "UPDATE": "[yellow]", "MERGE": "[blue]"}.get(action, "[white]")
        console.print(f"  {action_color}{action}[/{action_color.split('[')[1]}]: {', '.join(files)}")

    confirm = typer.confirm(f"\nApply {len(changes)} configuration changes?")
    if not confirm:
        console.print("[yellow]Operation cancelled.[/yellow]")
        logger.info("Operation cancelled by user", changes_count=len(changes))
        return False

    return True


def _apply_conflict_resolution(
    changes: list[ConfigChange],
    dry_run: bool,
    force: bool,
    structured_output: bool,
    logger: Any,
) -> list[ConfigChange]:
    """Handle conflict reporting and optionally filter conflicted changes."""
    if dry_run:
        return changes

    conflicted_changes = [c for c in changes if c.has_conflicts()]
    if not conflicted_changes:
        return changes

    total_conflicts = sum(len(c.conflicts) for c in conflicted_changes)
    if not structured_output:
        console.print(
            f"[yellow]⚠ Found {len(conflicted_changes)} changes with conflicts that need resolution[/yellow]",
        )
        for change in conflicted_changes:
            console.print(f"\n[bold]Conflicts in {change.file_path.name}:[/bold]")
            for conflict in change.conflicts:
                console.print(f"  • {conflict.description}")
                console.print(f"    [dim]Existing:[/dim] {conflict.existing_value}")
                console.print(f"    [dim]Template:[/dim] {conflict.template_value}")

        console.print("\n[bold yellow]Conflict Resolution Options:[/bold yellow]")
        console.print("  1. Use --dry-run to preview all changes")
        console.print("  2. Use --force to apply non-conflicted changes only")
        console.print("  3. Manually resolve conflicts and run apply again")

    if not force:
        if not structured_output:
            console.print(
                "\n[dim]Stopping due to conflicts. Use --force to apply non-conflicted changes.[/dim]",
            )
        logger.warning(
            "Configuration conflicts detected - stopping",
            conflicted_changes=len(conflicted_changes),
            total_conflicts=total_conflicts,
        )
        return []

    if not structured_output:
        console.print("\n[yellow]--force flag detected: applying non-conflicted changes only[/yellow]")

    filtered = [c for c in changes if not c.has_conflicts()]
    logger.info(
        "Applying non-conflicted changes only due to --force flag",
        original_changes=len(changes),
        applying_changes=len(filtered),
    )
    return filtered


def _execute_apply_changes(
    core_engine: CoreEngine,
    changes: list[ConfigChange],
    dry_run: bool,
    structured_output: bool,
    force: bool,
):
    """Execute the apply operation using the appropriate applier mode."""
    logger = get_logger()
    logger.info(
        "Applying configuration changes",
        changes_count=len(changes),
        dry_run=dry_run,
        interactive=not structured_output and not force and not dry_run,
    )

    if not structured_output and not force and not dry_run:
        return core_engine.applier.apply_changes_interactively(changes, dry_run=dry_run, batch_mode=False)

    if not structured_output and not dry_run:
        with console.status("[bold green]Applying configuration changes..."):
            return core_engine.applier.apply_changes(changes, dry_run=dry_run)

    return core_engine.applier.apply_changes(changes, dry_run=dry_run)


def _log_apply_result(logger: Any, result: Any) -> None:
    for change in result.successful_changes:
        logger.log_configuration_change(
            file_path=str(change.file_path),
            change_type=change.change_type.value.lower(),
            description=change.description,
            success=True,
        )

    for change, _error in result.failed_changes:
        logger.log_configuration_change(
            file_path=str(change.file_path),
            change_type=change.change_type.value.lower(),
            description=change.description,
            success=False,
        )


def _render_apply_results_console(
    *,
    result: Any,
    dry_run: bool,
    verbose: bool,
    changes: list[ConfigChange],
) -> None:
    console.print()
    _render_apply_success_details(result, verbose)
    _render_apply_failure_details(result)
    _render_apply_backup_info(result, verbose)
    _render_apply_conflict_info(result, verbose)
    _render_apply_summary(result, dry_run, changes)
    console.print()


def _render_apply_success_details(result: Any, verbose: bool) -> None:
    if not result.successful_changes:
        return

    console.print(f"[green]✓ Successfully applied {len(result.successful_changes)} changes[/green]")
    if verbose:
        console.print("\n[bold]Applied changes:[/bold]")
        for change in result.successful_changes:
            action_color = {"CREATE": "[green]", "UPDATE": "[yellow]", "MERGE": "[blue]"}.get(
                change.change_type.value,
                "[white]",
            )
            color_end = action_color.split("[")[1]
            console.print(
                f"  • {action_color}{change.change_type.value}[/{color_end}] "
                f"{change.file_path.name}: {change.description}",
            )
        return

    changed_files = [change.file_path.name for change in result.successful_changes]
    console.print(f"[dim]Modified files: {', '.join(changed_files)}[/dim]")


def _render_apply_failure_details(result: Any) -> None:
    if not result.failed_changes:
        return

    console.print(f"[red]✗ Failed to apply {len(result.failed_changes)} changes[/red]")
    for change, _error in result.failed_changes:
        console.print(f"  • [red]{change.file_path.name}[/red]: {_error}")


def _render_apply_backup_info(result: Any, verbose: bool) -> None:
    if not result.backups_created:
        return

    console.print(f"[dim]Created {len(result.backups_created)} backup files[/dim]")
    if verbose:
        console.print("\n[bold]Backup files:[/bold]")
        for backup_path in result.backups_created:
            console.print(f"  • {backup_path}")


def _render_apply_conflict_info(result: Any, verbose: bool) -> None:
    if not result.conflicts:
        return

    console.print(f"[yellow]⚠ {len(result.conflicts)} conflicts need manual resolution[/yellow]")
    if verbose:
        console.print("\n[bold]Unresolved conflicts:[/bold]")
        for conflict in result.conflicts:
            console.print(f"  • [yellow]{conflict.file_path}[/yellow]: {conflict.description}")


def _render_apply_summary(result: Any, dry_run: bool, changes: list[ConfigChange]) -> None:
    if dry_run:
        console.print("\n[bold]Summary:[/bold] This was a dry run - no changes were made.")
        if changes:
            console.print("[dim]Run without --dry-run to apply these changes.[/dim]")
        return

    if result.successful_changes:
        console.print("\n[bold]Summary:[/bold] Configuration changes applied successfully!")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. Review the applied changes")
        console.print("  2. Run [cyan]secuority check[/cyan] to verify the configuration")
        console.print("  3. Commit your changes to version control")

        has_precommit = any("pre-commit" in str(c.file_path) for c in result.successful_changes)
        has_pyproject = any("pyproject.toml" in str(c.file_path) for c in result.successful_changes)

        if has_precommit:
            console.print("  4. Run [cyan]pre-commit install[/cyan] to activate pre-commit hooks")
        if has_pyproject:
            console.print("  4. Install development dependencies with your package manager")
        return

    console.print("\n[bold]Summary:[/bold] No changes were applied.")


# Template subcommands
template_app = typer.Typer(name="template", help="Manage configuration templates.")
app.add_typer(template_app)


@template_app.command("list")
def template_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    structured_output: bool = typer.Option(False, "--structured", help="Output structured JSON logs"),
    language: str | None = typer.Option(
        None,
        "--language",
        "-l",
        help="Show templates for specific language (e.g., python, nodejs, rust)",
    ),
) -> None:
    """List available templates."""
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    try:
        logger.info("Listing available templates")
        core_engine = _get_core_engine()

        _display_templates_for_languages(
            core_engine=core_engine,
            language=language,
            verbose=verbose,
            structured_output=structured_output,
            logger=logger,
        )

    except TemplateError as e:
        _handle_template_list_error(e, structured_output, logger)
    except Exception as e:
        logger.exception("Failed to list templates", error=str(e))
        if not structured_output:
            console.print(f"[red]Error:[/red] Failed to list templates: {e}")
        raise typer.Exit(1) from None


def _display_templates_for_languages(
    *,
    core_engine: CoreEngine,
    language: str | None,
    verbose: bool,
    structured_output: bool,
    logger: Any,
) -> None:
    """Display templates for specified or all languages."""
    template_dir = core_engine.template_manager.get_template_directory()
    available_languages = core_engine.template_manager.get_available_languages()

    if not structured_output:
        console.print("\n[bold blue]Available Templates[/bold blue]\n")
        console.print(f"[dim]Template directory: {template_dir}[/dim]")
        console.print(f"[dim]Available languages: {', '.join(available_languages) or 'none'}[/dim]\n")

    languages_to_show = [language] if language else available_languages

    if language and language not in available_languages:
        _warn_language_not_found(language, available_languages, structured_output, logger)
        raise typer.Exit(1)

    for lang in languages_to_show:
        _try_render_language_templates(core_engine, lang, verbose, structured_output, logger)

    _try_render_common_templates(core_engine, verbose, structured_output, logger)

    if not structured_output:
        console.print("\n[dim]Use --language <name> to filter by language[/dim]")
        console.print()

    logger.info("Template listing completed", languages_shown=len(languages_to_show))


def _warn_language_not_found(
    language: str,
    available_languages: list[str],
    structured_output: bool,
    logger: Any,
) -> None:
    """Warn about language not found."""
    if not structured_output:
        console.print(f"[yellow]Warning:[/yellow] Language '{language}' not found.")
        console.print(f"[dim]Available languages: {', '.join(available_languages)}[/dim]")
    logger.warning("Language not found", language=language, available=available_languages)


def _try_render_language_templates(
    core_engine: CoreEngine,
    lang: str,
    verbose: bool,
    structured_output: bool,
    logger: Any,
) -> None:
    """Try to render templates for a language, handling errors gracefully."""
    try:
        templates = core_engine.template_manager.load_templates(language=lang)
        _render_language_templates(lang, templates, verbose, structured_output, logger)
    except TemplateError as e:
        logger.warning("Could not load templates for language", language=lang, error=str(e))
        if not structured_output:
            console.print(f"[yellow]Warning:[/yellow] Could not load {lang} templates: {e}")


def _try_render_common_templates(
    core_engine: CoreEngine,
    verbose: bool,
    structured_output: bool,
    logger: Any,
) -> None:
    """Try to render common templates."""
    try:
        common_templates = core_engine.template_manager.load_templates(language="common")
        if common_templates:
            _render_language_templates("common (shared)", common_templates, verbose, structured_output, logger)
    except TemplateError:
        pass  # Common templates may not exist separately


def _handle_template_list_error(e: TemplateError, structured_output: bool, logger: Any) -> None:
    """Handle TemplateError in template list command."""
    if not structured_output:
        console.print(f"[red]Error:[/red] {e}")
        console.print("[dim]Run 'secuority init' to initialize templates.[/dim]")
    logger.error("Failed to load templates", error=str(e))
    raise typer.Exit(1) from None


def _render_language_templates(
    language: str,
    templates: dict[str, str],
    verbose: bool,
    structured_output: bool,
    logger: Any,
) -> None:
    """Render templates table for a specific language."""
    if structured_output:
        logger.info("Language templates", language=language, count=len(templates))
        return

    # Template descriptions by category
    template_descriptions: dict[str, str] = {
        # Python
        "pyproject.toml.template": "Python project configuration",
        ".pre-commit-config.yaml.template": "Pre-commit hooks",
        # Node.js
        "biome.json.template": "Biome linter/formatter config",
        "tsconfig.json.template": "TypeScript configuration",
        # Rust
        "Cargo.toml.template": "Rust project configuration",
        "rustfmt.toml": "Rust formatter configuration",
        "deny.toml": "Cargo deny configuration",
        # Go
        ".golangci.yml": "GolangCI-Lint configuration",
        # C++
        ".clang-format": "Clang formatter configuration",
        ".clang-tidy": "Clang-Tidy linter configuration",
        "CMakeLists.txt.template": "CMake build configuration",
        # C#
        ".editorconfig": "Editor configuration",
        "Directory.Build.props": "MSBuild properties",
        # Common
        ".gitignore.template": "Git ignore patterns",
        "SECURITY.md.template": "Security policy",
        "CONTRIBUTING.md": "Contributing guidelines",
    }

    table = Table(title=f"[bold]{language.capitalize()} Templates[/bold]", show_header=True, header_style="bold cyan")
    table.add_column("Template", style="cyan", no_wrap=True)
    table.add_column("Description", style="dim")
    table.add_column("Size", justify="right")

    for template_name, content in sorted(templates.items()):
        description = template_descriptions.get(template_name, _infer_template_description(template_name))
        size = f"{len(content):,} chars"
        table.add_row(template_name, description, size)

    console.print(table)

    if verbose:
        console.print(f"[dim]  Total: {len(templates)} templates[/dim]")
    console.print()


def _infer_template_description(template_name: str) -> str:
    """Infer description from template name."""
    if "workflow" in template_name or template_name.endswith(".yml"):
        return "GitHub Actions workflow"
    if template_name.startswith(".github/"):
        return "GitHub configuration"
    if template_name.endswith(".template"):
        base_name = template_name.replace(".template", "")
        return f"{base_name} configuration"
    return "Configuration file"


@template_app.command("update")
def template_update(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    structured_output: bool = typer.Option(False, "--structured", help="Output structured JSON logs"),
) -> None:
    """Update templates from remote source."""
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    try:
        logger.info("Starting template update")
        core_engine = _get_core_engine()
        success = _execute_template_update(core_engine, structured_output)
        _handle_template_update_result(
            core_engine=core_engine,
            success=success,
            structured_output=structured_output,
            verbose=verbose,
            logger=logger,
        )

    except TemplateError as e:
        logger.exception("Template update failed", error=str(e))
        if not structured_output:
            console.print(f"[red]Error:[/red] Failed to update templates: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        logger.exception("Unexpected error during template update", error=str(e))
        if not structured_output:
            console.print(f"[red]Error:[/red] Unexpected error: {e}")
        raise typer.Exit(1) from None


def _execute_template_update(core_engine: CoreEngine, structured_output: bool) -> bool:
    if structured_output:
        return core_engine.template_manager.update_templates()

    console.print("[bold blue]Updating templates...[/bold blue]")
    with console.status("[bold green]Fetching latest templates..."):
        return core_engine.template_manager.update_templates()


def _handle_template_update_result(
    *,
    core_engine: CoreEngine,
    success: bool,
    structured_output: bool,
    verbose: bool,
    logger: Any,
) -> None:
    if success:
        history = core_engine.template_manager.get_template_history()
        logger.log_operation(
            operation="template_update",
            status="success",
            details={"templates_updated": True, "source": "remote"},
        )
        if not structured_output:
            _render_template_update_success(history, verbose)
        return

    logger.log_operation(
        operation="template_update",
        status="failed",
        details={"error": "Update returned false"},
    )
    if not structured_output:
        console.print("[yellow]⚠ Template update completed with warnings[/yellow]")
        console.print("[dim]Some templates may not have been updated.[/dim]")


def _render_template_update_success(history: list[dict[str, Any]] | None, verbose: bool) -> None:
    console.print("[green]✓ Templates updated successfully![/green]")
    if verbose and history:
        console.print("\n[bold]Update History:[/bold]")
        for entry in history[-3:]:
            action = entry.get("action", "unknown")
            timestamp = entry.get("timestamp", "unknown")
            version = entry.get("version", "unknown")
            console.print(f"  • {action.title()}: {timestamp} (v{version})")
    console.print("[dim]All templates are now up to date.[/dim]")


@app.command()
def init(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    structured_output: bool = typer.Option(False, "--structured", help="Output structured JSON logs"),
) -> None:
    """Initialize Secuority configuration directory and templates."""
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    try:
        logger.info("Starting Secuority initialization")
        core_engine = _get_core_engine()
        template_dir = core_engine.template_manager.get_template_directory()

        if not structured_output:
            _render_init_header(template_dir)

        template_count = _perform_initialization(core_engine, structured_output, logger)

        logger.log_operation(
            operation="secuority_init",
            status="success",
            details={
                "steps_completed": 4,
                "template_directory": str(template_dir),
                "templates_created": template_count,
            },
        )

        if not structured_output:
            _render_init_success(template_dir, template_count, verbose)

    except TemplateError as e:
        logger.exception("Secuority initialization failed", error=str(e))
        if not structured_output:
            console.print(f"[red]Error:[/red] Failed to initialize Secuority: {e}")
        raise typer.Exit(1) from None
    except Exception as e:
        logger.exception("Unexpected error during initialization", error=str(e))
        if not structured_output:
            console.print(f"[red]Error:[/red] Unexpected error: {e}")
        raise typer.Exit(1) from None


def _render_init_header(template_dir: Path) -> None:
    console.print("[bold blue]Initializing Secuority...[/bold blue]")
    console.print(f"[dim]Template directory: {template_dir}[/dim]\n")


def _perform_initialization(
    core_engine: CoreEngine,
    structured_output: bool,
    logger: Any,
) -> int:
    def verify_installation() -> None:
        core_engine.template_manager.load_templates()

    steps: list[tuple[str, Callable[[], None]]] = [
        ("Creating template directory", lambda: None),
        ("Installing default templates", lambda: core_engine.template_manager.initialize_templates()),
        ("Setting up configuration", lambda: None),
        ("Verifying installation", verify_installation),
    ]

    for index, (step_name, step_func) in enumerate(steps, 1):
        logger.debug("Initialization step", step=step_name, index=index)
        if not structured_output:
            console.print(f"[dim]• {step_name}...[/dim]")
        try:
            step_func()
        except Exception as exc:
            logger.error("Initialization step failed", step=step_name, error=str(exc))
            if not structured_output:
                console.print(f"[red]  ✗ Failed: {exc}[/red]")
            raise

    try:
        templates = core_engine.template_manager.load_templates()
        return len(templates)
    except TemplateError:
        return 0


def _render_init_success(
    template_dir: Path,
    template_count: int,
    verbose: bool,
) -> None:
    console.print("\n[green]✓ Secuority initialized successfully![/green]")
    console.print(f"[dim]Created {template_count} templates in {template_dir}[/dim]")

    if verbose:
        console.print("\n[bold]Template Directory Structure:[/bold]")
        console.print(f"  {template_dir}/")
        console.print("  ├── templates/")
        console.print("  │   ├── common/          [dim]# Shared templates (.gitignore, SECURITY.md, etc.)[/dim]")
        console.print("  │   ├── python/          [dim]# Python templates (pyproject.toml, pre-commit, etc.)[/dim]")
        console.print("  │   ├── nodejs/          [dim]# Node.js templates (biome.json, tsconfig, etc.)[/dim]")
        console.print("  │   ├── rust/            [dim]# Rust templates (Cargo.toml, rustfmt, etc.)[/dim]")
        console.print("  │   ├── go/              [dim]# Go templates (golangci-lint, etc.)[/dim]")
        console.print("  │   ├── cpp/             [dim]# C++ templates (clang-format, CMake, etc.)[/dim]")
        console.print("  │   └── csharp/          [dim]# C# templates (.editorconfig, etc.)[/dim]")
        console.print("  ├── config.yaml")
        console.print("  └── version.json")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Run [cyan]secuority check[/cyan] to analyze your project")
    console.print("  2. Run [cyan]secuority apply[/cyan] to apply recommended configurations")
    console.print("  3. Use [cyan]secuority template list[/cyan] to see available templates")
    console.print()


def _resolve_project_path(project_path: Path | None) -> Path:
    """Resolve the path passed via CLI, defaulting to the current working directory."""
    return project_path or Path.cwd()


def _determine_target_languages(project_path: Path, explicit_languages: list[str] | None) -> list[str]:
    """Determine which languages should be analyzed.

    Uses a confidence threshold of 0.5 to avoid false positives.
    Returns only languages with strong indicators in the project.
    """
    if explicit_languages:
        return explicit_languages

    registry = get_global_registry()
    detected = registry.detect_languages(project_path, min_confidence=0.5)

    # Filter to languages with reasonable confidence (>= 50%)
    languages = [d.language for d in detected if d.confidence >= 0.5]

    # If no language meets the threshold, fall back to the primary detected language
    if not languages and detected:
        primary = detected[0]  # Already sorted by confidence
        if primary.confidence >= 0.3:
            languages = [primary.language]

    return languages or ["python"]


def _is_python_project(
    project_state: ProjectState,
    language_results: dict[str, LanguageAnalysisResult],
) -> bool:
    """Return True if Python is part of the analyzed languages."""

    def _language_detected(lang: str) -> bool:
        result = language_results.get(lang)
        if not result:
            return False
        return bool(result.get("detected", False) or result.get("confidence", 0.0) >= 0.5)

    if _language_detected("python"):
        return True

    # Fall back to the full analysis map if CLI filtering removed Python
    analysis = getattr(project_state, "language_analysis", {}) or {}
    fallback = analysis.get("python")
    if fallback:
        return bool(fallback.get("detected", False) or fallback.get("confidence", 0.0) >= 0.5)

    # Finally, rely on Python-specific files or tool configs as heuristics
    python_files_present = any(
        [
            project_state.has_pyproject_toml,
            project_state.has_requirements_txt,
            project_state.has_setup_py,
            bool(project_state.current_tools),
        ],
    )
    if python_files_present:
        return True

    # When nothing was detected at all, keep previous behavior and assume Python
    return not language_results


def _build_config_file_info(
    project_state: Any,
    include_python_files: bool,
) -> list[tuple[str, bool, str, bool]]:
    """Collect information about important configuration files."""

    files: list[tuple[str, bool, str, bool]] = []
    if include_python_files:
        files.extend(
            [
                ("pyproject.toml", project_state.has_pyproject_toml, "Modern Python configuration", True),
                ("requirements.txt", project_state.has_requirements_txt, "Legacy format (consider migration)", False),
                ("setup.py", project_state.has_setup_py, "Legacy format (consider migration)", False),
            ],
        )

    files.extend(
        [
            (".gitignore", project_state.has_gitignore, "Git ignore patterns", True),
            (".pre-commit-config.yaml", project_state.has_pre_commit_config, "Pre-commit hooks", True),
            ("SECURITY.md", project_state.has_security_md, "Security policy", True),
        ],
    )
    return files


def _render_analysis_header(project_path: Path, detected_languages: list[str]) -> None:
    """Render the header for the check command output."""
    console.print("\n[bold blue]Secuority Analysis Report[/bold blue]")
    console.print(f"[dim]Project: {project_path}[/dim]")
    console.print(f"[dim]Detected languages: {', '.join(detected_languages)}[/dim]\n")


def _render_config_table(config_files_info: list[tuple[str, bool, str, bool]]) -> None:
    """Render configuration file statuses in a table."""
    config_table = Table(title="Configuration Files", show_header=True, header_style="bold magenta")
    config_table.add_column("File", style="cyan", no_wrap=True)
    config_table.add_column("Status", justify="center")
    config_table.add_column("Notes", style="dim")

    for filename, exists, note, is_recommended in config_files_info:
        if is_recommended:
            status = "[green]✓ Found[/green]" if exists else "[red]✗ Missing[/red]"
        elif exists:
            status = "[yellow]⚠ Found[/yellow]"
        else:
            status = "[green]✓ Not used[/green]"

        config_table.add_row(filename, status, note)

    console.print(config_table)
    console.print()


def _log_config_file_info(
    logger: Any,
    project_path: Path,
    config_files_info: list[tuple[str, bool, str, bool]],
) -> None:
    """Log configuration file status details."""
    for filename, exists, note, is_recommended in config_files_info:
        logger.log_analysis_result(
            file_path=str(project_path / filename),
            analysis_type="file_existence",
            result={"exists": exists, "description": note, "is_recommended": is_recommended},
        )


def _get_language_results(
    project_state: ProjectState,
    project_path: Path,
    requested_languages: list[str],
    logger: Any,
) -> dict[str, LanguageAnalysisResult]:
    """Resolve language analysis results from the ProjectState or registry."""
    analysis = getattr(project_state, "language_analysis", {}) or {}

    if requested_languages:
        filtered = {lang: analysis[lang] for lang in requested_languages if lang in analysis}
        if filtered:
            return filtered
    elif analysis:
        return dict(analysis)

    try:
        registry = get_global_registry()
        analyzed = registry.analyze_project(project_path, languages=requested_languages or None)
        project_state.language_analysis = analyzed
        return analyzed
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Failed to analyze languages", error=str(exc))
        return {}


def _resolve_cli_languages(
    *,
    project_state: ProjectState,
    project_path: Path,
    requested_languages: list[str],
    detected_languages: list[str],
    logger: Any,
) -> tuple[dict[str, LanguageAnalysisResult], list[str]]:
    """Determine which languages to report in the CLI along with their results.

    Filters results to only include languages with confidence >= 50% unless
    explicitly requested via CLI arguments.
    """
    language_results = _get_language_results(
        project_state=project_state,
        project_path=project_path,
        requested_languages=requested_languages,
        logger=logger,
    )

    if not language_results:
        return language_results, detected_languages

    # If specific languages were requested, return all of them
    if requested_languages:
        return language_results, requested_languages

    # Filter to languages with meaningful confidence (>= 50%)
    filtered_results = {lang: result for lang, result in language_results.items() if result["confidence"] >= 0.5}

    # If nothing passes, fall back to the highest confidence language
    if not filtered_results and language_results:
        best_lang = max(language_results.items(), key=lambda x: x[1]["confidence"])
        filtered_results = {best_lang[0]: best_lang[1]}

    return filtered_results, list(filtered_results.keys())


def _render_language_summary(language_results: dict[str, LanguageAnalysisResult]) -> None:
    """Render a table summarizing language analysis results.

    Only displays languages with confidence >= 50% to avoid noise from false positives.
    """
    if not language_results:
        return

    # Filter to languages with meaningful confidence (>= 50%)
    # This prevents showing languages that are barely detected
    filtered_results = {lang: result for lang, result in language_results.items() if result["confidence"] >= 0.5}

    # Fall back to showing the highest confidence language if nothing passes threshold
    if not filtered_results and language_results:
        best_lang = max(language_results.items(), key=lambda x: x[1]["confidence"])
        filtered_results = {best_lang[0]: best_lang[1]}

    table = Table(title="Language Detection", show_header=True, header_style="bold cyan")
    table.add_column("Language", style="cyan")
    table.add_column("Confidence", justify="right")
    table.add_column("Detected", justify="center")
    table.add_column("Config Files", justify="right")
    table.add_column("Configured Tools", justify="right")
    table.add_column("Missing Recommended", style="yellow")

    for language, result in filtered_results.items():
        total_configs = len(result["config_files"])
        existing_configs = sum(1 for cfg in result["config_files"] if cfg.exists)
        total_tools = len(result["tools"])
        configured_tools = sum(1 for enabled in result["tools"].values() if enabled)
        missing_tools = [
            rec.tool_name for rec in result["recommendations"] if not result["tools"].get(rec.tool_name, False)
        ]

        table.add_row(
            language,
            f"{result['confidence']:.0%}",
            "[green]✓[/green]" if result["detected"] else "[red]✗[/red]",
            f"{existing_configs}/{total_configs}",
            f"{configured_tools}/{total_tools}",
            ", ".join(missing_tools[:3]) if missing_tools else "-",
        )

    console.print(table)
    console.print()


def _log_language_summary(
    logger: Any,
    project_path: Path,
    language_results: dict[str, LanguageAnalysisResult],
) -> None:
    """Log structured language analysis information."""
    if not language_results:
        return

    for language, result in language_results.items():
        missing_tools = [
            rec.tool_name for rec in result["recommendations"] if not result["tools"].get(rec.tool_name, False)
        ]
        logger.log_analysis_result(
            file_path=str(project_path),
            analysis_type=f"language:{language}",
            result={
                "detected": result["detected"],
                "confidence": result["confidence"],
                "configured_tools": {name: enabled for name, enabled in result["tools"].items() if enabled},
                "missing_tools": missing_tools,
            },
        )


def _render_dependency_manager(project_state: Any) -> None:
    if project_state.dependency_manager:
        console.print(f"[bold]Dependency Manager:[/bold] {project_state.dependency_manager.value}")
        console.print()


def _render_current_tools(project_state: Any) -> None:
    if not project_state.current_tools:
        return

    tools_table = Table(title="Configured Tools", show_header=True, header_style="bold green")
    tools_table.add_column("Tool", style="cyan")
    tools_table.add_column("Status", justify="center")

    for tool_name, tool_config in project_state.current_tools.items():
        status = "[green]✓ Configured[/green]" if tool_config.enabled else "[yellow]⚠ Disabled[/yellow]"
        tools_table.add_row(tool_name, status)

    console.print(tools_table)
    console.print()


def _render_security_tools(project_state: Any) -> None:
    if not project_state.security_tools:
        return

    security_table = Table(title="Security Tools", show_header=True, header_style="bold red")
    security_table.add_column("Tool", style="cyan")
    security_table.add_column("Status", justify="center")

    for tool, configured in project_state.security_tools.items():
        status = "[green]✓ Configured[/green]" if configured else "[red]✗ Not configured[/red]"
        security_table.add_row(tool.value, status)

    console.print(security_table)
    console.print()


MODERN_QUALITY_TOOLS = {"ruff", "basedpyright", "pyright"}
LEGACY_QUALITY_TOOLS = {"black", "isort", "flake8", "pylint", "mypy"}


def _render_quality_tools(project_state: Any) -> None:
    if not project_state.quality_tools:
        return

    quality_table = Table(title="Quality Tools", show_header=True, header_style="bold blue")
    quality_table.add_column("Tool", style="cyan")
    quality_table.add_column("Status", justify="center")
    quality_table.add_column("Notes", style="dim")

    quality_tool_sources = getattr(project_state, "quality_tool_sources", {})

    for quality_tool, configured in project_state.quality_tools.items():
        tool_name = quality_tool.value.lower()
        source = quality_tool_sources.get(quality_tool)

        if isinstance(source, str) and source.startswith("virtual:"):
            provider = source.split(":", 1)[1]
            if provider == "ruff-lint":
                status = "[green]✓ Covered by Ruff[/green]"
                note = "Import sorting handled via Ruff I-rules"
            else:
                status = "[green]✓ Covered by modern tool[/green]"
                note = f"Virtualized by {provider}"
            quality_table.add_row(quality_tool.value, status, note)
            continue

        if tool_name in MODERN_QUALITY_TOOLS:
            status = "[green]✓ Configured[/green]" if configured else "[red]✗ Not configured[/red]"
            note = "Modern tool" if configured else "Recommended"
        elif tool_name in LEGACY_QUALITY_TOOLS:
            is_mypy = tool_name == "mypy"
            if configured:
                status = "[yellow]⚠ Configured[/yellow]"
                note = "Consider migrating to basedpyright" if is_mypy else "Consider migrating to ruff"
            else:
                status = "[green]✓ Not used[/green]"
                note = "Legacy tool (basedpyright replaces this)" if is_mypy else "Legacy tool (ruff replaces this)"
        else:
            status = "[green]✓ Configured[/green]" if configured else "[red]✗ Not configured[/red]"
            note = ""

        quality_table.add_row(quality_tool.value, status, note)

    console.print(quality_table)
    console.print()


def _render_workflows(project_state: Any) -> None:
    if not project_state.ci_workflows:
        return

    workflows_table = Table(title="CI/CD Workflows", show_header=True, header_style="bold purple")
    workflows_table.add_column("Workflow", style="cyan")
    workflows_table.add_column("Security Checks", justify="center")
    workflows_table.add_column("Quality Checks", justify="center")

    for workflow in project_state.ci_workflows:
        security_status = "[green]✓[/green]" if workflow.has_security_checks else "[red]✗[/red]"
        quality_status = "[green]✓[/green]" if workflow.has_quality_checks else "[red]✗[/red]"
        workflows_table.add_row(workflow.name, security_status, quality_status)

    console.print(workflows_table)
    console.print()


def _perform_github_analysis(
    core_engine: CoreEngine,
    project_path: Path,
    logger: Any,
) -> GitHubAnalysisResult | None:
    """Run GitHub analysis if the client is available."""
    if not core_engine.github_client:
        return None

    try:
        return core_engine.analyzer.analyze_github_repository(project_path)
    except Exception as exc:
        logger.debug("GitHub analysis failed", error=str(exc))
        return None


def _render_github_section(github_analysis: GitHubAnalysisResult | None) -> None:
    """Render GitHub analysis results."""
    if not github_analysis:
        console.print("[dim]GitHub integration not available (no token or not a GitHub repository)[/dim]\n")
        return

    if github_analysis.get("analysis_successful"):
        github_table = Table(title="GitHub Integration", show_header=True, header_style="bold green")
        github_table.add_column("Feature", style="cyan")
        github_table.add_column("Status", justify="center")

        push_protection = bool(github_analysis.get("push_protection", False))
        github_table.add_row(
            "Push Protection",
            "[green]✓ Enabled[/green]" if push_protection else "[red]✗ Disabled[/red]",
        )

        dependabot_cfg = github_analysis.get("dependabot")
        db_enabled = bool(dependabot_cfg and dependabot_cfg.get("enabled"))
        github_table.add_row("Dependabot", "[green]✓ Enabled[/green]" if db_enabled else "[red]✗ Disabled[/red]")

        security_settings = github_analysis.get("security_settings")
        if security_settings:
            vuln_alerts = security_settings.get("dependency_graph", False)
            github_table.add_row(
                "Vulnerability Alerts",
                "[green]✓ Enabled[/green]" if vuln_alerts else "[red]✗ Disabled[/red]",
            )

            security_policy = security_settings.get("security_policy", False)
            github_table.add_row(
                "Security Policy",
                "[green]✓ Enabled[/green]" if security_policy else "[red]✗ Disabled[/red]",
            )

        console.print(github_table)

        is_private = security_settings.get("is_private", False) if security_settings else False
        if not is_private:
            console.print(
                "[dim]Note: Some security features (Secret Scanning, Push Protection) "
                "require GitHub Advanced Security for public repositories.[/dim]",
            )

        console.print()
        return

    if github_analysis.get("authenticated", False):
        console.print("[yellow]⚠ GitHub integration available but analysis failed[/yellow]")
        console.print(f"[dim]Error: {github_analysis.get('error', 'Unknown error')}[/dim]\n")
        return

    console.print("[dim]GitHub integration not available (no token or not a GitHub repository)[/dim]\n")


def _build_recommendations(
    project_state: Any,
    github_analysis: GitHubAnalysisResult | None,
    python_project: bool,
) -> list[str]:
    """Build a list of recommendations based on analysis results."""
    recommendations: list[str] = []
    _append_github_recommendations(recommendations, github_analysis)
    _append_config_file_recommendations(recommendations, project_state, python_project)
    if python_project:
        _append_security_recommendations(recommendations, project_state)
        _append_quality_recommendations(recommendations, project_state)
    _append_workflow_recommendations(recommendations, project_state)
    return recommendations


def _append_github_recommendations(
    recommendations: list[str],
    github_analysis: GitHubAnalysisResult | None,
) -> None:
    if not (github_analysis and github_analysis.get("analysis_successful")):
        return

    if not github_analysis.get("push_protection", False):
        recommendations.append("Enable GitHub Push Protection for secret scanning")

    dependabot_cfg = github_analysis.get("dependabot")
    dependabot_enabled = bool(dependabot_cfg and dependabot_cfg.get("enabled", False))

    if not dependabot_enabled:
        recommendations.append("Enable Dependabot for automated dependency updates")


def _append_config_file_recommendations(
    recommendations: list[str],
    project_state: Any,
    python_project: bool,
) -> None:
    if python_project and not project_state.has_pyproject_toml:
        recommendations.append("Create pyproject.toml for modern Python configuration")
    if not project_state.has_gitignore:
        recommendations.append("Add .gitignore file with Python patterns")
    if not project_state.has_pre_commit_config:
        recommendations.append("Set up pre-commit hooks for code quality")
    if not project_state.has_security_md:
        recommendations.append("Add SECURITY.md to define security policy and enable GitHub Security tab")

    dep_analysis = project_state.dependency_analysis
    if python_project and dep_analysis and dep_analysis.migration_needed:
        recommendations.append("Migrate from requirements.txt to pyproject.toml dependencies")


def _append_security_recommendations(recommendations: list[str], project_state: Any) -> None:
    if not project_state.security_tools:
        return

    missing_security = [tool.value for tool, configured in project_state.security_tools.items() if not configured]
    if missing_security:
        recommendations.append(f"Configure security tools: {', '.join(missing_security)}")


def _append_quality_recommendations(recommendations: list[str], project_state: Any) -> None:
    if not project_state.quality_tools:
        return

    missing_essential = [
        qt.value
        for qt, configured in project_state.quality_tools.items()
        if qt.value.lower() in MODERN_QUALITY_TOOLS and not configured
    ]
    if missing_essential:
        recommendations.append(f"Configure essential quality tools: {', '.join(missing_essential)}")

    ruff_configured = any(
        tool.value.lower() == "ruff" and configured for tool, configured in project_state.quality_tools.items()
    )
    if ruff_configured:
        redundant_tools = [
            tool.value
            for tool, configured in project_state.quality_tools.items()
            if configured and tool.value.lower() in {"black", "flake8", "isort"}
        ]
        if redundant_tools:
            recommendations.append(
                f"Consider removing redundant tools (ruff already handles: {', '.join(redundant_tools)})",
            )
        return

    legacy_in_use = [
        tool.value
        for tool, configured in project_state.quality_tools.items()
        if configured and tool.value.lower() in {"black", "flake8", "pylint"}
    ]
    if legacy_in_use:
        recommendations.append(f"Consider migrating to ruff (can replace: {', '.join(legacy_in_use)})")


def _append_workflow_recommendations(recommendations: list[str], project_state: Any) -> None:
    if not project_state.ci_workflows:
        recommendations.append("Set up CI/CD workflows for automated testing and security checks")
        return

    has_security_workflow = any(wf.has_security_checks for wf in project_state.ci_workflows)
    has_quality_workflow = any(wf.has_quality_checks for wf in project_state.ci_workflows)
    if not has_security_workflow:
        recommendations.append("Add security checks to existing CI/CD workflows")
    if not has_quality_workflow:
        recommendations.append("Add quality checks to existing CI/CD workflows")


def _log_recommendations(logger: Any, recommendations: list[str]) -> None:
    if recommendations:
        logger.info("Generated recommendations", recommendations=recommendations, count=len(recommendations))
    else:
        logger.info("No recommendations needed - project configuration looks good")


def _log_project_statistics(logger: Any, project_path: Path) -> int:
    python_files_count = len(list(project_path.glob("**/*.py")))
    logger.debug(
        "Project statistics",
        python_files=python_files_count,
        total_files=len(list(project_path.glob("**/*"))),
    )
    return python_files_count


def _render_recommendation_panel(recommendations: list[str]) -> None:
    if recommendations:
        console.print(
            Panel(
                "\n".join(f"• {rec}" for rec in recommendations),
                title="[bold yellow]Recommendations[/bold yellow]",
                border_style="yellow",
            ),
        )
        return

    console.print(
        Panel(
            "[green]✓ Project configuration looks good![/green]",
            title="[bold green]Status[/bold green]",
            border_style="green",
        ),
    )


def _render_verbose_details(
    project_path: Path,
    project_state: Any,
    github_analysis: GitHubAnalysisResult | None,
    python_files_count: int,
    core_engine: CoreEngine,
) -> None:
    """Render the verbose section of the check command."""
    console.print("\n[bold]Detailed Information:[/bold]")
    console.print(f"  • Project path: {project_path}")
    console.print(f"  • Python files found: {python_files_count}")
    if project_state.python_version:
        console.print(f"  • Python version requirement: {project_state.python_version}")
    if project_state.dependency_manager:
        console.print(f"  • Dependency manager: {project_state.dependency_manager.value}")

    _render_dependency_stats(project_state)
    _render_configured_tools(project_state)
    _render_workflow_details(project_state)
    _render_github_details(github_analysis)
    _render_template_overview(core_engine)
    console.print()


def _render_dependency_stats(project_state: Any) -> None:
    dep_analysis = project_state.dependency_analysis
    if not dep_analysis:
        return

    console.print(f"  • Requirements.txt packages: {len(dep_analysis.requirements_packages)}")
    console.print(f"  • Pyproject.toml dependencies: {len(dep_analysis.pyproject_dependencies)}")
    if dep_analysis.extras_found:
        console.print(f"  • Extras found: {', '.join(dep_analysis.extras_found)}")
    if dep_analysis.conflicts:
        console.print(f"  • Dependency conflicts: {len(dep_analysis.conflicts)}")
        for conflict in dep_analysis.conflicts[:3]:
            console.print(f"    - {conflict}")


def _render_configured_tools(project_state: Any) -> None:
    if not project_state.current_tools:
        return

    console.print(f"  • Configured tools: {len(project_state.current_tools)}")
    for tool_name in list(project_state.current_tools.keys())[:5]:
        console.print(f"    - {tool_name}")


def _render_workflow_details(project_state: Any) -> None:
    if not project_state.ci_workflows:
        return

    console.print(f"  • CI/CD workflows: {len(project_state.ci_workflows)}")
    for workflow in project_state.ci_workflows[:3]:
        triggers = ", ".join(workflow.triggers[:2]) if workflow.triggers else "none"
        console.print(f"    - {workflow.name} (triggers: {triggers})")


def _render_github_details(github_analysis: GitHubAnalysisResult | None) -> None:
    if not (github_analysis and github_analysis.get("analysis_successful")):
        return

    console.print(
        f"  • GitHub repository: {github_analysis.get('owner')}/{github_analysis.get('repo')}",
    )
    workflows = github_analysis.get("workflows", [])
    if workflows:
        console.print(f"  • Remote workflows: {len(workflows)}")
        for workflow in workflows[:3]:
            console.print(f"    - {workflow.get('name', 'Unknown')}")


def _render_template_overview(core_engine: CoreEngine) -> None:
    try:
        template_dir = core_engine.template_manager.get_template_directory()
        console.print(f"  • Template directory: {template_dir}")
        templates = core_engine.template_manager.load_templates()
        console.print(f"  • Available templates: {len(templates)}")
    except TemplateError:
        console.print("  • Templates: Not initialized")


def main() -> None:
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
