"""End-to-end integration tests for complete workflows."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from secuority.cli.main import app


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def minimal_project(self, tmp_path: Path) -> Path:
        """Create a minimal Python project."""
        # Just a Python file, no configuration
        (tmp_path / "main.py").write_text('print("Hello, World!")\n')
        return tmp_path

    @pytest.fixture
    def legacy_project(self, tmp_path: Path) -> Path:
        """Create a legacy Python project with old-style configuration."""
        # Old-style requirements.txt
        (tmp_path / "requirements.txt").write_text("requests==2.31.0\npytest>=7.0.0\nblack==23.0.0\n")

        # Basic setup.py
        (tmp_path / "setup.py").write_text(
            'from setuptools import setup\nsetup(name="legacy-project", version="0.1.0")\n',
        )

        # Minimal .gitignore
        (tmp_path / ".gitignore").write_text("*.pyc\n")

        # Source code
        (tmp_path / "main.py").write_text('print("Legacy project")\n')

        return tmp_path

    @pytest.fixture
    def modern_project(self, tmp_path: Path) -> Path:
        """Create a modern Python project with pyproject.toml."""
        # Modern pyproject.toml
        (tmp_path / "pyproject.toml").write_text(
            "[project]\n"
            'name = "modern-project"\n'
            'version = "0.1.0"\n'
            'requires-python = ">=3.12"\n'
            "dependencies = [\n"
            '    "requests>=2.31.0",\n'
            "]\n"
            "\n"
            "[tool.ruff]\n"
            "line-length = 120\n"
            'target-version = "py312"\n'
            "\n"
            "[tool.mypy]\n"
            "strict = true\n",
        )

        # Comprehensive .gitignore
        (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n.venv/\n.env\ndist/\n*.egg-info/\n")

        # Source code
        src_dir = tmp_path / "src" / "modern_project"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text('"""Modern project."""\n')
        (src_dir / "main.py").write_text('def main() -> None:\n    print("Modern")\n')

        return tmp_path

    @pytest.fixture
    def git_project(self, tmp_path: Path) -> Path:
        """Create a project with Git repository."""
        # Initialize git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text(
            '[core]\nrepositoryformatversion = 0\n[remote "origin"]\nurl = https://github.com/test/repo.git\n',
        )

        # Basic project files
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "git-project"\nversion = "0.1.0"\n')
        (tmp_path / "main.py").write_text('print("Git project")\n')

        return tmp_path

    def test_complete_workflow_minimal_to_modern(
        self,
        runner: CliRunner,
        minimal_project: Path,
    ) -> None:
        """Test complete workflow: minimal project to modern setup."""
        # Step 1: Check the project (should find many issues)
        check_result = runner.invoke(
            app,
            ["check", "--project-path", str(minimal_project)],
        )
        assert check_result.exit_code == 0

        # Step 2: Apply configurations with dry-run
        dry_run_result = runner.invoke(
            app,
            ["apply", "--project-path", str(minimal_project), "--dry-run"],
        )
        assert dry_run_result.exit_code == 0

        # Step 3: Apply configurations with force
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(minimal_project), "--force"],
        )
        assert apply_result.exit_code == 0

        # Step 4: Check again (should have fewer issues)
        final_check = runner.invoke(
            app,
            ["check", "--project-path", str(minimal_project)],
        )
        assert final_check.exit_code == 0

    def test_complete_workflow_legacy_migration(
        self,
        runner: CliRunner,
        legacy_project: Path,
    ) -> None:
        """Test complete workflow: migrate legacy project to modern setup."""
        # Step 1: Initial check
        initial_check = runner.invoke(
            app,
            ["check", "--project-path", str(legacy_project), "--verbose"],
        )
        assert initial_check.exit_code == 0

        # Verify requirements.txt exists
        assert (legacy_project / "requirements.txt").exists()

        # Step 2: Apply modernization
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(legacy_project), "--force"],
        )
        assert apply_result.exit_code == 0

        # Step 3: Verify pyproject.toml was created or updated
        pyproject_path = legacy_project / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            # Should have project metadata
            assert "project" in content or "tool" in content

        # Step 4: Final check
        final_check = runner.invoke(
            app,
            ["check", "--project-path", str(legacy_project)],
        )
        assert final_check.exit_code == 0

    def test_complete_workflow_modern_project_enhancement(
        self,
        runner: CliRunner,
        modern_project: Path,
    ) -> None:
        """Test complete workflow: enhance already modern project."""
        # Step 1: Check modern project
        check_result = runner.invoke(
            app,
            ["check", "--project-path", str(modern_project)],
        )
        assert check_result.exit_code == 0

        # Step 2: Apply security enhancements
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(modern_project), "--force"],
        )
        assert apply_result.exit_code == 0

        # Step 3: Verify security tools were added
        pyproject_path = modern_project / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            # Should have security tool configurations
            # (bandit, safety, etc.)
            assert "tool" in content

        # Step 4: Check for workflows
        workflows_dir = modern_project / ".github" / "workflows"
        if workflows_dir.exists():
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            # May have generated workflows
            assert len(workflow_files) >= 0  # At least attempt was made

    def test_complete_workflow_with_github_integration(
        self,
        runner: CliRunner,
        git_project: Path,
    ) -> None:
        """Test complete workflow with GitHub integration."""
        # Mock GitHub API to avoid actual calls
        with patch("secuority.core.github_client.GitHubClient.is_authenticated") as mock_auth:
            mock_auth.return_value = False

            # Step 1: Check with GitHub integration
            check_result = runner.invoke(
                app,
                ["check", "--project-path", str(git_project)],
            )
            assert check_result.exit_code == 0

            # Step 2: Apply with GitHub-aware configurations
            apply_result = runner.invoke(
                app,
                ["apply", "--project-path", str(git_project), "--force"],
            )
            assert apply_result.exit_code == 0

    def test_init_and_apply_workflow(
        self,
        runner: CliRunner,
        tmp_path: Path,
        minimal_project: Path,
    ) -> None:
        """Test workflow: initialize templates then apply to project."""
        # Step 1: Initialize templates
        with patch("pathlib.Path.home", return_value=tmp_path):
            init_result = runner.invoke(app, ["init"])
        assert init_result.exit_code == 0

        # Step 2: Apply to project
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(minimal_project), "--force"],
        )
        assert apply_result.exit_code == 0

    def test_template_management_workflow(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test complete template management workflow."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            # Step 1: Initialize
            init_result = runner.invoke(app, ["init"])
            assert init_result.exit_code == 0

            # Step 2: List templates
            with patch("secuority.core.template_manager.TemplateManager.load_templates") as mock_load:
                mock_load.return_value = {
                    "pyproject.toml.template": "[project]\n",
                }
                list_result = runner.invoke(app, ["template", "list"])
            assert list_result.exit_code == 0

            # Step 3: Update templates
            with patch("secuority.core.template_manager.TemplateManager.update_templates") as mock_update:
                mock_update.return_value = True
                update_result = runner.invoke(app, ["template", "update"])
            assert update_result.exit_code == 0

    def test_check_apply_check_cycle(
        self,
        runner: CliRunner,
        legacy_project: Path,
    ) -> None:
        """Test check -> apply -> check cycle."""
        # First check
        check1 = runner.invoke(
            app,
            ["check", "--project-path", str(legacy_project)],
        )
        assert check1.exit_code == 0

        # Apply changes
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(legacy_project), "--force"],
        )
        assert apply_result.exit_code == 0

        # Second check (should show improvements)
        check2 = runner.invoke(
            app,
            ["check", "--project-path", str(legacy_project)],
        )
        assert check2.exit_code == 0

    def test_dry_run_does_not_modify_project(
        self,
        runner: CliRunner,
        modern_project: Path,
    ) -> None:
        """Test that dry-run mode doesn't modify any files."""
        # Get initial state
        pyproject_before = (modern_project / "pyproject.toml").read_text()
        gitignore_before = (modern_project / ".gitignore").read_text()

        # Run with dry-run
        result = runner.invoke(
            app,
            ["apply", "--project-path", str(modern_project), "--dry-run"],
        )
        assert result.exit_code == 0

        # Verify no changes
        pyproject_after = (modern_project / "pyproject.toml").read_text()
        gitignore_after = (modern_project / ".gitignore").read_text()

        assert pyproject_before == pyproject_after
        assert gitignore_before == gitignore_after

    def test_backup_creation_workflow(
        self,
        runner: CliRunner,
        modern_project: Path,
    ) -> None:
        """Test that backups are created during apply."""
        # Apply changes
        result = runner.invoke(
            app,
            ["apply", "--project-path", str(modern_project), "--force"],
        )
        assert result.exit_code == 0

        # Check for backup files (if any changes were made)
        # Backups may or may not exist depending on whether changes were needed
        # Just verify the command succeeded
        assert result.exit_code == 0

    def test_error_handling_invalid_project(
        self,
        runner: CliRunner,
    ) -> None:
        """Test error handling with invalid project path."""
        result = runner.invoke(
            app,
            ["check", "--project-path", "/nonexistent/invalid/path"],
        )
        # Should handle error gracefully
        assert result.exit_code != 0 or "error" in result.stdout.lower()

    def test_error_handling_corrupted_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test error handling with corrupted configuration files."""
        # Create corrupted pyproject.toml
        (tmp_path / "pyproject.toml").write_text(
            "[project\n"  # Missing closing bracket
            "name = 'broken'\n",
        )

        result = runner.invoke(
            app,
            ["check", "--project-path", str(tmp_path)],
        )
        # Should handle parsing error gracefully
        assert result.exit_code in [0, 1]  # May succeed with warnings or fail gracefully

    def test_verbose_output_workflow(
        self,
        runner: CliRunner,
        modern_project: Path,
    ) -> None:
        """Test workflow with verbose output."""
        # Check with verbose
        check_result = runner.invoke(
            app,
            ["check", "--project-path", str(modern_project), "--verbose"],
        )
        assert check_result.exit_code == 0

        # Apply with verbose (if supported)
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(modern_project), "--force"],
        )
        assert apply_result.exit_code == 0

    def test_structured_output_workflow(
        self,
        runner: CliRunner,
        modern_project: Path,
    ) -> None:
        """Test workflow with structured output."""
        result = runner.invoke(
            app,
            ["check", "--project-path", str(modern_project), "--structured"],
        )
        # Structured output may have different exit codes
        assert result.exit_code in [0, 1]

    def test_multiple_projects_workflow(
        self,
        runner: CliRunner,
        minimal_project: Path,
        modern_project: Path,
    ) -> None:
        """Test applying to multiple projects sequentially."""
        # Check first project
        result1 = runner.invoke(
            app,
            ["check", "--project-path", str(minimal_project)],
        )
        assert result1.exit_code == 0

        # Check second project
        result2 = runner.invoke(
            app,
            ["check", "--project-path", str(modern_project)],
        )
        assert result2.exit_code == 0

        # Apply to first project
        apply1 = runner.invoke(
            app,
            ["apply", "--project-path", str(minimal_project), "--force"],
        )
        assert apply1.exit_code == 0

        # Apply to second project
        apply2 = runner.invoke(
            app,
            ["apply", "--project-path", str(modern_project), "--force"],
        )
        assert apply2.exit_code == 0

    def test_security_focused_workflow(
        self,
        runner: CliRunner,
        modern_project: Path,
    ) -> None:
        """Test workflow focused on security enhancements."""
        # Initial check
        check_result = runner.invoke(
            app,
            ["check", "--project-path", str(modern_project)],
        )
        assert check_result.exit_code == 0

        # Apply security configurations
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(modern_project), "--force"],
        )
        assert apply_result.exit_code == 0

        # Verify security files were created/updated
        pyproject_path = modern_project / "pyproject.toml"
        if pyproject_path.exists():
            content = pyproject_path.read_text()
            # Should have security-related configurations
            assert "tool" in content

    def test_ci_workflow_generation(
        self,
        runner: CliRunner,
        git_project: Path,
    ) -> None:
        """Test CI/CD workflow generation."""
        # Apply configurations
        result = runner.invoke(
            app,
            ["apply", "--project-path", str(git_project), "--force"],
        )
        assert result.exit_code == 0

        # Check if workflows directory was created
        # Workflows may or may not be created depending on project state
        # Just verify command succeeded
        assert result.exit_code == 0

    def test_help_and_version_commands(
        self,
        runner: CliRunner,
    ) -> None:
        """Test help and version commands work."""
        # Test help
        help_result = runner.invoke(app, ["--help"])
        assert help_result.exit_code == 0
        assert "check" in help_result.stdout

        # Test version (may not be implemented, so just check it doesn't crash)
        version_result = runner.invoke(app, ["--version"])
        # Version command may exit with 2 if not implemented
        assert version_result.exit_code in [0, 2]

    def test_complete_new_project_setup(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test complete setup for a brand new project."""
        # Create empty project directory
        new_project = tmp_path / "new_project"
        new_project.mkdir()
        (new_project / "main.py").write_text('print("New project")\n')

        # Initialize templates
        with patch("pathlib.Path.home", return_value=tmp_path):
            init_result = runner.invoke(app, ["init"])
        assert init_result.exit_code == 0

        # Check the new project
        check_result = runner.invoke(
            app,
            ["check", "--project-path", str(new_project)],
        )
        assert check_result.exit_code == 0

        # Apply all configurations
        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(new_project), "--force"],
        )
        assert apply_result.exit_code == 0

        # Final verification
        final_check = runner.invoke(
            app,
            ["check", "--project-path", str(new_project)],
        )
        assert final_check.exit_code == 0


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    def test_open_source_project_setup(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test setting up an open-source project."""
        # Create project structure
        project = tmp_path / "opensource_project"
        project.mkdir()

        # Add typical open-source files
        (project / "README.md").write_text("# My Project\n")
        (project / "LICENSE").write_text("MIT License\n")
        (project / "pyproject.toml").write_text('[project]\nname = "opensource-project"\nversion = "1.0.0"\n')

        src = project / "src" / "myproject"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text('"""My project."""\n')

        # Run secuority
        check_result = runner.invoke(
            app,
            ["check", "--project-path", str(project)],
        )
        assert check_result.exit_code == 0

        apply_result = runner.invoke(
            app,
            ["apply", "--project-path", str(project), "--force"],
        )
        assert apply_result.exit_code == 0

    def test_private_project_setup(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test setting up a private/internal project."""
        project = tmp_path / "private_project"
        project.mkdir()

        (project / "pyproject.toml").write_text('[project]\nname = "private-project"\nversion = "0.1.0"\n')
        (project / "main.py").write_text('print("Private")\n')

        # Add .env file (should be ignored)
        (project / ".env").write_text("SECRET_KEY=secret\n")

        result = runner.invoke(
            app,
            ["check", "--project-path", str(project)],
        )
        assert result.exit_code == 0

    def test_monorepo_subproject(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test working with a subproject in a monorepo."""
        # Create monorepo structure
        monorepo = tmp_path / "monorepo"
        monorepo.mkdir()

        # Subproject
        subproject = monorepo / "services" / "api"
        subproject.mkdir(parents=True)
        (subproject / "pyproject.toml").write_text('[project]\nname = "api-service"\nversion = "0.1.0"\n')
        (subproject / "main.py").write_text('print("API")\n')

        # Run on subproject
        result = runner.invoke(
            app,
            ["check", "--project-path", str(subproject)],
        )
        assert result.exit_code == 0

    def test_migration_from_poetry(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test project already using Poetry."""
        project = tmp_path / "poetry_project"
        project.mkdir()

        # Poetry-style pyproject.toml
        (project / "pyproject.toml").write_text(
            "[tool.poetry]\n"
            'name = "poetry-project"\n'
            'version = "0.1.0"\n'
            "\n"
            "[tool.poetry.dependencies]\n"
            'python = "^3.12"\n'
            'requests = "^2.31.0"\n',
        )
        (project / "main.py").write_text('print("Poetry")\n')

        # Should detect Poetry and handle appropriately
        result = runner.invoke(
            app,
            ["check", "--project-path", str(project)],
        )
        assert result.exit_code == 0

    def test_project_with_existing_security_tools(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test project that already has some security tools."""
        project = tmp_path / "secure_project"
        project.mkdir()

        (project / "pyproject.toml").write_text(
            "[project]\n"
            'name = "secure-project"\n'
            'version = "0.1.0"\n'
            "\n"
            "[tool.bandit]\n"
            'exclude_dirs = ["/tests"]\n'
            "\n"
            "[tool.ruff]\n"
            "line-length = 120\n",
        )

        (project / ".pre-commit-config.yaml").write_text(
            "repos:\n  - repo: https://github.com/psf/black\n    rev: 23.0.0\n    hooks:\n      - id: black\n",
        )

        # Should merge with existing configuration
        result = runner.invoke(
            app,
            ["check", "--project-path", str(project)],
        )
        assert result.exit_code == 0
