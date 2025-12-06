"""Unit tests for CLI helper behavior."""

from pathlib import Path

from secuority.cli import main as cli_main
from secuority.models.interfaces import ProjectState, QualityTool, SecurityTool


def test_build_config_file_info_non_python_hides_python_rows(tmp_path: Path) -> None:
    """Non-Python projects should not receive Python-specific file prompts."""
    state = ProjectState(project_path=tmp_path)

    files_info = cli_main._build_config_file_info(state, include_python_files=False)

    file_names = [entry[0] for entry in files_info]
    assert "pyproject.toml" not in file_names
    assert "requirements.txt" not in file_names
    assert "setup.py" not in file_names
    assert ".gitignore" in file_names
    assert "SECURITY.md" in file_names


def test_build_recommendations_skips_python_specific_items(tmp_path: Path) -> None:
    """Python-only recommendations should be skipped when project is not Python."""
    state = ProjectState(project_path=tmp_path)
    state.has_gitignore = False
    state.security_tools = dict.fromkeys(SecurityTool, False)
    state.quality_tools = dict.fromkeys(QualityTool, False)

    recommendations = cli_main._build_recommendations(state, github_analysis=None, python_project=False)

    combined = " ".join(recommendations).lower()
    assert "pyproject" not in combined
    assert "bandit" not in combined
    assert "ruff" not in combined
    assert "gitignore" in combined
