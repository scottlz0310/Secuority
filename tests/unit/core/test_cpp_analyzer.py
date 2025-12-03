"""Unit tests for the C++ language analyzer."""

from __future__ import annotations

import json
from pathlib import Path

from secuority.core.languages.cpp import CppAnalyzer


class TestCppAnalyzer:
    """Validate C++ detection, tooling, and dependency handling."""

    def test_detect_accumulates_build_indicators(self, tmp_path: Path) -> None:
        analyzer = CppAnalyzer()
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.0)\n", encoding="utf-8")
        (tmp_path / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
        (tmp_path / "include").mkdir()
        (tmp_path / "include" / "main.hpp").write_text("#pragma once\n", encoding="utf-8")
        (tmp_path / "Makefile").write_text("all:\n\tg++ main.cpp\n", encoding="utf-8")
        (tmp_path / "build").mkdir()
        (tmp_path / "vcpkg.json").write_text('{"dependencies": ["fmt"]}', encoding="utf-8")
        (tmp_path / "conanfile.txt").write_text("[requires]\nspdlog/1.13.0\n", encoding="utf-8")

        result = analyzer.detect(tmp_path)

        assert result.language == "cpp"
        assert result.confidence == 1.0
        assert "CMakeLists.txt" in result.indicators
        assert any(".cpp/.cc/.cxx files" in indicator for indicator in result.indicators)

    def test_detect_tools_from_configs_and_workflows(self, tmp_path: Path) -> None:
        analyzer = CppAnalyzer()
        (tmp_path / ".clang-format").write_text("", encoding="utf-8")
        (tmp_path / ".clang-tidy").write_text("", encoding="utf-8")
        (tmp_path / ".cppcheck").write_text("", encoding="utf-8")
        (tmp_path / "CMakeLists.txt").write_text("", encoding="utf-8")
        (tmp_path / "vcpkg.json").write_text(json.dumps({"dependencies": []}), encoding="utf-8")
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        workflows.joinpath("ci.yml").write_text(
            "- run: clang-format\n- run: clang-tidy\n- run: cppcheck\n",
            encoding="utf-8",
        )

        tools = analyzer.detect_tools(tmp_path, config_files=[])

        assert tools["clang-format"]
        assert tools["clang-tidy"]
        assert tools["cppcheck"]
        assert tools["cmake"]
        assert tools["vcpkg"]

    def test_parse_dependencies_reads_vcpkg_and_conan(self, tmp_path: Path) -> None:
        analyzer = CppAnalyzer()
        (tmp_path / "vcpkg.json").write_text(
            json.dumps({"dependencies": ["fmt", {"name": "spdlog"}]}),
            encoding="utf-8",
        )
        (tmp_path / "conanfile.txt").write_text("[requires]\ncatch2/3.0.0\n", encoding="utf-8")

        deps = analyzer.parse_dependencies(tmp_path, [])

        assert set(deps) == {"fmt", "spdlog", "catch2"}

    def test_detect_config_files_reports_compile_commands(self, tmp_path: Path) -> None:
        analyzer = CppAnalyzer()
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "compile_commands.json").write_text("[]", encoding="utf-8")
        (tmp_path / ".clang-format").write_text("", encoding="utf-8")

        config_files = analyzer.detect_config_files(tmp_path)
        config_map = {cfg.name: cfg for cfg in config_files}

        assert config_map[".clang-format"].file_type == "yaml"
        assert config_map["build/compile_commands.json"].file_type == "json"
