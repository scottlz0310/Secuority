"""C# language analyzer implementation."""

import xml.etree.ElementTree as ET
from pathlib import Path

from secuority.utils.logger import debug

from .base import ConfigFile, LanguageAnalyzer, LanguageDetectionResult, ToolRecommendation


class CSharpAnalyzer(LanguageAnalyzer):
    """Analyzer for C# projects.

    Detects C# configuration files, tools, and provides recommendations
    for C#-specific quality and security tools.
    """

    def _get_language_name(self) -> str:
        """Get the name of this language."""
        return "csharp"

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses C#.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score
        """
        indicators = []
        confidence = 0.0

        # Check for .csproj files (primary indicator)
        csproj_files = list(project_path.glob("**/*.csproj"))
        if csproj_files:
            indicators.append(f"{len(csproj_files)} .csproj files")
            confidence += 0.6

        # Check for .sln (solution) files
        sln_files = list(project_path.glob("*.sln"))
        if sln_files:
            indicators.append(f"{len(sln_files)} .sln files")
            confidence += 0.2

        # Check for .cs files
        cs_files = list(project_path.glob("**/*.cs"))
        if cs_files:
            total_files = len(cs_files)
            indicators.append(f"{total_files} .cs files")
            confidence += 0.3

        # Check for global.json
        if (project_path / "global.json").exists():
            indicators.append("global.json")
            confidence += 0.1

        # Check for NuGet.config
        if (project_path / "NuGet.config").exists() or (project_path / "nuget.config").exists():
            indicators.append("NuGet.config")
            confidence += 0.1

        # Check for bin/obj directories
        if (project_path / "bin").exists() or (project_path / "obj").exists():
            indicators.append("bin/obj directories")
            confidence += 0.1

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        return LanguageDetectionResult(
            language="csharp",
            confidence=confidence,
            indicators=indicators,
        )

    def get_config_file_patterns(self) -> dict[str, str]:
        """Get configuration file patterns for C#.

        Returns:
            Dictionary mapping file names to descriptions
        """
        return {
            "*.csproj": "C# project file",
            "*.sln": "Visual Studio solution file",
            "global.json": ".NET SDK version specification",
            "NuGet.config": "NuGet package manager configuration",
            ".editorconfig": "EditorConfig formatting rules",
            "Directory.Build.props": "MSBuild properties for all projects",
            "Directory.Build.targets": "MSBuild targets for all projects",
            ".runsettings": "Test run settings",
        }

    def detect_config_files(self, project_path: Path) -> list[ConfigFile]:
        """Detect configuration files present in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            List of detected configuration files
        """
        config_files = []

        # Check for .csproj files
        csproj_files = list(project_path.glob("**/*.csproj"))
        config_files.extend(
            ConfigFile(
                name=csproj.name,
                path=csproj,
                exists=True,
                file_type="xml",
            )
            for csproj in csproj_files
        )

        # Check for .sln files
        sln_files = list(project_path.glob("*.sln"))
        config_files.extend(
            ConfigFile(
                name=sln.name,
                path=sln,
                exists=True,
                file_type="solution",
            )
            for sln in sln_files
        )

        # Check for other configuration files
        standard_configs = {
            "global.json": ".NET SDK version specification",
            "NuGet.config": "NuGet package manager configuration",
            "nuget.config": "NuGet package manager configuration",
            ".editorconfig": "EditorConfig formatting rules",
            "Directory.Build.props": "MSBuild properties",
            "Directory.Build.targets": "MSBuild targets",
            ".runsettings": "Test run settings",
        }

        for filename in standard_configs:
            file_path = project_path / filename
            if file_path.exists() and file_path.is_file():
                config_files.append(
                    ConfigFile(
                        name=filename,
                        path=file_path,
                        exists=True,
                        file_type=self._determine_file_type(filename),
                    ),
                )

        return config_files

    def _determine_file_type(self, filename: str) -> str:
        """Infer file type for configuration files."""
        if filename.endswith(".json"):
            return "json"
        if filename.endswith(".config"):
            return "xml"
        if filename.endswith(".props") or filename.endswith(".targets"):
            return "msbuild"
        if filename == ".editorconfig":
            return "editorconfig"
        if filename == ".runsettings":
            return "xml"
        return "unknown"

    def detect_tools(self, project_path: Path, _config_files: list[ConfigFile] | None = None) -> dict[str, bool]:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            Dictionary mapping tool names to whether they are configured
        """
        tools = {}

        # Check for .editorconfig
        tools["editorconfig"] = (project_path / ".editorconfig").exists()

        # Check for StyleCop (in .csproj files)
        tools["stylecop"] = False
        csproj_files = list(project_path.glob("**/*.csproj"))
        for csproj in csproj_files:
            try:
                content = csproj.read_text()
                if "StyleCop" in content:
                    tools["stylecop"] = True
                    break
            except OSError as exc:
                debug("Failed to read %s: %s", csproj, exc)

        # Check for dotnet-format (usually in workflows)
        tools["dotnet-format"] = False

        # Check for GitHub Actions workflows
        workflows_dir = project_path / ".github" / "workflows"
        if workflows_dir.exists():
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            for workflow in workflow_files:
                content = workflow.read_text()
                if "dotnet format" in content:
                    tools["dotnet-format"] = True
                if "dotnet test" in content:
                    tools["dotnet-test"] = True

        return tools

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        """Get recommended tools for C# projects.

        Returns:
            List of tool recommendations
        """
        return [
            ToolRecommendation(
                tool_name="dotnet-format",
                category="quality",
                description=".NET code formatter (built-in)",
                config_section=".editorconfig",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="editorconfig",
                category="quality",
                description="EditorConfig for consistent formatting",
                config_section=".editorconfig",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="stylecop",
                category="quality",
                description="StyleCop code style analyzer",
                config_section=".csproj",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="dotnet-test",
                category="testing",
                description=".NET testing framework (built-in)",
                config_section="built-in",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="security-scan",
                category="security",
                description="Security code scan for .NET",
                config_section="built-in",
                priority=2,
            ),
        ]

    def get_security_tools(self) -> list[str]:
        """Get list of security-focused tools for C#.

        Returns:
            List of tool names
        """
        return ["security-scan"]

    def get_quality_tools(self) -> list[str]:
        """Get list of code quality tools for C#.

        Returns:
            List of tool names
        """
        return ["dotnet-format", "stylecop"]

    def get_formatting_tools(self) -> list[str]:
        """Get list of code formatting tools for C#.

        Returns:
            List of tool names
        """
        return ["dotnet-format"]

    def parse_dependencies(self, project_path: Path, _config_files: list[ConfigFile]) -> list[str]:
        """Parse project dependencies from .csproj files.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            List of dependency names
        """
        dependencies = []

        # Parse .csproj files
        csproj_files = list(project_path.glob("**/*.csproj"))
        for csproj in csproj_files:
            try:
                tree = ET.parse(csproj)  # noqa: S314  # Parsing local project files, not untrusted data
                root = tree.getroot()

                # Find PackageReference elements
                for package_ref in root.findall(".//PackageReference"):
                    include = package_ref.get("Include")
                    if include:
                        dependencies.append(include)
            except (ET.ParseError, OSError) as exc:
                debug("Failed to parse %s: %s", csproj, exc)

        return list(set(dependencies))  # Remove duplicates
