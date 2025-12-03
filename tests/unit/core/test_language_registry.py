"""Unit tests for the language registry."""

from __future__ import annotations

from pathlib import Path

from secuority.core.languages.base import (
    ConfigFile,
    LanguageAnalyzer,
    LanguageDetectionResult,
    ToolRecommendation,
)
from secuority.core.languages.registry import LanguageRegistry


class StubAnalyzer(LanguageAnalyzer):
    """Minimal analyzer used to validate registry behavior."""

    def __init__(
        self,
        name: str,
        confidence: float = 1.0,
        missing: list[ToolRecommendation] | None = None,
    ) -> None:
        self._name = name
        self._stub_confidence = confidence
        self._missing_override = missing
        super().__init__()
        self._recommended = [
            ToolRecommendation(
                tool_name=f"{self.language_name}-lint",
                category="quality",
                description="stub",
                config_section="config",
                priority=1,
            )
        ]
        self._missing = missing if missing is not None else self._recommended[:1]

    def _get_language_name(self) -> str:
        return self._name

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        return LanguageDetectionResult(
            language=self.language_name,
            confidence=self._stub_confidence,
            indicators=[project_path.name or "tmp"],
        )

    def get_config_file_patterns(self) -> dict[str, str]:
        return {}

    def detect_config_files(self, _project_path: Path) -> list[ConfigFile]:
        return [ConfigFile(name=f"{self.language_name}.cfg", path=None, exists=False, file_type="text")]

    def detect_tools(self, _project_path: Path, _config_files: list[ConfigFile]) -> dict[str, bool]:
        return {f"{self.language_name}-tool": True}

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        return self._recommended

    def get_security_tools(self) -> list[str]:
        return []

    def get_quality_tools(self) -> list[str]:
        return []

    def get_formatting_tools(self) -> list[str]:
        return []

    def parse_dependencies(self, _project_path: Path, _config_files: list[ConfigFile]) -> list[str]:
        return [f"{self.language_name}-dep"]

    def get_missing_tools(self, _project_path: Path) -> list[ToolRecommendation]:
        return self._missing


class TestLanguageRegistry:
    """Verify the orchestration logic for multilingual analysis."""

    def test_detect_languages_filters_by_confidence(self, tmp_path: Path) -> None:
        registry = LanguageRegistry()
        registry.register(StubAnalyzer("high", confidence=0.9), priority=10)
        registry.register(StubAnalyzer("low", confidence=0.1), priority=30)

        default_results = registry.detect_languages(tmp_path)
        assert [result.language for result in default_results] == ["high"]

        relaxed_results = registry.detect_languages(tmp_path, min_confidence=0.05)
        assert [result.language for result in relaxed_results] == ["high", "low"]

    def test_analyze_project_auto_detects_when_languages_not_provided(self, tmp_path: Path) -> None:
        registry = LanguageRegistry()
        registry.register(StubAnalyzer("pythonish", confidence=0.8), priority=10)

        analysis = registry.analyze_project(tmp_path)

        assert "pythonish" in analysis
        assert analysis["pythonish"]["detected"]
        assert analysis["pythonish"]["language"] == "pythonish"
        assert analysis["pythonish"]["tools"] == {"pythonish-tool": True}

    def test_get_all_recommendations_includes_missing_and_full_lists(self, tmp_path: Path) -> None:
        missing = [
            ToolRecommendation(
                tool_name="special-lint",
                category="quality",
                description="stub",
                config_section="config",
                priority=1,
            )
        ]
        registry = LanguageRegistry()
        registry.register(StubAnalyzer("nodeish", confidence=0.9, missing=missing), priority=20)

        recommendations = registry.get_all_recommendations(tmp_path)

        assert recommendations["nodeish"]["missing_tools"] == missing
        assert recommendations["nodeish"]["all_recommendations"] == registry.get_analyzer(
            "nodeish"
        ).get_recommended_tools()

    def test_unregister_and_language_name_tracking(self) -> None:
        registry = LanguageRegistry()
        registry.register(StubAnalyzer("goish", confidence=0.7), priority=15)

        assert registry.has_language("goish")
        assert set(registry.get_language_names()) == {"goish"}

        registry.unregister("goish")

        assert not registry.has_language("goish")
        assert registry.get_language_names() == []
