"""Language-specific analyzers for multi-language support.

This module provides an abstraction layer for analyzing projects
in different programming languages. Each language has its own
analyzer that implements the LanguageAnalyzer interface.

Usage:
    from secuority.core.languages import get_global_registry
    from secuority.core.languages.python import PythonAnalyzer

    # Get the global registry (Python analyzer is auto-registered)
    registry = get_global_registry()

    # Detect languages in a project
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
from .python import PythonAnalyzer
from .registry import (
    LanguageRegistry,
    get_global_registry,
    register_language,
)

# Auto-register Python analyzer
register_language(PythonAnalyzer(), priority=10)

__all__ = [
    "ConfigFile",
    "LanguageAnalyzer",
    "LanguageDetectionResult",
    "LanguageRegistry",
    "PythonAnalyzer",
    "ToolRecommendation",
    "get_global_registry",
    "register_language",
]
