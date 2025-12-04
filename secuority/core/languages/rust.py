"""Rust language analyzer implementation."""

from pathlib import Path

from .base import ConfigFile, LanguageAnalyzer, LanguageDetectionResult, ToolRecommendation


class RustAnalyzer(LanguageAnalyzer):
    """Analyzer for Rust projects.

    Detects Rust configuration files, tools, and provides recommendations
    for Rust-specific quality and security tools.
    """

    def _get_language_name(self) -> str:
        """Get the name of this language."""
        return "rust"

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses Rust.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score
        """
        indicators = []
        confidence = 0.0

        # Check for Cargo.toml (primary indicator)
        if (project_path / "Cargo.toml").exists():
            indicators.append("Cargo.toml")
            confidence += 0.6

        # Check for Cargo.lock
        if (project_path / "Cargo.lock").exists():
            indicators.append("Cargo.lock")
            confidence += 0.2

        # Check for .rs files
        rs_files = list(project_path.glob("**/*.rs"))
        if rs_files:
            total_files = len(rs_files)
            indicators.append(f"{total_files} .rs files")
            confidence += 0.3

        # Check for target directory
        if (project_path / "target").exists():
            indicators.append("target/")
            confidence += 0.1

        # Check for rust-toolchain file
        if (project_path / "rust-toolchain").exists() or (project_path / "rust-toolchain.toml").exists():
            indicators.append("rust-toolchain")
            confidence += 0.1

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        return LanguageDetectionResult(
            language="rust",
            confidence=confidence,
            indicators=indicators,
        )

    def get_config_file_patterns(self) -> dict[str, str]:
        """Get configuration file patterns for Rust.

        Returns:
            Dictionary mapping file names to descriptions
        """
        return {
            "Cargo.toml": "Rust package configuration",
            "Cargo.lock": "Rust dependencies lock file",
            "rust-toolchain": "Rust toolchain version specification",
            "rust-toolchain.toml": "Rust toolchain configuration",
            "rustfmt.toml": "Rustfmt formatter configuration",
            ".rustfmt.toml": "Rustfmt formatter configuration (hidden)",
            "clippy.toml": "Clippy linter configuration",
            ".clippy.toml": "Clippy linter configuration (hidden)",
            ".cargo/config.toml": "Cargo build configuration",
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
        """Infer file type for configuration files."""
        if filename.endswith(".toml"):
            return "toml"
        if filename.endswith(".lock"):
            return "lock"
        if filename.endswith(".json"):
            return "json"
        return "unknown"

    def detect_tools(self, project_path: Path, config_files: list[ConfigFile] | None = None) -> dict[str, bool]:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary mapping tool names to whether they are configured
        """
        tools = {}

        # Check for rustfmt configuration
        tools["rustfmt"] = (project_path / "rustfmt.toml").exists() or (project_path / ".rustfmt.toml").exists()

        # Check for clippy configuration
        tools["clippy"] = (project_path / "clippy.toml").exists() or (project_path / ".clippy.toml").exists()

        # Check for cargo-audit (check in Cargo.toml)
        cargo_toml = project_path / "Cargo.toml"
        if cargo_toml.exists():
            try:
                import tomllib

                with cargo_toml.open("rb") as f:
                    cargo_data = tomllib.load(f)
                    # Check if cargo-audit is in dev-dependencies
                    dev_deps = cargo_data.get("dev-dependencies", {})
                    tools["cargo-audit"] = "cargo-audit" in dev_deps
            except Exception:
                tools["cargo-audit"] = False
        else:
            tools["cargo-audit"] = False

        # Check for cargo-deny configuration
        tools["cargo-deny"] = (project_path / "deny.toml").exists()

        # Check for cargo-tarpaulin (code coverage)
        tools["cargo-tarpaulin"] = (project_path / "tarpaulin.toml").exists()

        # Check for GitHub Actions workflows
        workflows_dir = project_path / ".github" / "workflows"
        if workflows_dir.exists():
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            for workflow in workflow_files:
                content = workflow.read_text()
                if "cargo clippy" in content:
                    tools["clippy"] = True
                if "cargo fmt" in content:
                    tools["rustfmt"] = True
                if "cargo audit" in content:
                    tools["cargo-audit"] = True
                if "cargo deny" in content:
                    tools["cargo-deny"] = True
                if "cargo tarpaulin" in content:
                    tools["cargo-tarpaulin"] = True

        return tools

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        """Get recommended tools for Rust projects.

        Returns:
            List of tool recommendations
        """
        return [
            ToolRecommendation(
                tool_name="clippy",
                category="quality",
                description="Rust linter for catching common mistakes",
                config_section="clippy.toml",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="rustfmt",
                category="quality",
                description="Rust code formatter",
                config_section="rustfmt.toml",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="cargo-audit",
                category="security",
                description="Audit Cargo.lock for security vulnerabilities",
                config_section="Cargo.toml",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="cargo-deny",
                category="security",
                description="Lint dependencies for security and license issues",
                config_section="deny.toml",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="cargo-tarpaulin",
                category="testing",
                description="Code coverage tool for Rust",
                config_section="tarpaulin.toml",
                priority=3,
            ),
        ]

    def get_security_tools(self) -> list[str]:
        """Get list of security-focused tools for Rust.

        Returns:
            List of tool names
        """
        return ["cargo-audit", "cargo-deny"]

    def get_quality_tools(self) -> list[str]:
        """Get list of code quality tools for Rust.

        Returns:
            List of tool names
        """
        return ["clippy"]

    def get_formatting_tools(self) -> list[str]:
        """Get list of code formatting tools for Rust.

        Returns:
            List of tool names
        """
        return ["rustfmt"]

    def parse_dependencies(self, project_path: Path, config_files: list[ConfigFile]) -> list[str]:
        """Parse project dependencies from Cargo.toml.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            List of dependency names
        """
        dependencies = []
        cargo_toml = project_path / "Cargo.toml"

        if cargo_toml.exists():
            try:
                import tomllib

                with cargo_toml.open("rb") as f:
                    cargo_data = tomllib.load(f)

                    # Parse dependencies
                    deps = cargo_data.get("dependencies", {})
                    dependencies.extend(deps.keys())

                    # Parse dev-dependencies
                    dev_deps = cargo_data.get("dev-dependencies", {})
                    dependencies.extend(dev_deps.keys())
            except Exception:
                pass

        return dependencies
