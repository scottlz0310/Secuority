"""Unit tests for the Rust language analyzer."""

from __future__ import annotations

import textwrap
from pathlib import Path

from secuority.core.languages.rust import RustAnalyzer


class TestRustAnalyzer:
    """Validate Rust detection, tooling, and dependency parsing."""

    def test_detect_collects_primary_indicators(self, tmp_path: Path) -> None:
        analyzer = RustAnalyzer()
        (tmp_path / "Cargo.toml").write_text('[package]\nname = "demo"\n', encoding="utf-8")
        (tmp_path / "Cargo.lock").write_text("version = 3\n", encoding="utf-8")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.rs").write_text("fn main() {}\n", encoding="utf-8")
        (tmp_path / "target").mkdir()
        (tmp_path / "rust-toolchain").write_text("stable\n", encoding="utf-8")

        result = analyzer.detect(tmp_path)

        assert result.language == "rust"
        assert result.confidence == 1.0
        assert "Cargo.toml" in result.indicators
        assert any(".rs files" in indicator for indicator in result.indicators)

    def test_detect_tools_uses_configs_and_workflows(self, tmp_path: Path) -> None:
        analyzer = RustAnalyzer()
        (tmp_path / "Cargo.toml").write_text(
            textwrap.dedent(
                """
                [package]
                name = "demo"

                [dev-dependencies]
                cargo-audit = "0.18"
                """,
            ).strip(),
            encoding="utf-8",
        )
        (tmp_path / "rustfmt.toml").write_text("", encoding="utf-8")
        (tmp_path / ".clippy.toml").write_text("", encoding="utf-8")
        (tmp_path / "deny.toml").write_text("", encoding="utf-8")
        (tmp_path / "tarpaulin.toml").write_text("", encoding="utf-8")

        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        workflows.joinpath("ci.yml").write_text(
            textwrap.dedent(
                """
                - run: cargo clippy
                - run: cargo fmt
                - run: cargo audit
                - run: cargo deny
                - run: cargo tarpaulin
                """,
            ).strip(),
            encoding="utf-8",
        )

        tools = analyzer.detect_tools(tmp_path, config_files=[])

        assert tools["rustfmt"]
        assert tools["clippy"]
        assert tools["cargo-audit"]
        assert tools["cargo-deny"]
        assert tools["cargo-tarpaulin"]

    def test_parse_dependencies_reads_sections(self, tmp_path: Path) -> None:
        analyzer = RustAnalyzer()
        (tmp_path / "Cargo.toml").write_text(
            textwrap.dedent(
                """
                [dependencies]
                serde = "1.0"

                [dev-dependencies]
                anyhow = "1.0"
                """,
            ).strip(),
            encoding="utf-8",
        )

        deps = analyzer.parse_dependencies(tmp_path, [])

        assert set(deps) == {"serde", "anyhow"}

    def test_detect_config_files_reports_types(self, tmp_path: Path) -> None:
        analyzer = RustAnalyzer()
        (tmp_path / "rustfmt.toml").write_text("", encoding="utf-8")
        (tmp_path / ".cargo").mkdir()
        (tmp_path / ".cargo" / "config.toml").write_text("", encoding="utf-8")

        config_files = analyzer.detect_config_files(tmp_path)
        config_map = {cfg.name: cfg for cfg in config_files}

        assert config_map["rustfmt.toml"].file_type == "toml"
        assert config_map[".cargo/config.toml"].file_type == "toml"
