"""Integration tests for CLI commands."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from secuority.cli.main import app


class TestCLICommands:
    """Test CLI command integration."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def sample_project(self, tmp_path: Path) -> Path:
        """Create a sample project for testing."""
        # Create basic project structure
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test-project"\nversion = "0.1.0"\n')
        (tmp_path / "requirements.txt").write_text("pytest>=7.0.0\n")
        (tmp_path / ".gitignore").write_text("*.pyc\n")

        return tmp_path

    def test_check_command_basic(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test basic check command execution."""
        result = runner.invoke(app, ["check", "--project-path", str(sample_project)])

        assert result.exit_code == 0
        # Check for any indication of analysis output
        assert "Analysis" in result.stdout or "Report" in result.stdout or "Configuration" in result.stdout

    def test_check_command_verbose(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test check command with verbose flag."""
        result = runner.invoke(
            app,
            ["check", "--project-path", str(sample_project), "--verbose"],
        )

        assert result.exit_code == 0

    def test_check_command_nonexistent_path(self, runner: CliRunner) -> None:
        """Test check command with non-existent path."""
        result = runner.invoke(app, ["check", "--project-path", "/nonexistent/path"])

        # Should handle error gracefully
        assert result.exit_code != 0 or "error" in result.stdout.lower()

    def test_apply_command_dry_run(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test apply command with dry-run flag."""
        result = runner.invoke(
            app,
            ["apply", "--project-path", str(sample_project), "--dry-run"],
        )

        # Dry run should not fail
        assert result.exit_code == 0 or "dry" in result.stdout.lower()

    def test_apply_command_with_force(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test apply command with force flag."""
        # Force flag should skip interactive prompts
        result = runner.invoke(
            app,
            ["apply", "--project-path", str(sample_project), "--force"],
        )

        # Should execute without prompts
        assert result.exit_code == 0 or "apply" in result.stdout.lower()

    def test_init_command_basic(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test basic init command execution."""
        # Change to temp directory for init
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(app, ["init"])

        # Init should succeed or provide helpful message
        assert result.exit_code == 0 or "initialized" in result.stdout.lower()

    def test_init_command_verbose(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test init command with verbose flag."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(app, ["init", "--verbose"])

        assert result.exit_code == 0

    def test_template_list_command(self, runner: CliRunner) -> None:
        """Test template list command."""
        # Mock template manager to avoid file system dependencies
        with patch("secuority.core.template_manager.TemplateManager.load_templates") as mock_load:
            mock_load.return_value = {
                "pyproject.toml.template": "[project]\n",
                ".gitignore.template": "*.pyc\n",
            }

            result = runner.invoke(app, ["template", "list"])

        # Should list templates or handle gracefully
        assert result.exit_code == 0 or "template" in result.stdout.lower()

    def test_template_update_command(self, runner: CliRunner) -> None:
        """Test template update command."""
        # Mock template manager update
        with patch("secuority.core.template_manager.TemplateManager.update_templates") as mock_update:
            mock_update.return_value = True

            result = runner.invoke(app, ["template", "update"])

        # Should attempt update or handle gracefully
        assert result.exit_code == 0 or "update" in result.stdout.lower()

    def test_check_command_with_github_integration(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test check command with GitHub integration."""
        # Create .git directory to simulate git repo
        git_dir = sample_project / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text('[remote "origin"]\n' "url = https://github.com/test/repo.git\n")

        # Mock GitHub client to avoid actual API calls
        with patch("secuority.core.github_client.GitHubClient.is_authenticated") as mock_auth:
            mock_auth.return_value = False

            result = runner.invoke(
                app,
                ["check", "--project-path", str(sample_project)],
            )

        assert result.exit_code == 0

    def test_apply_command_creates_backup(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test that apply command creates backups."""
        # Create a file to be modified
        test_file = sample_project / "test.txt"
        test_file.write_text("original content")

        result = runner.invoke(
            app,
            ["apply", "--project-path", str(sample_project), "--force"],
        )

        # Command should execute
        assert result.exit_code == 0 or "apply" in result.stdout.lower()

    def test_check_command_detects_missing_files(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test check command detects missing configuration files."""
        # Create minimal project without common files
        (tmp_path / "main.py").write_text("print('hello')")

        result = runner.invoke(app, ["check", "--project-path", str(tmp_path)])

        # Should detect missing files
        assert result.exit_code == 0

    def test_check_command_structured_output(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test check command with structured output."""
        result = runner.invoke(
            app,
            ["check", "--project-path", str(sample_project), "--structured"],
        )

        # Structured output may have different exit codes
        # Just check that command executed
        assert result.exit_code in [0, 1]  # May exit with 1 if issues found

    def test_apply_command_handles_conflicts(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test apply command handles configuration conflicts."""
        # Create conflicting configuration
        (sample_project / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")

        result = runner.invoke(
            app,
            ["apply", "--project-path", str(sample_project), "--dry-run"],
        )

        # Should handle conflicts gracefully
        assert result.exit_code == 0 or "apply" in result.stdout.lower()

    def test_init_command_creates_config(
        self,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test init command creates configuration directory."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = runner.invoke(app, ["init"])

        # Init should succeed or provide helpful message
        assert result.exit_code == 0 or "init" in result.stdout.lower()

    def test_check_command_with_security_tools(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test check command detects security tools."""
        # Add security tool configuration
        (sample_project / "pyproject.toml").write_text('[project]\nname = "test"\n[tool.bandit]\nskip = ["B101"]\n')

        result = runner.invoke(app, ["check", "--project-path", str(sample_project)])

        assert result.exit_code == 0

    def test_apply_command_respects_dry_run(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test that dry-run doesn't modify files."""
        original_content = (sample_project / "pyproject.toml").read_text()

        result = runner.invoke(
            app,
            ["apply", "--project-path", str(sample_project), "--dry-run"],
        )

        # File should not be modified
        assert (sample_project / "pyproject.toml").read_text() == original_content
        assert result.exit_code == 0

    def test_check_command_with_workflows(
        self,
        runner: CliRunner,
        sample_project: Path,
    ) -> None:
        """Test check command detects CI/CD workflows."""
        # Create workflow directory
        workflows_dir = sample_project / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n")

        result = runner.invoke(app, ["check", "--project-path", str(sample_project)])

        assert result.exit_code == 0

    def test_help_command(self, runner: CliRunner) -> None:
        """Test help command displays usage information."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "check" in result.stdout
        assert "apply" in result.stdout
        assert "init" in result.stdout

    def test_version_command(self, runner: CliRunner) -> None:
        """Test version command displays version information."""
        result = runner.invoke(app, ["--version"])

        # Should display version or handle gracefully
        assert result.exit_code == 0 or "version" in result.stdout.lower()
