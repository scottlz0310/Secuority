"""Unit tests for the Node.js language analyzer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from secuority.core.languages.nodejs import NodeJSAnalyzer


class TestNodeJSAnalyzer:
    """Validate Node.js language detection and parsing."""

    def _write_files(self, base_path: Path, filenames: list[str]) -> None:
        for name in filenames:
            file_path = base_path / name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("", encoding="utf-8")

    def test_detect_caps_confidence_at_one_with_multiple_indicators(self, tmp_path: Path) -> None:
        analyzer = NodeJSAnalyzer()
        self._write_files(
            tmp_path,
            [
                "package.json",
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
                "tsconfig.json",
            ],
        )
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "index.js").write_text("console.log('hi');\n", encoding="utf-8")
        (tmp_path / "node_modules").mkdir()

        result = analyzer.detect(tmp_path)

        assert result.language == "nodejs"
        assert result.confidence == pytest.approx(1.0)
        assert "package.json" in result.indicators
        assert "tsconfig.json" in result.indicators
        assert any(".js/.ts files" in indicator for indicator in result.indicators)

    def test_detect_tools_merges_package_json_and_config_files(self, tmp_path: Path) -> None:
        analyzer = NodeJSAnalyzer()
        package_json = {
            "dependencies": {
                "@biomejs/biome": "1.0.0",
                "typescript": "^5.0.0",
                "prettier": "^3.0.0",
                "@playwright/test": "^1.0.0",
            },
            "devDependencies": {
                "eslint": "^9.0.0",
                "jest": "^29.0.0",
                "vitest": "^1.0.0",
                "snyk": "^1.0.0",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(package_json), encoding="utf-8")

        self._write_files(
            tmp_path,
            [
                "biome.json",
                ".eslintrc.json",
                ".prettierrc",
                "tsconfig.json",
                "vitest.config.ts",
                "playwright.config.ts",
                "package-lock.json",
                "yarn.lock",
                "pnpm-lock.yaml",
            ],
        )

        config_files = analyzer.detect_config_files(tmp_path)
        tools = analyzer.detect_tools(tmp_path, config_files)
        config_map = {cfg.name: cfg for cfg in config_files}

        assert tools["biome"]
        assert tools["eslint"]
        assert tools["typescript"]
        assert tools["prettier"]
        assert tools["jest"]
        assert tools["vitest"]
        assert tools["playwright"]
        assert tools["snyk"]
        assert tools["npm"]
        assert tools["yarn"]
        assert tools["pnpm"]
        assert config_map["tsconfig.json"].file_type == "json"
        assert config_map["vitest.config.ts"].file_type == "typescript"
        assert config_map["package-lock.json"].file_type == "json"
        assert config_map["yarn.lock"].file_type == "lock"

    def test_parse_dependencies_collects_prod_and_dev_dependencies(self, tmp_path: Path) -> None:
        analyzer = NodeJSAnalyzer()
        package_json = {
            "dependencies": {"react": "^18.0.0"},
            "devDependencies": {"vitest": "^1.0.0"},
        }
        (tmp_path / "package.json").write_text(json.dumps(package_json), encoding="utf-8")

        config_files = analyzer.detect_config_files(tmp_path)
        deps = analyzer.parse_dependencies(tmp_path, config_files)

        assert set(deps) == {"react", "vitest"}
