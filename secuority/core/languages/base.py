"""Base classes for language-specific analyzers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ToolRecommendation:
    """Recommendation for a specific tool."""

    tool_name: str
    category: str  # "security", "quality", "formatting", "testing"
    description: str
    config_section: str  # Where to configure (e.g., "pyproject.toml", "package.json")
    priority: int  # 1-5, where 1 is highest priority
    modern_alternative: str | None = None  # If this replaces an older tool


@dataclass
class ConfigFile:
    """Information about a configuration file."""

    name: str
    path: Path | None
    exists: bool
    file_type: str  # "toml", "json", "yaml", etc.


@dataclass
class LanguageDetectionResult:
    """Result of language detection."""

    language: str  # "python", "nodejs", "cpp", "csharp", etc.
    confidence: float  # 0.0 to 1.0
    indicators: list[str]  # Files/patterns that indicated this language


class LanguageAnalyzer(ABC):
    """Abstract base class for language-specific analyzers.

    Each language implementation should:
    1. Detect if a project uses that language
    2. Identify configuration files
    3. Detect installed/configured tools
    4. Provide recommendations for missing tools
    5. Generate language-specific templates
    """

    def __init__(self) -> None:
        """Initialize the language analyzer."""
        self.language_name = self._get_language_name()

    @abstractmethod
    def _get_language_name(self) -> str:
        """Get the name of this language (e.g., 'python', 'nodejs')."""

    @abstractmethod
    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses this language.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score and indicators
        """

    @abstractmethod
    def get_config_file_patterns(self) -> dict[str, str]:
        """Get configuration file patterns for this language.

        Returns:
            Dictionary mapping file names to descriptions
            Example: {"pyproject.toml": "Python project configuration"}
        """

    @abstractmethod
    def detect_config_files(self, project_path: Path) -> list[ConfigFile]:
        """Detect configuration files present in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            List of ConfigFile objects for files that exist
        """

    @abstractmethod
    def detect_tools(self, project_path: Path, config_files: list[ConfigFile]) -> dict[str, bool]:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            Dictionary mapping tool names to whether they're configured
            Example: {"ruff": True, "mypy": False, "pytest": True}
        """

    @abstractmethod
    def get_recommended_tools(self) -> list[ToolRecommendation]:
        """Get list of recommended tools for this language.

        Returns:
            List of ToolRecommendation objects, ordered by priority
        """

    @abstractmethod
    def get_security_tools(self) -> list[str]:
        """Get list of security-focused tools for this language.

        Returns:
            List of tool names (e.g., ["bandit", "safety", "semgrep"])
        """

    @abstractmethod
    def get_quality_tools(self) -> list[str]:
        """Get list of code quality tools for this language.

        Returns:
            List of tool names (e.g., ["ruff", "basedpyright", "pylint"])
        """

    @abstractmethod
    def get_formatting_tools(self) -> list[str]:
        """Get list of code formatting tools for this language.

        Returns:
            List of tool names (e.g., ["ruff format", "black"])
        """

    @abstractmethod
    def parse_dependencies(self, project_path: Path, config_files: list[ConfigFile]) -> list[str]:
        """Parse project dependencies.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            List of dependency names
        """

    def analyze(self, project_path: Path) -> dict[str, Any]:
        """Perform a complete analysis of the project for this language.

        This is a convenience method that orchestrates the analysis.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary containing analysis results
        """
        detection = self.detect(project_path)

        if detection.confidence < 0.3:
            return {
                "detected": False,
                "confidence": detection.confidence,
                "language": self.language_name,
            }

        config_files = self.detect_config_files(project_path)
        tools = self.detect_tools(project_path, config_files)
        recommendations = self.get_recommended_tools()
        dependencies = self.parse_dependencies(project_path, config_files)

        return {
            "detected": True,
            "confidence": detection.confidence,
            "language": self.language_name,
            "indicators": detection.indicators,
            "config_files": config_files,
            "tools": tools,
            "recommendations": recommendations,
            "dependencies": dependencies,
        }

    def get_missing_tools(self, project_path: Path) -> list[ToolRecommendation]:
        """Get recommendations for tools that are not yet configured.

        Args:
            project_path: Path to the project directory

        Returns:
            List of ToolRecommendation for missing tools
        """
        config_files = self.detect_config_files(project_path)
        configured_tools = self.detect_tools(project_path, config_files)
        all_recommendations = self.get_recommended_tools()

        missing = [rec for rec in all_recommendations if not configured_tools.get(rec.tool_name, False)]

        return sorted(missing, key=lambda x: x.priority)
