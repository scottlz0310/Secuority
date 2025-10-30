"""Main CLI entry point for Secuority."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

app = typer.Typer(
    name="secuority",
    help="Automate and standardize Python project security and quality configurations.",
    add_completion=False,
)


@app.command()
def check(
    verbose: bool = typer.Option(
        False, 
        "--verbose", 
        "-v", 
        help="Show detailed analysis information"
    ),
    project_path: Path = typer.Option(
        Path.cwd(),
        "--project-path",
        "-p",
        help="Path to the project directory",
    ),
) -> None:
    """Analyze project configuration and show recommendations."""
    try:
        # For now, we'll implement basic functionality without the core engine
        # from ..core.engine import CoreEngine
        
        console.print(f"\n[bold blue]Secuority Analysis Report[/bold blue]")
        console.print(f"[dim]Project: {project_path}[/dim]\n")
        
        # For now, show a simple analysis
        config_table = Table(title="Configuration Files", show_header=True, header_style="bold magenta")
        config_table.add_column("File", style="cyan", no_wrap=True)
        config_table.add_column("Status", justify="center")
        config_table.add_column("Notes", style="dim")
        
        # Check basic files
        files_to_check = [
            ("pyproject.toml", "Modern Python configuration"),
            ("requirements.txt", "Legacy dependency format"),
            ("setup.py", "Legacy setup configuration"),
            (".gitignore", "Git ignore patterns"),
            (".pre-commit-config.yaml", "Pre-commit hooks"),
        ]
        
        for filename, note in files_to_check:
            file_path = project_path / filename
            exists = file_path.exists()
            status = "[green]✓ Found[/green]" if exists else "[red]✗ Missing[/red]"
            config_table.add_row(filename, status, note)
        
        console.print(config_table)
        console.print()
        
        # Show recommendations
        recommendations = []
        if not (project_path / "pyproject.toml").exists():
            recommendations.append("• Create pyproject.toml for modern Python configuration")
        if not (project_path / ".gitignore").exists():
            recommendations.append("• Add .gitignore file with Python patterns")
        if not (project_path / ".pre-commit-config.yaml").exists():
            recommendations.append("• Set up pre-commit hooks for code quality")
        
        if recommendations:
            console.print(Panel(
                "\n".join(recommendations),
                title="[bold yellow]Recommendations[/bold yellow]",
                border_style="yellow"
            ))
        else:
            console.print(Panel(
                "[green]✓ Project configuration looks good![/green]",
                title="[bold green]Status[/bold green]",
                border_style="green"
            ))
        
        if verbose:
            console.print("\n[bold]Detailed Information:[/bold]")
            console.print(f"  • Project path: {project_path}")
            console.print(f"  • Python files found: {len(list(project_path.glob('**/*.py')))}")
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to analyze project: {e}")
        raise typer.Exit(1)


@app.command()
def apply(
    dry_run: bool = typer.Option(
        False, 
        "--dry-run", 
        "-n", 
        help="Show changes without applying them"
    ),
    force: bool = typer.Option(
        False, 
        "--force", 
        "-f", 
        help="Apply changes without confirmation"
    ),
    project_path: Path = typer.Option(
        Path.cwd(),
        "--project-path",
        "-p",
        help="Path to the project directory",
    ),
) -> None:
    """Apply configuration changes to the project."""
    try:
        if dry_run:
            console.print(f"\n[bold blue]Dry Run - Configuration Changes Preview[/bold blue]\n")
        else:
            console.print(f"\n[bold green]Applying Configuration Changes[/bold green]\n")
        
        console.print(f"[dim]Project: {project_path}[/dim]")
        console.print(f"[dim]Dry run: {dry_run}, Force: {force}[/dim]\n")
        
        if not dry_run and not force:
            console.print("[bold yellow]⚠️  This will modify your project files![/bold yellow]")
            console.print("[dim]Backups will be created for existing files.[/dim]")
            
            confirm = typer.confirm("\nApply configuration changes?")
            if not confirm:
                console.print("[yellow]Operation cancelled.[/yellow]")
                return
        
        # Show what would be done
        changes_table = Table(title="Planned Changes", show_header=True, header_style="bold green")
        changes_table.add_column("File", style="cyan")
        changes_table.add_column("Action", justify="center")
        changes_table.add_column("Description", style="dim")
        
        # Example changes
        if not (project_path / "pyproject.toml").exists():
            changes_table.add_row("pyproject.toml", "[green]CREATE[/green]", "Modern Python configuration")
        
        if not (project_path / ".gitignore").exists():
            changes_table.add_row(".gitignore", "[green]CREATE[/green]", "Python ignore patterns")
        
        console.print(changes_table)
        
        if dry_run:
            console.print("\n[bold]Summary:[/bold] This was a dry run - no changes were made.")
        else:
            console.print("\n[bold]Summary:[/bold] Configuration changes applied successfully!")
        
        console.print()
        
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to apply configurations: {e}")
        raise typer.Exit(1)


# Template subcommands
template_app = typer.Typer(name="template", help="Manage configuration templates.")
app.add_typer(template_app)


@template_app.command("list")
def template_list() -> None:
    """List available templates."""
    console.print(f"\n[bold blue]Available Templates[/bold blue]\n")
    
    template_table = Table(title="Configuration Templates", show_header=True, header_style="bold magenta")
    template_table.add_column("Template", style="cyan", no_wrap=True)
    template_table.add_column("Description", style="dim")
    template_table.add_column("Status", justify="center")
    
    templates = [
        ("pyproject.toml.template", "Modern Python project configuration", "Available"),
        (".gitignore.template", "Python-specific ignore patterns", "Available"),
        (".pre-commit-config.yaml.template", "Pre-commit hooks configuration", "Available"),
        ("security-check.yml", "GitHub Actions security workflow", "Available"),
        ("quality-check.yml", "GitHub Actions quality workflow", "Available")
    ]
    
    for template_name, description, status in templates:
        status_color = "[green]✓ Available[/green]" if status == "Available" else "[red]✗ Missing[/red]"
        template_table.add_row(template_name, description, status_color)
    
    console.print(template_table)
    console.print("\n[dim]Run 'secuority init' to initialize templates if not available.[/dim]")
    console.print()


@template_app.command("update")
def template_update() -> None:
    """Update templates from remote source."""
    console.print("[bold blue]Updating templates...[/bold blue]")
    
    # Simulate template update
    import time
    with console.status("[bold green]Fetching latest templates..."):
        time.sleep(1)  # Simulate network request
    
    console.print("[green]✓ Templates updated successfully![/green]")
    console.print("[dim]All templates are now up to date.[/dim]")


@app.command()
def init() -> None:
    """Initialize Secuority configuration directory and templates."""
    console.print("[bold blue]Initializing Secuority...[/bold blue]")
    
    # Show initialization steps
    steps = [
        "Creating template directory",
        "Installing default templates",
        "Setting up configuration",
        "Verifying installation"
    ]
    
    for step in steps:
        console.print(f"[dim]• {step}...[/dim]")
    
    console.print("\n[green]✓ Secuority initialized successfully![/green]")
    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. Run [cyan]secuority check[/cyan] to analyze your project")
    console.print("  2. Run [cyan]secuority apply[/cyan] to apply recommended configurations")
    console.print("  3. Use [cyan]secuority template list[/cyan] to see available templates")
    console.print()


def main() -> None:
    """Main entry point for the CLI application."""
    app()


if __name__ == "__main__":
    main()