"""Language-specific analyzers for multi-language support.

This module provides an abstraction layer for analyzing projects
in different programming languages. Each language has its own
analyzer that implements the LanguageAnalyzer interface.

Usage:
    from secuority.core.languages import get_global_registry, register_language
    from secuority.core.languages.python import PythonAnalyzer

    # Register a language analyzer
    register_language(PythonAnalyzer())

    # Detect languages in a project
    registry = get_global_registry()
    detected = registry.detect_languages(project_path)

    # Analyze a project
    results = registry.analyze_project(project_path)
"""

from .base import (
    ConfigFile,
    LanguageAnalyzer,
    LanguageDetectionResult,
    ToolRecommendation,
)
from .registry import (
    LanguageRegistry,
    get_global_registry,
    register_language,
)

__all__ = [
    "ConfigFile",
    "LanguageAnalyzer",
    "LanguageDetectionResult",
    "LanguageRegistry",
    "ToolRecommendation",
    "get_global_registry",
    "register_language",
]
