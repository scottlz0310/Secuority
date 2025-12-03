"""Unit tests for the Python language analyzer."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from secuority.core.languages.python import PythonAnalyzer


class TestPythonAnalyzer:
    """Validate Python-specific language detection and parsing."""

    def _write_files(self, base_path: Path, filenames: list[str]) -> None:
        for name in filenames:
            file_path = base_path / name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("", encoding="utf-8")

    def test_detect_caps_confidence_at_one_with_multiple_indicators(self, tmp_path: Path) -> None:
        analyzer = PythonAnalyzer()
        self._write_files(
            tmp_path,
            [
                "pyproject.toml",
                "requirements.txt",
                "setup.py",
                "poetry.lock",
                "Pipfile",
            ],
        )
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n", encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "__init__.py").write_text("print('ok')\n", encoding="utf-8")

        result = analyzer.detect(tmp_path)

        assert result.language == "python"
        assert result.confidence == pytest.approx(1.0)
        assert "pyproject.toml" in result.indicators
        assert "requirements.txt" in result.indicators
        assert any(indicator.endswith(".py files") for indicator in result.indicators)

    def test_detect_tools_merges_pyproject_and_individual_configs(self, tmp_path: Path) -> None:
        analyzer = PythonAnalyzer()
        pyproject_content = textwrap.dedent(
            """
            [project]
            dependencies = ["pytest>=7.4"]

            [tool.ruff]
            [tool.basedpyright]
            [tool.bandit]
            [tool.black]
            [tool.poetry]
            [tool.uv]
            """,
        ).strip()
        (tmp_path / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")

        self._write_files(
            tmp_path,
            [
                "mypy.ini",
                ".flake8",
                ".pylintrc",
                "bandit.yaml",
                "pytest.ini",
                "tox.ini",
                "poetry.lock",
                "Pipfile",
                "pdm.lock",
            ],
        )

        config_files = analyzer.detect_config_files(tmp_path)
        tools = analyzer.detect_tools(tmp_path, config_files)

        assert tools["ruff"]
        assert tools["basedpyright"]
        assert tools["bandit"]
        assert tools["black"]
        assert tools["pytest"]
        assert tools["mypy"]
        assert tools["pylint"]
        assert tools["tox"]
        assert tools["poetry"]
        assert tools["pipenv"]
        assert tools["pdm"]
        assert tools["uv"]

    def test_parse_dependencies_combines_pyproject_and_requirements(self, tmp_path: Path) -> None:
        analyzer = PythonAnalyzer()
        (tmp_path / "pyproject.toml").write_text(
            textwrap.dedent(
                """
                [project]
                dependencies = [
                    "requests>=2.0",
                    "pytest==8.0",
                ]
                """,
            ).strip(),
            encoding="utf-8",
        )
        (tmp_path / "requirements.txt").write_text(
            textwrap.dedent(
                """
                requests==2.31.0
                flask==3.0.0
                """,
            ).strip(),
            encoding="utf-8",
        )

        config_files = analyzer.detect_config_files(tmp_path)
        deps = analyzer.parse_dependencies(tmp_path, config_files)

        assert set(deps) == {"requests", "pytest", "flask"}

    def test_detect_config_files_report_expected_types(self, tmp_path: Path) -> None:
        analyzer = PythonAnalyzer()
        self._write_files(tmp_path, ["bandit.yaml", "setup.py", "requirements.txt"])

        config_files = analyzer.detect_config_files(tmp_path)
        config_map = {cfg.name: cfg for cfg in config_files}

        assert config_map["bandit.yaml"].file_type == "yaml" and config_map["bandit.yaml"].exists
        assert config_map["setup.py"].file_type == "python" and config_map["setup.py"].exists
        assert config_map["requirements.txt"].file_type == "text" and config_map["requirements.txt"].exists
