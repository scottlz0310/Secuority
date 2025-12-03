"""Unit tests for the Go language analyzer."""

from __future__ import annotations

import textwrap
from pathlib import Path

from secuority.core.languages.go import GoAnalyzer


class TestGoAnalyzer:
    """Validate Go detection, tooling, and dependency logic."""

    def test_detect_accumulates_multiple_indicators(self, tmp_path: Path) -> None:
        analyzer = GoAnalyzer()

        (tmp_path / "go.mod").write_text("module example\n", encoding="utf-8")
        (tmp_path / "go.sum").write_text("example v0.0.1 h1:abc\n", encoding="utf-8")
        (tmp_path / "go.work").write_text("go 1.21\n", encoding="utf-8")
        (tmp_path / "vendor").mkdir()
        (tmp_path / "main.go").write_text("package main\n", encoding="utf-8")

        result = analyzer.detect(tmp_path)

        assert result.language == "go"
        assert result.confidence == 1.0  # capped after multiple indicators
        assert "go.mod" in result.indicators
        assert any(".go files" in indicator for indicator in result.indicators)

    def test_detect_tools_reads_configs_and_workflows(self, tmp_path: Path) -> None:
        analyzer = GoAnalyzer()
        (tmp_path / "go.mod").write_text("module example\n", encoding="utf-8")
        (tmp_path / ".golangci.yml").write_text("run: {}\n", encoding="utf-8")
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        workflows.joinpath("ci.yml").write_text(
            textwrap.dedent(
                """
                jobs:
                  lint:
                    steps:
                      - run: golangci-lint run
                      - run: go test ./...
                      - run: govulncheck ./...
                      - run: gosec ./...
                """
            ).strip(),
            encoding="utf-8",
        )

        tools = analyzer.detect_tools(tmp_path, config_files=[])

        assert tools["golangci-lint"]
        assert tools["gofmt"]
        assert tools["gotest"]
        assert tools["govulncheck"]
        assert tools["gosec"]

    def test_parse_dependencies_reads_require_block(self, tmp_path: Path) -> None:
        analyzer = GoAnalyzer()
        (tmp_path / "go.mod").write_text(
            textwrap.dedent(
                """
                module example

                require (
                    github.com/pkg/errors v0.9.1
                    golang.org/x/crypto v0.21.0
                )
                """
            ).strip(),
            encoding="utf-8",
        )

        deps = analyzer.parse_dependencies(tmp_path, [])

        assert set(deps) == {"github.com/pkg/errors", "golang.org/x/crypto"}

    def test_detect_config_files_reports_file_types(self, tmp_path: Path) -> None:
        analyzer = GoAnalyzer()
        (tmp_path / ".golangci.yml").write_text("run: {}\n", encoding="utf-8")
        (tmp_path / ".gofmt").write_text("", encoding="utf-8")

        config_files = analyzer.detect_config_files(tmp_path)
        names = {cfg.name: cfg for cfg in config_files}

        assert names[".golangci.yml"].file_type == "yaml"
        assert names[".gofmt"].file_type == "config"
