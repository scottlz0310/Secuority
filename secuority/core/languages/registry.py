"""Language registry for detecting and managing multiple languages."""

from pathlib import Path
from typing import Any

from .base import LanguageAnalyzer, LanguageDetectionResult


class LanguageRegistry:
    """Registry for managing language-specific analyzers.

    This class maintains a registry of available language analyzers
    and provides methods to detect which languages are used in a project.
    """

    def __init__(self) -> None:
        """Initialize the language registry."""
        self._analyzers: dict[str, LanguageAnalyzer] = {}
        self._detection_order: list[str] = []

    def register(self, analyzer: LanguageAnalyzer, priority: int = 50) -> None:
        """Register a language analyzer.

        Args:
            analyzer: Language analyzer instance
            priority: Detection priority (lower = higher priority, default 50)
        """
        language_name = analyzer.language_name
        self._analyzers[language_name] = analyzer

        # Insert based on priority
        self._detection_order.append(language_name)
        self._detection_order.sort(key=lambda x: self._get_priority(x, priority))

    def _get_priority(self, _language: str, default: int) -> int:
        """Get priority for a language (lower = higher priority)."""
        # Could be extended to store priorities per language
        return default

    def unregister(self, language_name: str) -> None:
        """Unregister a language analyzer.

        Args:
            language_name: Name of the language to unregister
        """
        if language_name in self._analyzers:
            del self._analyzers[language_name]
            self._detection_order.remove(language_name)

    def get_analyzer(self, language_name: str) -> LanguageAnalyzer | None:
        """Get analyzer for a specific language.

        Args:
            language_name: Name of the language

        Returns:
            Language analyzer instance or None if not registered
        """
        return self._analyzers.get(language_name)

    def get_all_analyzers(self) -> dict[str, LanguageAnalyzer]:
        """Get all registered analyzers.

        Returns:
            Dictionary mapping language names to analyzer instances
        """
        return self._analyzers.copy()

    def detect_languages(
        self,
        project_path: Path,
        min_confidence: float = 0.3,
    ) -> list[LanguageDetectionResult]:
        """Detect all languages used in a project.

        Args:
            project_path: Path to the project directory
            min_confidence: Minimum confidence threshold (0.0 to 1.0)

        Returns:
            List of LanguageDetectionResult objects, ordered by confidence
        """
        results = []

        for language_name in self._detection_order:
            analyzer = self._analyzers[language_name]
            detection = analyzer.detect(project_path)

            if detection.confidence >= min_confidence:
                results.append(detection)

        # Sort by confidence (highest first)
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results

    def detect_primary_language(self, project_path: Path) -> LanguageDetectionResult | None:
        """Detect the primary language of a project.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult for the primary language, or None if no language detected
        """
        results = self.detect_languages(project_path, min_confidence=0.3)
        return results[0] if results else None

    def analyze_project(
        self,
        project_path: Path,
        languages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Analyze a project with all relevant language analyzers.

        Args:
            project_path: Path to the project directory
            languages: Optional list of specific languages to analyze.
                      If None, auto-detects languages.

        Returns:
            Dictionary with analysis results per language
        """
        if languages is None:
            # Auto-detect languages
            detected = self.detect_languages(project_path, min_confidence=0.3)
            languages = [d.language for d in detected]

        results = {}
        for language_name in languages:
            analyzer = self.get_analyzer(language_name)
            if analyzer:
                results[language_name] = analyzer.analyze(project_path)

        return results

    def get_all_recommendations(
        self,
        project_path: Path,
        languages: list[str] | None = None,
    ) -> dict[str, Any]:
        """Get tool recommendations for all detected languages.

        Args:
            project_path: Path to the project directory
            languages: Optional list of specific languages.
                      If None, auto-detects languages.

        Returns:
            Dictionary mapping language names to their recommendations
        """
        if languages is None:
            detected = self.detect_languages(project_path, min_confidence=0.3)
            languages = [d.language for d in detected]

        recommendations = {}
        for language_name in languages:
            analyzer = self.get_analyzer(language_name)
            if analyzer:
                missing = analyzer.get_missing_tools(project_path)
                recommendations[language_name] = {
                    "missing_tools": missing,
                    "all_recommendations": analyzer.get_recommended_tools(),
                }

        return recommendations

    def get_language_names(self) -> list[str]:
        """Get list of all registered language names.

        Returns:
            List of language names
        """
        return list(self._analyzers.keys())

    def has_language(self, language_name: str) -> bool:
        """Check if a language is registered.

        Args:
            language_name: Name of the language

        Returns:
            True if language is registered, False otherwise
        """
        return language_name in self._analyzers

    def clear(self) -> None:
        """Clear all registered analyzers."""
        self._analyzers.clear()
        self._detection_order.clear()


# Global registry instance
_global_registry = LanguageRegistry()


def get_global_registry() -> LanguageRegistry:
    """Get the global language registry instance.

    Returns:
        Global LanguageRegistry instance
    """
    return _global_registry


def register_language(analyzer: LanguageAnalyzer, priority: int = 50) -> None:
    """Register a language analyzer in the global registry.

    Args:
        analyzer: Language analyzer instance
        priority: Detection priority (lower = higher priority)
    """
    _global_registry.register(analyzer, priority)
