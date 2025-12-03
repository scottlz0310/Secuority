"""Unit tests for the C# language analyzer."""

from __future__ import annotations

import textwrap
from pathlib import Path

from secuority.core.languages.csharp import CSharpAnalyzer


class TestCSharpAnalyzer:
    """Validate C# detection, tooling, and dependency parsing."""

    def test_detect_accumulates_project_indicators(self, tmp_path: Path) -> None:
        analyzer = CSharpAnalyzer()
        project_dir = tmp_path / "src"
        project_dir.mkdir()
        csproj = project_dir / "Demo.csproj"
        csproj.write_text('<Project Sdk="Microsoft.NET.Sdk" />', encoding="utf-8")
        (tmp_path / "Demo.sln").write_text("", encoding="utf-8")
        (project_dir / "Program.cs").write_text("class Program {}", encoding="utf-8")
        (tmp_path / "global.json").write_text('{"sdk": {"version": "8.0.0"}}', encoding="utf-8")
        (tmp_path / "NuGet.config").write_text("<configuration/>", encoding="utf-8")
        (tmp_path / "bin").mkdir()

        result = analyzer.detect(tmp_path)

        assert result.language == "csharp"
        assert result.confidence == 1.0
        assert any(".csproj files" in indicator for indicator in result.indicators)
        assert "global.json" in result.indicators

    def test_detect_tools_from_csproj_and_workflows(self, tmp_path: Path) -> None:
        analyzer = CSharpAnalyzer()
        csproj = tmp_path / "App.csproj"
        csproj.write_text(
            textwrap.dedent(
                """
                <Project Sdk="Microsoft.NET.Sdk">
                  <ItemGroup>
                    <PackageReference Include="StyleCop.Analyzers" Version="1.2.0" />
                  </ItemGroup>
                </Project>
                """,
            ).strip(),
            encoding="utf-8",
        )
        (tmp_path / ".editorconfig").write_text("", encoding="utf-8")
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        workflows.joinpath("ci.yml").write_text(
            "- run: dotnet format\n- run: dotnet test\n",
            encoding="utf-8",
        )

        tools = analyzer.detect_tools(tmp_path, config_files=[])

        assert tools["editorconfig"]
        assert tools["stylecop"]
        assert tools["dotnet-format"]
        assert tools["dotnet-test"]

    def test_parse_dependencies_reads_csproj(self, tmp_path: Path) -> None:
        analyzer = CSharpAnalyzer()
        csproj = tmp_path / "Lib.csproj"
        csproj.write_text(
            textwrap.dedent(
                """
                <Project Sdk="Microsoft.NET.Sdk">
                  <ItemGroup>
                    <PackageReference Include="Newtonsoft.Json" Version="13.0.1" />
                    <PackageReference Include="Serilog" Version="2.12.0" />
                  </ItemGroup>
                </Project>
                """,
            ).strip(),
            encoding="utf-8",
        )

        deps = analyzer.parse_dependencies(tmp_path, [])

        assert set(deps) == {"Newtonsoft.Json", "Serilog"}

    def test_detect_config_files_reports_editorconfig(self, tmp_path: Path) -> None:
        analyzer = CSharpAnalyzer()
        project_dir = tmp_path / "src"
        project_dir.mkdir()
        csproj = project_dir / "Demo.csproj"
        csproj.write_text("<Project/>", encoding="utf-8")
        (tmp_path / ".editorconfig").write_text("", encoding="utf-8")

        config_files = analyzer.detect_config_files(tmp_path)
        config_map = {cfg.name: cfg for cfg in config_files}

        assert config_map["Demo.csproj"].file_type == "xml"
        assert config_map[".editorconfig"].file_type == "editorconfig"
