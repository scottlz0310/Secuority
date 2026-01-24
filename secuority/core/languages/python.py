"""Python language analyzer implementation."""

import re
import tomllib
from pathlib import Path
from typing import Any, cast

from secuority.utils.logger import debug

from .base import (
    ConfigFile,
    LanguageAnalyzer,
    LanguageDetectionResult,
    ToolRecommendation,
    ToolStatusMap,
)


class PythonAnalyzer(LanguageAnalyzer):
    """Analyzer for Python projects.

    Detects Python configuration files, tools, and provides recommendations
    for Python-specific quality and security tools.
    """

    def _get_language_name(self) -> str:
        """Get the name of this language."""
        return "python"

    @staticmethod
    def _normalize_dependency_list(raw_value: object) -> list[str]:
        if not isinstance(raw_value, list):
            return []
        items = cast(list[object], raw_value)
        return [item for item in items if isinstance(item, str) and item]

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses Python.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score
        """
        indicators: list[str] = []
        confidence = 0.0

        # Check for pyproject.toml
        if (project_path / "pyproject.toml").exists():
            indicators.append("pyproject.toml")
            confidence += 0.4

        # Check for requirements.txt
        if (project_path / "requirements.txt").exists():
            indicators.append("requirements.txt")
            confidence += 0.3

        # Check for setup.py
        if (project_path / "setup.py").exists():
            indicators.append("setup.py")
            confidence += 0.3

        # Check for .py files
        py_files = list(project_path.glob("**/*.py"))
        if py_files:
            indicators.append(f"{len(py_files)} .py files")
            confidence += 0.5

        # Check for poetry.lock
        if (project_path / "poetry.lock").exists():
            indicators.append("poetry.lock")
            confidence += 0.2

        # Check for Pipfile
        if (project_path / "Pipfile").exists():
            indicators.append("Pipfile")
            confidence += 0.2

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        return LanguageDetectionResult(
            language="python",
            confidence=confidence,
            indicators=indicators,
        )

    def get_config_file_patterns(self) -> dict[str, str]:
        """Get configuration file patterns for Python.

        Returns:
            Dictionary mapping file names to descriptions
        """
        return {
            "pyproject.toml": "Python project configuration",
            "requirements.txt": "Python dependencies (pip)",
            "setup.py": "Python package setup script",
            "setup.cfg": "Python package configuration",
            "tox.ini": "Tox testing configuration",
            "pytest.ini": "Pytest configuration",
            "mypy.ini": "MyPy type checker configuration",
            ".flake8": "Flake8 linter configuration",
            ".pylintrc": "Pylint configuration",
            "bandit.yaml": "Bandit security configuration",
            "poetry.lock": "Poetry dependencies lock file",
            "Pipfile": "Pipenv dependencies",
            "Pipfile.lock": "Pipenv dependencies lock file",
            "pdm.lock": "PDM dependencies lock file",
        }

    def detect_config_files(self, project_path: Path) -> list[ConfigFile]:
        """Detect configuration files present in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            List of ConfigFile objects for files that exist
        """
        patterns = self.get_config_file_patterns()
        config_files: list[ConfigFile] = []

        for filename in patterns:
            file_path = project_path / filename
            file_type = self._determine_file_type(filename)

            config_files.append(
                ConfigFile(
                    name=filename,
                    path=file_path if file_path.exists() else None,
                    exists=file_path.exists(),
                    file_type=file_type,
                ),
            )

        return config_files

    def _determine_file_type(self, filename: str) -> str:
        """Determine file type from filename."""
        suffix_map = {
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".ini": "ini",
            ".py": "python",
            ".txt": "text",
            ".lock": "lock",
        }
        for suffix, file_type in suffix_map.items():
            if filename.endswith(suffix):
                return file_type
        return "unknown"

    def detect_tools(self, project_path: Path, config_files: list[ConfigFile]) -> ToolStatusMap:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            Dictionary mapping tool names to whether they're configured
        """
        tools: ToolStatusMap = {
            # Quality tools
            "ruff": False,
            "basedpyright": False,
            "mypy": False,
            "pylint": False,
            "flake8": False,
            "black": False,
            # Security tools
            "bandit": False,
            "safety": False,
            "pip-audit": False,
            "trivy": False,
            # Testing tools
            "pytest": False,
            "tox": False,
            # Dependency managers
            "poetry": False,
            "pdm": False,
            "pipenv": False,
            "uv": False,
        }

        resolved_configs = config_files or self.detect_config_files(project_path)

        # Check pyproject.toml
        pyproject_file = next((f for f in resolved_configs if f.name == "pyproject.toml" and f.exists), None)
        if pyproject_file and pyproject_file.path:
            tools.update(self._detect_tools_in_pyproject(pyproject_file.path))

        # Check standalone config files
        tools.update(self._detect_tools_from_config_files(resolved_configs))

        return tools

    def _detect_tools_in_pyproject(self, pyproject_path: Path) -> dict[str, bool]:
        """Detect tools configured in pyproject.toml."""
        tools: dict[str, bool] = {}

        try:
            with pyproject_path.open("rb") as f:
                raw_data: Any = tomllib.load(f)

            if not isinstance(raw_data, dict):
                return tools
            data = cast(dict[str, Any], raw_data)

            tool_section_raw = data.get("tool")
            if isinstance(tool_section_raw, dict):
                tool_section = cast(dict[str, Any], tool_section_raw)
                tools["ruff"] = "ruff" in tool_section
                tools["basedpyright"] = "basedpyright" in tool_section or "pyright" in tool_section
                tools["mypy"] = "mypy" in tool_section
                tools["pylint"] = "pylint" in tool_section
                tools["black"] = "black" in tool_section
                tools["bandit"] = "bandit" in tool_section
                tools["pytest"] = "pytest" in tool_section
                tools["poetry"] = "poetry" in tool_section
                tools["pdm"] = "pdm" in tool_section
                tools["uv"] = "uv" in tool_section

            project_section_raw = data.get("project")
            if isinstance(project_section_raw, dict):
                project_section = cast(dict[str, Any], project_section_raw)
                dependencies_value = project_section.get("dependencies")
                dep_tokens = self._normalize_dependency_list(dependencies_value)
                dep_str = " ".join(dep_tokens)
                if dep_str:
                    tools["pytest"] = tools.get("pytest", False) or "pytest" in dep_str

        except (OSError, tomllib.TOMLDecodeError) as exc:
            debug(f"Failed to parse pyproject.toml at {pyproject_path}: {exc}")

        return tools

    def _detect_tools_from_config_files(self, config_files: list[ConfigFile]) -> dict[str, bool]:
        """Detect tools from standalone configuration files."""
        tools: dict[str, bool] = {}

        file_map = {
            "mypy.ini": "mypy",
            ".flake8": "flake8",
            ".pylintrc": "pylint",
            "bandit.yaml": "bandit",
            "pytest.ini": "pytest",
            "tox.ini": "tox",
            "poetry.lock": "poetry",
            "Pipfile": "pipenv",
            "pdm.lock": "pdm",
        }

        for config_file in config_files:
            if config_file.exists and config_file.name in file_map:
                tool_name = file_map[config_file.name]
                tools[tool_name] = True

        return tools

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        """Get list of recommended tools for Python.

        Returns:
            List of ToolRecommendation objects, ordered by priority
        """
        return [
            ToolRecommendation(
                tool_name="ruff",
                category="quality",
                description="Fast Python linter and formatter (replaces flake8, black, isort)",
                config_section="[tool.ruff]",
                priority=1,
                modern_alternative="flake8 + black + isort",
            ),
            ToolRecommendation(
                tool_name="basedpyright",
                category="quality",
                description="Fast static type checker based on pyright",
                config_section="[tool.basedpyright]",
                priority=1,
                modern_alternative="mypy",
            ),
            ToolRecommendation(
                tool_name="pytest",
                category="testing",
                description="Testing framework for Python",
                config_section="[tool.pytest.ini_options]",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="bandit",
                category="security",
                description="Security linter for Python code",
                config_section="[tool.bandit]",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="safety",
                category="security",
                description="Dependency vulnerability scanner",
                config_section="[tool.safety]",
                priority=3,
            ),
            ToolRecommendation(
                tool_name="uv",
                category="dependency",
                description="Fast Python package installer and resolver",
                config_section="[tool.uv]",
                priority=1,
            ),
        ]

    def get_security_tools(self) -> list[str]:
        """Get list of security-focused tools for Python."""
        return ["bandit", "safety", "pip-audit", "trivy"]

    def get_quality_tools(self) -> list[str]:
        """Get list of code quality tools for Python."""
        return ["ruff", "basedpyright", "mypy", "pylint"]

    def get_formatting_tools(self) -> list[str]:
        """Get list of code formatting tools for Python."""
        return ["ruff format", "black"]

    def parse_dependencies(self, project_path: Path, config_files: list[ConfigFile]) -> list[str]:
        """Parse project dependencies.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            List of dependency names
        """
        dependencies: list[str] = []

        resolved_configs = config_files or self.detect_config_files(project_path)

        # Parse pyproject.toml
        pyproject_file = next((f for f in resolved_configs if f.name == "pyproject.toml" and f.exists), None)
        if pyproject_file and pyproject_file.path:
            dependencies.extend(self._parse_pyproject_dependencies(pyproject_file.path))

        # Parse requirements.txt
        requirements_file = next((f for f in resolved_configs if f.name == "requirements.txt" and f.exists), None)
        if requirements_file and requirements_file.path:
            dependencies.extend(self._parse_requirements_txt(requirements_file.path))

        # Remove duplicates
        return list(set(dependencies))

    def _parse_pyproject_dependencies(self, pyproject_path: Path) -> list[str]:
        """Parse dependencies from pyproject.toml."""
        dependencies: list[str] = []

        try:
            with pyproject_path.open("rb") as f:
                raw_data: Any = tomllib.load(f)

            if not isinstance(raw_data, dict):
                return []

            data = cast(dict[str, Any], raw_data)
            project_section_raw = data.get("project")
            if isinstance(project_section_raw, dict):
                project_section = cast(dict[str, Any], project_section_raw)
                dep_list_raw = project_section.get("dependencies")
                for dep in self._normalize_dependency_list(dep_list_raw):
                    match = re.match(r"([a-zA-Z0-9_-]+)", dep)
                    if match:
                        dependencies.append(match.group(1))

        except (OSError, tomllib.TOMLDecodeError) as exc:
            debug(f"Failed to parse dependencies from {pyproject_path}: {exc}")

        return dependencies

    def _parse_requirements_txt(self, requirements_path: Path) -> list[str]:
        """Parse dependencies from requirements.txt."""
        dependencies: list[str] = []

        try:
            with requirements_path.open(encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith("#"):
                        continue
                    # Extract package name
                    match = re.match(r"([a-zA-Z0-9_-]+)", line)
                    if match:
                        dependencies.append(match.group(1))

        except OSError as exc:
            debug(f"Failed to parse requirements.txt at {requirements_path}: {exc}")

        return dependencies
