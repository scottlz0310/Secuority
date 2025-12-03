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
from .cpp import CppAnalyzer
from .csharp import CSharpAnalyzer
from .go import GoAnalyzer
from .nodejs import NodeJSAnalyzer
from .python import PythonAnalyzer
from .registry import (
    LanguageRegistry,
    get_global_registry,
    register_language,
)
from .rust import RustAnalyzer

# Auto-register language analyzers
register_language(PythonAnalyzer(), priority=10)
register_language(NodeJSAnalyzer(), priority=10)
register_language(RustAnalyzer(), priority=20)
register_language(GoAnalyzer(), priority=20)
register_language(CppAnalyzer(), priority=30)
register_language(CSharpAnalyzer(), priority=30)

__all__ = [
    "CSharpAnalyzer",
    "ConfigFile",
    "CppAnalyzer",
    "GoAnalyzer",
    "LanguageAnalyzer",
    "LanguageDetectionResult",
    "LanguageRegistry",
    "NodeJSAnalyzer",
    "PythonAnalyzer",
    "RustAnalyzer",
    "ToolRecommendation",
    "get_global_registry",
    "register_language",
]
