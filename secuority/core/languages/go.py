"""Go language analyzer implementation."""

from pathlib import Path

from secuority.utils.logger import debug

from .base import ConfigFile, LanguageAnalyzer, LanguageDetectionResult, ToolRecommendation


class GoAnalyzer(LanguageAnalyzer):
    """Analyzer for Go projects.

    Detects Go configuration files, tools, and provides recommendations
    for Go-specific quality and security tools.
    """

    def _get_language_name(self) -> str:
        """Get the name of this language."""
        return "go"

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses Go.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score
        """
        indicators = []
        confidence = 0.0

        # Check for go.mod (primary indicator)
        if (project_path / "go.mod").exists():
            indicators.append("go.mod")
            confidence += 0.6

        # Check for go.sum
        if (project_path / "go.sum").exists():
            indicators.append("go.sum")
            confidence += 0.2

        # Check for .go files
        go_files = list(project_path.glob("**/*.go"))
        if go_files:
            total_files = len(go_files)
            indicators.append(f"{total_files} .go files")
            confidence += 0.3

        # Check for go.work (Go workspaces)
        if (project_path / "go.work").exists():
            indicators.append("go.work")
            confidence += 0.1

        # Check for vendor directory
        if (project_path / "vendor").exists():
            indicators.append("vendor/")
            confidence += 0.1

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        return LanguageDetectionResult(
            language="go",
            confidence=confidence,
            indicators=indicators,
        )

    def get_config_file_patterns(self) -> dict[str, str]:
        """Get configuration file patterns for Go.

        Returns:
            Dictionary mapping file names to descriptions
        """
        return {
            "go.mod": "Go module configuration",
            "go.sum": "Go dependencies checksum file",
            "go.work": "Go workspace configuration",
            ".golangci.yml": "golangci-lint configuration",
            ".golangci.yaml": "golangci-lint configuration",
            ".gofmt": "gofmt formatter configuration",
            ".govet": "go vet configuration",
        }

    def detect_config_files(self, project_path: Path) -> list[ConfigFile]:
        """Detect configuration files present in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            List of detected configuration files
        """
        config_files = []
        patterns = self.get_config_file_patterns()

        for pattern in patterns:
            file_path = project_path / pattern
            if not file_path.exists() or not file_path.is_file():
                continue
            config_files.append(
                ConfigFile(
                    name=pattern,
                    path=file_path,
                    exists=True,
                    file_type=self._determine_file_type(pattern),
                ),
            )

        return config_files

    def _determine_file_type(self, filename: str) -> str:
        """Determine file type based on extension."""
        if filename.endswith(".mod"):
            return "module"
        if filename.endswith(".sum"):
            return "checksum"
        if filename.endswith(".work"):
            return "workspace"
        if filename.endswith((".yml", ".yaml")):
            return "yaml"
        if filename.startswith(".go"):
            return "config"
        return "unknown"

    def detect_tools(self, project_path: Path, _config_files: list[ConfigFile] | None = None) -> dict[str, bool]:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary mapping tool names to whether they are configured
        """
        tools = {}

        # Check for golangci-lint configuration
        tools["golangci-lint"] = (project_path / ".golangci.yml").exists() or (project_path / ".golangci.yaml").exists()

        # Check for gofmt (always available with Go installation)
        tools["gofmt"] = (project_path / "go.mod").exists()

        # Check for go vet (always available with Go installation)
        tools["govet"] = (project_path / "go.mod").exists()

        # Check for govulncheck (security scanner)
        # This is typically used in CI, so check workflows
        workflows_dir = project_path / ".github" / "workflows"
        tools["govulncheck"] = False
        if workflows_dir.exists():
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            for workflow in workflow_files:
                content = workflow.read_text()
                if "govulncheck" in content:
                    tools["govulncheck"] = True
                if "golangci-lint" in content:
                    tools["golangci-lint"] = True
                if "go test" in content:
                    tools["gotest"] = True

        # Check for gosec (security scanner)
        tools["gosec"] = False
        if workflows_dir.exists():
            for workflow in workflow_files:
                content = workflow.read_text()
                if "gosec" in content:
                    tools["gosec"] = True

        return tools

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        """Get recommended tools for Go projects.

        Returns:
            List of tool recommendations
        """
        return [
            ToolRecommendation(
                tool_name="golangci-lint",
                category="quality",
                description="Fast linters runner for Go (runs 50+ linters)",
                config_section=".golangci.yml",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="gofmt",
                category="quality",
                description="Go code formatter (built-in)",
                config_section="built-in",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="govet",
                category="quality",
                description="Go static analyzer (built-in)",
                config_section="built-in",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="govulncheck",
                category="security",
                description="Go vulnerability scanner from Go team",
                config_section="built-in",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="gosec",
                category="security",
                description="Security checker for Go code",
                config_section="gosec.json",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="gotest",
                category="testing",
                description="Go testing framework (built-in)",
                config_section="built-in",
                priority=1,
            ),
        ]

    def get_security_tools(self) -> list[str]:
        """Get list of security-focused tools for Go.

        Returns:
            List of tool names
        """
        return ["govulncheck", "gosec"]

    def get_quality_tools(self) -> list[str]:
        """Get list of code quality tools for Go.

        Returns:
            List of tool names
        """
        return ["golangci-lint", "govet"]

    def get_formatting_tools(self) -> list[str]:
        """Get list of code formatting tools for Go.

        Returns:
            List of tool names
        """
        return ["gofmt"]

    def parse_dependencies(self, project_path: Path, _config_files: list[ConfigFile]) -> list[str]:
        """Parse project dependencies from go.mod.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            List of dependency names
        """
        dependencies = []
        go_mod = project_path / "go.mod"

        if go_mod.exists():
            try:
                content = go_mod.read_text()
                # Simple parsing of go.mod
                in_require = False
                for raw_line in content.split("\n"):
                    line = raw_line.strip()
                    if line.startswith("require"):
                        in_require = True
                        # Handle single-line require
                        if "(" not in line and line.count(" ") >= 2:
                            parts = line.split()
                            if len(parts) >= 2:
                                dependencies.append(parts[1])
                        continue
                    if in_require:
                        if line == ")":
                            in_require = False
                            continue
                        if line and not line.startswith("//"):
                            parts = line.split()
                            if parts:
                                dependencies.append(parts[0])
            except OSError as exc:
                debug("Failed to parse go.mod at %s: %s", go_mod, exc)

        return dependencies
