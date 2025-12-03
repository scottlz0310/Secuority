"""Main CLI entry point for Secuority."""

from collections.abc import Callable
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..core.analyzer import ProjectAnalyzer
from ..core.applier import ConfigurationApplier
from ..core.engine import CoreEngine
from ..core.github_client import GitHubClient
from ..core.languages import get_global_registry
from ..core.template_manager import TemplateManager
from ..models.config import ConfigChange
from ..models.exceptions import ConfigurationError, ProjectAnalysisError, TemplateError
from ..models.interfaces import GitHubAnalysisResult
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
    # Configure logging based on CLI options
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    # Use current directory if no project path specified
    if project_path is None:
        project_path = Path.cwd()

    try:
        logger.info("Starting project analysis", project_path=str(project_path))
        logger.debug("Analysis configuration", verbose=verbose, structured_output=structured_output)

        # Detect languages in the project
        registry = get_global_registry()

        # Auto-detect or use specified languages
        if language is None:
            detected = registry.detect_languages(project_path)
            detected_languages = [d.language for d in detected if d.confidence > 0.3]
            if not detected_languages:
                # Default to Python if no languages detected
                detected_languages = ["python"]
        else:
            detected_languages = language

        logger.info("Detected languages", languages=detected_languages)

        # Get core engine and analyze project
        core_engine = _get_core_engine()
        project_state = core_engine.analyze_project(project_path)

        if not structured_output:
            console.print("\n[bold blue]Secuority Analysis Report[/bold blue]")
            console.print(f"[dim]Project: {project_path}[/dim]")
            console.print(f"[dim]Detected languages: {', '.join(detected_languages)}[/dim]\n")

        # Display configuration files status
        config_files_info = [
            ("pyproject.toml", project_state.has_pyproject_toml, "Modern Python configuration", True),
            ("requirements.txt", project_state.has_requirements_txt, "Legacy format (consider migration)", False),
            ("setup.py", project_state.has_setup_py, "Legacy format (consider migration)", False),
            (".gitignore", project_state.has_gitignore, "Git ignore patterns", True),
            (".pre-commit-config.yaml", project_state.has_pre_commit_config, "Pre-commit hooks", True),
            ("SECURITY.md", project_state.has_security_md, "Security policy", True),
        ]

        if not structured_output:
            config_table = Table(title="Configuration Files", show_header=True, header_style="bold magenta")
            config_table.add_column("File", style="cyan", no_wrap=True)
            config_table.add_column("Status", justify="center")
            config_table.add_column("Notes", style="dim")

            for filename, exists, note, is_recommended in config_files_info:
                if is_recommended:
                    # For recommended files (pyproject.toml, .gitignore, .pre-commit-config.yaml)
                    status = "[green]✓ Found[/green]" if exists else "[red]✗ Missing[/red]"
                # For legacy files (requirements.txt, setup.py) - not having them is good
                elif exists:
                    status = "[yellow]⚠ Found[/yellow]"
                else:
                    status = "[green]✓ Not used[/green]"

                config_table.add_row(filename, status, note)

            console.print(config_table)
            console.print()

        # Log analysis results
        for filename, exists, note, is_recommended in config_files_info:
            logger.log_analysis_result(
                file_path=str(project_path / filename),
                analysis_type="file_existence",
                result={"exists": exists, "description": note, "is_recommended": is_recommended},
            )

        # Display dependency manager information
        if project_state.dependency_manager and not structured_output:
            console.print(f"[bold]Dependency Manager:[/bold] {project_state.dependency_manager.value}")
            console.print()

        # Display configured tools
        if project_state.current_tools and not structured_output:
            tools_table = Table(title="Configured Tools", show_header=True, header_style="bold green")
            tools_table.add_column("Tool", style="cyan")
            tools_table.add_column("Status", justify="center")

            for tool_name, tool_config in project_state.current_tools.items():
                status = "[green]✓ Configured[/green]" if tool_config.enabled else "[yellow]⚠ Disabled[/yellow]"
                tools_table.add_row(tool_name, status)

            console.print(tools_table)
            console.print()

        # Display security tools status
        if project_state.security_tools and not structured_output:
            security_table = Table(title="Security Tools", show_header=True, header_style="bold red")
            security_table.add_column("Tool", style="cyan")
            security_table.add_column("Status", justify="center")

            for tool, configured in project_state.security_tools.items():
                status = "[green]✓ Configured[/green]" if configured else "[red]✗ Not configured[/red]"
                security_table.add_row(tool.value, status)

            console.print(security_table)
            console.print()

        # Display quality tools status
        if project_state.quality_tools and not structured_output:
            quality_table = Table(title="Quality Tools", show_header=True, header_style="bold blue")
            quality_table.add_column("Tool", style="cyan")
            quality_table.add_column("Status", justify="center")
            quality_table.add_column("Notes", style="dim")

            # Define modern and legacy tools
            modern_tools = {"ruff", "mypy"}
            legacy_tools = {"black", "isort", "flake8", "pylint"}

            for quality_tool, configured in project_state.quality_tools.items():
                tool_name = quality_tool.value.lower()

                if tool_name in modern_tools:
                    # Modern tools - show configured/not configured
                    status = "[green]✓ Configured[/green]" if configured else "[red]✗ Not configured[/red]"
                    note = "Modern tool" if configured else "Recommended"
                elif tool_name in legacy_tools:
                    # Legacy tools - show not used (green) if not configured
                    if configured:
                        status = "[yellow]⚠ Configured[/yellow]"
                        note = "Consider migrating to ruff"
                    else:
                        status = "[green]✓ Not used[/green]"
                        note = "Legacy tool (ruff replaces this)"
                else:
                    # Other tools
                    status = "[green]✓ Configured[/green]" if configured else "[red]✗ Not configured[/red]"
                    note = ""

                quality_table.add_row(quality_tool.value, status, note)

            console.print(quality_table)
            console.print()

        # Display CI/CD workflows
        if project_state.ci_workflows and not structured_output:
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

        # Initialize recommendations list
        recommendations: list[str] = []

        # GitHub integration analysis (if available)
        github_analysis: GitHubAnalysisResult | None = None
        if core_engine.github_client:
            try:
                github_analysis = core_engine.analyzer.analyze_github_repository(project_path)
                if github_analysis.get("analysis_successful"):
                    if not github_analysis.get("push_protection", False):
                        recommendations.append("Enable GitHub Push Protection for secret scanning")

                    dependabot_cfg = github_analysis.get("dependabot")
                    if not dependabot_cfg or not dependabot_cfg.get("enabled", False):
                        recommendations.append("Enable Dependabot for automated dependency updates")
            except Exception as e:
                logger.debug("GitHub analysis failed", error=str(e))
                # Don't fail the entire check if GitHub analysis fails

        # Display GitHub integration status
        if github_analysis and not structured_output:
            if github_analysis.get("analysis_successful"):
                github_table = Table(title="GitHub Integration", show_header=True, header_style="bold green")
                github_table.add_column("Feature", style="cyan")
                github_table.add_column("Status", justify="center")

                # Push Protection
                push_protection = bool(github_analysis.get("push_protection", False))
                pp_status = "[green]✓ Enabled[/green]" if push_protection else "[red]✗ Disabled[/red]"
                github_table.add_row("Push Protection", pp_status)

                # Dependabot
                dependabot_cfg = github_analysis.get("dependabot")
                db_enabled = bool(dependabot_cfg and dependabot_cfg.get("enabled"))
                db_status = "[green]✓ Enabled[/green]" if db_enabled else "[red]✗ Disabled[/red]"
                github_table.add_row("Dependabot", db_status)

                # Security Settings
                security_settings = github_analysis.get("security_settings")
                if security_settings:
                    # Vulnerability Alerts (dependency_graph in API response)
                    vuln_alerts = security_settings.get("dependency_graph", False)
                    va_status = "[green]✓ Enabled[/green]" if vuln_alerts else "[red]✗ Disabled[/red]"
                    github_table.add_row("Vulnerability Alerts", va_status)

                    # Security Policy
                    security_policy = security_settings.get("security_policy", False)
                    sp_status = "[green]✓ Enabled[/green]" if security_policy else "[red]✗ Disabled[/red]"
                    github_table.add_row("Security Policy", sp_status)

                console.print(github_table)

                # Add note for public repositories
                is_private = security_settings.get("is_private", False) if security_settings else False
                if not is_private:
                    console.print(
                        "[dim]Note: Some security features (Secret Scanning, Push Protection) "
                        "require GitHub Advanced Security for public repositories.[/dim]",
                    )

                console.print()
            elif github_analysis.get("authenticated", False):
                console.print("[yellow]⚠ GitHub integration available but analysis failed[/yellow]")
                console.print(f"[dim]Error: {github_analysis.get('error', 'Unknown error')}[/dim]\n")
            else:
                console.print("[dim]GitHub integration not available (no token or not a GitHub repository)[/dim]\n")

        # Add more recommendations based on project state
        if not project_state.has_pyproject_toml:
            recommendations.append("Create pyproject.toml for modern Python configuration")
        if not project_state.has_gitignore:
            recommendations.append("Add .gitignore file with Python patterns")
        if not project_state.has_pre_commit_config:
            recommendations.append("Set up pre-commit hooks for code quality")
        if not project_state.has_security_md:
            recommendations.append("Add SECURITY.md to define security policy and enable GitHub Security tab")

        # Check for dependency migration
        if project_state.dependency_analysis and project_state.dependency_analysis.migration_needed:
            recommendations.append("Migrate from requirements.txt to pyproject.toml dependencies")

        # Check for missing security tools
        if project_state.security_tools:
            missing_security: list[str] = [
                tool.value for tool, configured in project_state.security_tools.items() if not configured
            ]
            if missing_security:
                recommendations.append(f"Configure security tools: {', '.join(missing_security)}")

        # Check for missing quality tools (modern approach)
        if project_state.quality_tools:
            # Check for essential modern tools
            essential_tools = ["ruff", "mypy"]
            missing_essential: list[str] = []

            for quality_tool, configured in project_state.quality_tools.items():
                tool_name = quality_tool.value.lower()
                if tool_name in essential_tools and not configured:
                    missing_essential.append(quality_tool.value)

            if missing_essential:
                recommendations.append(f"Configure essential quality tools: {', '.join(missing_essential)}")

            # Check for tool redundancy and suggest modern alternatives
            ruff_configured = any(t.value.lower() == "ruff" for t, c in project_state.quality_tools.items() if c)

            if ruff_configured:
                # Check if using redundant tools that ruff can replace
                redundant_tools: list[str] = []
                for qtool, configured in project_state.quality_tools.items():
                    tool_name = qtool.value.lower()
                    if tool_name in ["black", "flake8", "isort"] and configured:
                        # Only suggest if it's configured separately from ruff
                        redundant_tools.append(qtool.value)

                if redundant_tools:
                    recommendations.append(
                        f"Consider removing redundant tools (ruff already handles: {', '.join(redundant_tools)})",
                    )
            else:
                # Ruff not configured, suggest it as replacement for legacy tools
                legacy_in_use: list[str] = []
                for qtool, configured in project_state.quality_tools.items():
                    tool_name = qtool.value.lower()
                    if tool_name in ["black", "flake8", "pylint"] and configured:
                        legacy_in_use.append(qtool.value)

                if legacy_in_use:
                    recommendations.append(f"Consider migrating to ruff (can replace: {', '.join(legacy_in_use)})")

        # Check CI workflows - only recommend if no workflows exist
        if not project_state.ci_workflows:
            recommendations.append("Set up CI/CD workflows for automated testing and security checks")
        else:
            # If workflows exist, check for specific missing features
            has_security_workflow = any(wf.has_security_checks for wf in project_state.ci_workflows)
            has_quality_workflow = any(wf.has_quality_checks for wf in project_state.ci_workflows)

            if not has_security_workflow:
                recommendations.append("Add security checks to existing CI/CD workflows")
            if not has_quality_workflow:
                recommendations.append("Add quality checks to existing CI/CD workflows")

        # Log recommendations
        if recommendations:
            logger.info("Generated recommendations", recommendations=recommendations, count=len(recommendations))
        else:
            logger.info("No recommendations needed - project configuration looks good")

        # Count Python files for verbose output
        python_files_count = len(list(project_path.glob("**/*.py")))
        logger.debug(
            "Project statistics",
            python_files=python_files_count,
            total_files=len(list(project_path.glob("**/*"))),
        )

        if not structured_output:
            if recommendations:
                console.print(
                    Panel(
                        "\n".join(f"• {rec}" for rec in recommendations),
                        title="[bold yellow]Recommendations[/bold yellow]",
                        border_style="yellow",
                    ),
                )
            else:
                console.print(
                    Panel(
                        "[green]✓ Project configuration looks good![/green]",
                        title="[bold green]Status[/bold green]",
                        border_style="green",
                    ),
                )

            if verbose:
                console.print("\n[bold]Detailed Information:[/bold]")
                console.print(f"  • Project path: {project_path}")
                console.print(f"  • Python files found: {python_files_count}")
                if project_state.python_version:
                    console.print(f"  • Python version requirement: {project_state.python_version}")
                if project_state.dependency_manager:
                    console.print(f"  • Dependency manager: {project_state.dependency_manager.value}")

                if project_state.dependency_analysis:
                    dep_analysis = project_state.dependency_analysis
                    console.print(f"  • Requirements.txt packages: {len(dep_analysis.requirements_packages)}")
                    console.print(f"  • Pyproject.toml dependencies: {len(dep_analysis.pyproject_dependencies)}")
                    if dep_analysis.extras_found:
                        console.print(f"  • Extras found: {', '.join(dep_analysis.extras_found)}")
                    if dep_analysis.conflicts:
                        console.print(f"  • Dependency conflicts: {len(dep_analysis.conflicts)}")
                        for conflict in dep_analysis.conflicts[:3]:  # Show first 3 conflicts
                            console.print(f"    - {conflict}")

                # Show configured tools details
                if project_state.current_tools:
                    console.print(f"  • Configured tools: {len(project_state.current_tools)}")
                    for tool_name in list(project_state.current_tools.keys())[:5]:  # Show first 5
                        console.print(f"    - {tool_name}")

                # Show workflow details
                if project_state.ci_workflows:
                    console.print(f"  • CI/CD workflows: {len(project_state.ci_workflows)}")
                    for workflow in project_state.ci_workflows[:3]:  # Show first 3
                        triggers = ", ".join(workflow.triggers[:2]) if workflow.triggers else "none"
                        console.print(f"    - {workflow.name} (triggers: {triggers})")

                # Show GitHub details
                if github_analysis and github_analysis.get("analysis_successful"):
                    console.print(
                        f"  • GitHub repository: {github_analysis.get('owner')}/{github_analysis.get('repo')}",
                    )
                    workflows = github_analysis.get("workflows", [])
                    if workflows:
                        console.print(f"  • Remote workflows: {len(workflows)}")
                        for workflow in workflows[:3]:  # Show first 3
                            console.print(f"    - {workflow.get('name', 'Unknown')}")

                # Show template information
                try:
                    template_dir = core_engine.template_manager.get_template_directory()
                    console.print(f"  • Template directory: {template_dir}")
                    templates = core_engine.template_manager.load_templates()
                    console.print(f"  • Available templates: {len(templates)}")
                except TemplateError:
                    console.print("  • Templates: Not initialized")

            console.print()

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
    # Configure logging
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    # Use current directory if no project path specified
    if project_path is None:
        project_path = Path.cwd()

    try:
        logger.info("Starting configuration application", project_path=str(project_path), dry_run=dry_run, force=force)

        # Detect languages in the project
        registry = get_global_registry()

        # Auto-detect or use specified languages
        if language is None:
            detected = registry.detect_languages(project_path)
            detected_languages = [d.language for d in detected if d.confidence > 0.3]
            if not detected_languages:
                # Default to Python if no languages detected
                detected_languages = ["python"]
        else:
            detected_languages = language

        logger.info("Target languages for template application", languages=detected_languages)

        if not structured_output:
            if dry_run:
                console.print("\n[bold blue]Dry Run - Configuration Changes Preview[/bold blue]\n")
            else:
                console.print("\n[bold green]Applying Configuration Changes[/bold green]\n")

            console.print(f"[dim]Project: {project_path}[/dim]")
            console.print(f"[dim]Languages: {', '.join(detected_languages)}[/dim]")
            console.print(f"[dim]Dry run: {dry_run}, Force: {force}[/dim]\n")

        # Get core engine and analyze project first
        core_engine = _get_core_engine()
        project_state = core_engine.analyze_project(project_path)

        # Generate configuration changes based on analysis
        changes: list[ConfigChange] = []

        # Load templates for all detected languages
        all_templates: dict[str, str] = {}
        try:
            # Load templates for each detected language
            for lang in detected_languages:
                try:
                    lang_templates = core_engine.template_manager.load_templates(language=lang)
                    # Prefix template names with language for disambiguation if multiple languages
                    if len(detected_languages) > 1:
                        all_templates.update({f"{lang}:{k}": v for k, v in lang_templates.items()})
                    else:
                        all_templates.update(lang_templates)
                    logger.debug(f"Loaded {len(lang_templates)} templates for {lang}")
                except TemplateError as e:
                    logger.warning(f"Could not load templates for {lang}", error=str(e))
        except Exception as e:
            if not structured_output:
                console.print(f"[yellow]Warning:[/yellow] Could not load templates: {e}")
                console.print("[dim]Run 'secuority init' to initialize templates.[/dim]")
            logger.warning("Templates not available", error=str(e))

        templates: dict[str, str] = all_templates

        # Filter changes based on options
        apply_security = not templates_only
        apply_templates = not security_only

        logger.debug(
            "Generating configuration changes",
            apply_security=apply_security,
            apply_templates=apply_templates,
            templates_available=len(templates),
        )

        # Generate changes for missing template files
        if apply_templates:
            # pyproject.toml template
            if not project_state.has_pyproject_toml and "pyproject.toml.template" in templates:
                try:
                    change = core_engine.applier.merge_file_configurations(
                        project_path / "pyproject.toml",
                        templates["pyproject.toml.template"],
                    )
                    changes.append(change)
                    logger.debug("Added pyproject.toml template change")
                except Exception as e:
                    logger.warning("Failed to generate pyproject.toml change", error=str(e))

            # .gitignore template
            if not project_state.has_gitignore and ".gitignore.template" in templates:
                try:
                    change = core_engine.applier.merge_file_configurations(
                        project_path / ".gitignore",
                        templates[".gitignore.template"],
                    )
                    changes.append(change)
                    logger.debug("Added .gitignore template change")
                except Exception as e:
                    logger.warning("Failed to generate .gitignore change", error=str(e))

            # pre-commit template
            if not project_state.has_pre_commit_config and ".pre-commit-config.yaml.template" in templates:
                try:
                    change = core_engine.applier.merge_file_configurations(
                        project_path / ".pre-commit-config.yaml",
                        templates[".pre-commit-config.yaml.template"],
                    )
                    changes.append(change)
                    logger.debug("Added pre-commit template change")
                except Exception as e:
                    logger.warning("Failed to generate pre-commit change", error=str(e))

            # SECURITY.md template
            if not project_state.has_security_md and "SECURITY.md.template" in templates:
                try:
                    change = core_engine.applier.merge_file_configurations(
                        project_path / "SECURITY.md",
                        templates["SECURITY.md.template"],
                    )
                    changes.append(change)
                    logger.debug("Added SECURITY.md template change")
                except Exception as e:
                    logger.warning("Failed to generate SECURITY.md change", error=str(e))

        # Add security tools integration if needed
        if apply_security and project_state.security_tools:
            missing_security_tools: list[str] = [
                tool.value for tool, configured in project_state.security_tools.items() if not configured
            ]
            if missing_security_tools:
                try:
                    security_changes = core_engine.applier.get_security_integration_changes(
                        project_path,
                        missing_security_tools,
                    )
                    changes.extend(security_changes)
                    logger.debug(
                        "Added security tools integration changes",
                        tools=missing_security_tools,
                        count=len(security_changes),
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to generate security integration changes",
                        tools=missing_security_tools,
                        error=str(e),
                    )

        # Add quality tools integration if needed
        if apply_templates and project_state.quality_tools:
            missing_quality_tools: list[str] = [
                tool.value for tool, configured in project_state.quality_tools.items() if not configured
            ]
            if missing_quality_tools:
                try:
                    quality_changes = core_engine.applier.get_quality_integration_changes(
                        project_path,
                        missing_quality_tools,
                    )
                    changes.extend(quality_changes)
                    logger.debug(
                        "Added quality tools integration changes",
                        tools=missing_quality_tools,
                        count=len(quality_changes),
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to generate quality integration changes",
                        tools=missing_quality_tools,
                        error=str(e),
                    )

        # Handle dependency migration if needed
        if apply_templates and project_state.dependency_analysis and project_state.dependency_analysis.migration_needed:
            try:
                migration_change = core_engine.applier.get_dependency_migration_change(
                    project_path,
                    project_state.dependency_analysis,
                )
                if migration_change:
                    changes.append(migration_change)
                    logger.debug("Added dependency migration change")
            except Exception as e:
                logger.warning("Failed to generate dependency migration change", error=str(e))

        # Add CI/CD workflows if needed
        if apply_templates:
            try:
                workflow_changes = core_engine.applier.get_workflow_integration_changes(
                    project_path,
                    ["security", "quality", "cicd", "dependency"],
                )
                changes.extend(workflow_changes)
                logger.debug("Added CI/CD workflow changes", count=len(workflow_changes))
            except Exception as e:
                logger.warning("Failed to generate workflow changes", error=str(e))

        if not changes:
            if not structured_output:
                console.print("[green]✓ No configuration changes needed![/green]")
                console.print("[dim]Project configuration is already up to date.[/dim]")
            logger.info("No configuration changes needed")
            return

        # Show planned changes
        if not structured_output:
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

        # Get user confirmation if not dry run and not force
        if not dry_run and not force:
            if not structured_output:
                console.print("[bold yellow]⚠️  This will modify your project files![/bold yellow]")
                console.print("[dim]Backups will be created for existing files.[/dim]")

                # Show summary of what will be changed
                file_changes: dict[str, list[str]] = {}
                for change in changes:
                    action = change.change_type.value
                    if action not in file_changes:
                        file_changes[action] = []
                    file_changes[action].append(change.file_path.name)

                console.print("\n[bold]Summary of changes:[/bold]")
                for action, files in file_changes.items():
                    action_color = {"CREATE": "[green]", "UPDATE": "[yellow]", "MERGE": "[blue]"}.get(action, "[white]")
                    console.print(f"  {action_color}{action}[/{action_color.split('[')[1]}]: {', '.join(files)}")

                confirm = typer.confirm(f"\nApply {len(changes)} configuration changes?")
                if not confirm:
                    console.print("[yellow]Operation cancelled.[/yellow]")
                    logger.info("Operation cancelled by user", changes_count=len(changes))
                    return
            else:
                # In structured mode, require force flag for non-interactive operation
                logger.error("Interactive confirmation required - use --force flag for non-interactive operation")
                raise typer.Exit(1) from None

        # Check for conflicts before applying
        conflicted_changes = [c for c in changes if c.has_conflicts()]
        if conflicted_changes and not dry_run:
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
                    console.print(
                        "\n[dim]Stopping due to conflicts. Use --force to apply non-conflicted changes.[/dim]",
                    )
                    logger.warning(
                        "Configuration conflicts detected - stopping",
                        conflicted_changes=len(conflicted_changes),
                        total_conflicts=sum(len(c.conflicts) for c in conflicted_changes),
                    )
                    return
                # Filter out conflicted changes when using --force
                console.print("\n[yellow]--force flag detected: applying non-conflicted changes only[/yellow]")
                changes = [c for c in changes if not c.has_conflicts()]
                logger.info(
                    "Applying non-conflicted changes only due to --force flag",
                    original_changes=len(changes) + len(conflicted_changes),
                    applying_changes=len(changes),
                )
            else:
                logger.warning(
                    "Configuration conflicts detected",
                    conflicted_changes=len(conflicted_changes),
                    total_conflicts=sum(len(c.conflicts) for c in conflicted_changes),
                )
                if not force:
                    return
                # Filter out conflicted changes when using --force
                changes = [c for c in changes if not c.has_conflicts()]

        # Apply changes with appropriate method based on mode
        logger.info(
            "Applying configuration changes",
            changes_count=len(changes),
            dry_run=dry_run,
            interactive=not structured_output and not force and not dry_run,
        )

        if not structured_output and not force and not dry_run:
            # Interactive mode - show diffs and get individual approvals
            result = core_engine.applier.apply_changes_interactively(changes, dry_run=dry_run, batch_mode=False)
        # Batch mode - apply all changes at once
        elif not structured_output and not dry_run:
            with console.status("[bold green]Applying configuration changes..."):
                result = core_engine.applier.apply_changes(changes, dry_run=dry_run)
        else:
            result = core_engine.applier.apply_changes(changes, dry_run=dry_run)

        # Log results
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

        # Show results
        if not structured_output:
            console.print()  # Add spacing

            if result.successful_changes:
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
                else:
                    # Show summary of file types changed
                    changed_files = [change.file_path.name for change in result.successful_changes]
                    console.print(f"[dim]Modified files: {', '.join(changed_files)}[/dim]")

            if result.failed_changes:
                console.print(f"[red]✗ Failed to apply {len(result.failed_changes)} changes[/red]")
                for change, _error in result.failed_changes:
                    console.print(f"  • [red]{change.file_path.name}[/red]: {_error}")

            if result.backups_created:
                console.print(f"[dim]Created {len(result.backups_created)} backup files[/dim]")
                if verbose:
                    console.print("\n[bold]Backup files:[/bold]")
                    for backup_path in result.backups_created:
                        console.print(f"  • {backup_path}")

            if result.conflicts:
                console.print(f"[yellow]⚠ {len(result.conflicts)} conflicts need manual resolution[/yellow]")
                if verbose:
                    console.print("\n[bold]Unresolved conflicts:[/bold]")
                    for conflict in result.conflicts:
                        console.print(f"  • [yellow]{conflict.file_path}[/yellow]: {conflict.description}")

            # Show summary with next steps
            if dry_run:
                console.print("\n[bold]Summary:[/bold] This was a dry run - no changes were made.")
                if changes:
                    console.print("[dim]Run without --dry-run to apply these changes.[/dim]")
            elif result.successful_changes:
                console.print("\n[bold]Summary:[/bold] Configuration changes applied successfully!")
                console.print("\n[bold]Next steps:[/bold]")
                console.print("  1. Review the applied changes")
                console.print("  2. Run [cyan]secuority check[/cyan] to verify the configuration")
                console.print("  3. Commit your changes to version control")

                # Suggest specific next steps based on what was applied
                has_precommit = any("pre-commit" in str(c.file_path) for c in result.successful_changes)
                has_pyproject = any("pyproject.toml" in str(c.file_path) for c in result.successful_changes)

                if has_precommit:
                    console.print("  4. Run [cyan]pre-commit install[/cyan] to activate pre-commit hooks")
                if has_pyproject:
                    console.print("  4. Install development dependencies with your package manager")
            else:
                console.print("\n[bold]Summary:[/bold] No changes were applied.")

            console.print()

        logger.log_operation(
            operation="configuration_apply",
            status="completed" if not dry_run else "dry_run_completed",
            details={
                "changes_count": len(changes),
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


# Template subcommands
template_app = typer.Typer(name="template", help="Manage configuration templates.")
app.add_typer(template_app)


@template_app.command("list")
def template_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
    structured_output: bool = typer.Option(False, "--structured", help="Output structured JSON logs"),
) -> None:
    """List available templates."""
    configure_logging(verbose=verbose, structured_output=structured_output)
    logger = get_logger()

    try:
        logger.info("Listing available templates")

        # Get template manager and load templates
        core_engine = _get_core_engine()

        try:
            templates = core_engine.template_manager.load_templates()
            template_dir = core_engine.template_manager.get_template_directory()
        except TemplateError as e:
            if not structured_output:
                console.print(f"[red]Error:[/red] {e}")
                console.print("[dim]Run 'secuority init' to initialize templates.[/dim]")
            logger.error("Failed to load templates", error=str(e))
            raise typer.Exit(1) from None

        if not structured_output:
            console.print("\n[bold blue]Available Templates[/bold blue]\n")
            console.print(f"[dim]Template directory: {template_dir}[/dim]\n")

        # Template descriptions
        template_descriptions = {
            "pyproject.toml.template": "Modern Python project configuration",
            ".gitignore.template": "Python-specific ignore patterns",
            ".pre-commit-config.yaml.template": "Pre-commit hooks configuration",
            "workflows/security-check.yml": "GitHub Actions security workflow",
            "workflows/quality-check.yml": "GitHub Actions quality workflow",
        }

        if not structured_output:
            template_table = Table(title="Configuration Templates", show_header=True, header_style="bold magenta")
            template_table.add_column("Template", style="cyan", no_wrap=True)
            template_table.add_column("Description", style="dim")
            template_table.add_column("Status", justify="center")

            # Show all expected templates
            for template_name, description in template_descriptions.items():
                exists = template_name in templates
                status_color = "[green]✓ Available[/green]" if exists else "[red]✗ Missing[/red]"
                template_table.add_row(template_name, description, status_color)

                logger.debug(
                    "Template details",
                    template_name=template_name,
                    template_description=description,
                    template_available=exists,
                )

            console.print(template_table)

            if verbose and templates:
                console.print("\n[bold]Template Details:[/bold]")
                for template_name, content in templates.items():
                    console.print(f"  • {template_name}: {len(content)} characters")

            console.print(f"\n[dim]Found {len(templates)} templates[/dim]")
            if len(templates) < len(template_descriptions):
                console.print("[dim]Run 'secuority init' to initialize missing templates.[/dim]")
            console.print()

        logger.info(
            "Template listing completed",
            available_templates=len(templates),
            expected_templates=len(template_descriptions),
        )

    except Exception as e:
        logger.exception("Failed to list templates", error=str(e))
        if not structured_output:
            console.print(f"[red]Error:[/red] Failed to list templates: {e}")
        raise typer.Exit(1) from None


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

        # Get template manager
        core_engine = _get_core_engine()

        if not structured_output:
            console.print("[bold blue]Updating templates...[/bold blue]")

        # Update templates
        if not structured_output:
            with console.status("[bold green]Fetching latest templates..."):
                success = core_engine.template_manager.update_templates()
        else:
            success = core_engine.template_manager.update_templates()

        if success:
            # Get update history
            history = core_engine.template_manager.get_template_history()

            logger.log_operation(
                operation="template_update",
                status="success",
                details={"templates_updated": True, "source": "remote"},
            )

            if not structured_output:
                console.print("[green]✓ Templates updated successfully![/green]")

                if verbose and history:
                    console.print("\n[bold]Update History:[/bold]")
                    for entry in history[-3:]:  # Show last 3 entries
                        action = entry.get("action", "unknown")
                        timestamp = entry.get("timestamp", "unknown")
                        version = entry.get("version", "unknown")
                        console.print(f"  • {action.title()}: {timestamp} (v{version})")

                console.print("[dim]All templates are now up to date.[/dim]")
        else:
            logger.log_operation(
                operation="template_update",
                status="failed",
                details={"error": "Update returned false"},
            )

            if not structured_output:
                console.print("[yellow]⚠ Template update completed with warnings[/yellow]")
                console.print("[dim]Some templates may not have been updated.[/dim]")

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

        # Get template manager
        core_engine = _get_core_engine()
        template_dir = core_engine.template_manager.get_template_directory()

        if not structured_output:
            console.print("[bold blue]Initializing Secuority...[/bold blue]")
            console.print(f"[dim]Template directory: {template_dir}[/dim]\n")

        # Initialize templates
        def verify_installation() -> None:
            core_engine.template_manager.load_templates()

        steps: list[tuple[str, Callable[[], None]]] = [
            ("Creating template directory", lambda: None),
            ("Installing default templates", lambda: core_engine.template_manager.initialize_templates()),
            ("Setting up configuration", lambda: None),
            ("Verifying installation", verify_installation),
        ]

        for i, (step_name, step_func) in enumerate(steps, 1):
            logger.debug(f"Initialization step {i}", step=step_name)
            if not structured_output:
                console.print(f"[dim]• {step_name}...[/dim]")

            try:
                step_func()
            except Exception as e:
                logger.error(f"Step {i} failed", step=step_name, error=str(e))
                if not structured_output:
                    console.print(f"[red]  ✗ Failed: {e}[/red]")
                raise

        # Verify templates were created
        try:
            templates = core_engine.template_manager.load_templates()
            template_count = len(templates)
        except TemplateError:
            template_count = 0

        logger.log_operation(
            operation="secuority_init",
            status="success",
            details={
                "steps_completed": len(steps),
                "template_directory": str(template_dir),
                "templates_created": template_count,
            },
        )

        if not structured_output:
            console.print("\n[green]✓ Secuority initialized successfully![/green]")
            console.print(f"[dim]Created {template_count} templates in {template_dir}[/dim]")

            if verbose:
                console.print("\n[bold]Template Directory Structure:[/bold]")
                console.print(f"  {template_dir}/")
                console.print("  ├── templates/")
                console.print("  │   ├── pyproject.toml.template")
                console.print("  │   ├── .gitignore.template")
                console.print("  │   ├── .pre-commit-config.yaml.template")
                console.print("  │   └── workflows/")
                console.print("  ├── config.yaml")
                console.print("  └── version.json")

            console.print("\n[bold]Next steps:[/bold]")
            console.print("  1. Run [cyan]secuority check[/cyan] to analyze your project")
            console.print("  2. Run [cyan]secuority apply[/cyan] to apply recommended configurations")
            console.print("  3. Use [cyan]secuority template list[/cyan] to see available templates")
            console.print()

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


def main() -> None:
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()
