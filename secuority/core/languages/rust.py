"""Rust language analyzer implementation."""

from pathlib import Path
from typing import Any, cast

from secuority.utils.logger import debug

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

from .base import (
    ConfigFile,
    LanguageAnalyzer,
    LanguageDetectionResult,
    ToolRecommendation,
    ToolStatusMap,
)


class RustAnalyzer(LanguageAnalyzer):
    """Analyzer for Rust projects.

    Detects Rust configuration files, tools, and provides recommendations
    for Rust-specific quality and security tools.
    """

    def _get_language_name(self) -> str:
        """Get the name of this language."""
        return "rust"

    @staticmethod
    def _coerce_str_mapping(mapping: object) -> dict[str, Any]:
        if not isinstance(mapping, dict):
            return {}
        typed_mapping = cast(dict[Any, Any], mapping)
        return {str(key): value for key, value in typed_mapping.items() if isinstance(key, str)}

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses Rust.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score
        """
        indicators: list[str] = []
        confidence = 0.0

        indicator_checks = [
            (project_path / "Cargo.toml", "Cargo.toml", 0.6),
            (project_path / "Cargo.lock", "Cargo.lock", 0.2),
            (project_path / "target", "target/", 0.1),
        ]
        for path, label, weight in indicator_checks:
            if path.exists():
                indicators.append(label)
                confidence += weight

        # Check for .rs files
        rs_files = list(project_path.glob("**/*.rs"))
        if rs_files:
            total_files = len(rs_files)
            indicators.append(f"{total_files} .rs files")
            confidence += 0.3

        toolchain_files = [project_path / "rust-toolchain", project_path / "rust-toolchain.toml"]
        if any(path.exists() for path in toolchain_files):
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
        config_files: list[ConfigFile] = []
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

    def detect_tools(self, project_path: Path, config_files: list[ConfigFile]) -> ToolStatusMap:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary mapping tool names to whether they are configured
        """
        resolved_configs = config_files or self.detect_config_files(project_path)
        config_names = {cfg.name for cfg in resolved_configs if cfg.exists}

        tools: ToolStatusMap = {
            "rustfmt": "rustfmt.toml" in config_names or ".rustfmt.toml" in config_names,
            "clippy": "clippy.toml" in config_names or ".clippy.toml" in config_names,
            "cargo-audit": False,
            "cargo-deny": "deny.toml" in config_names,
            "cargo-tarpaulin": "tarpaulin.toml" in config_names,
        }

        cargo_config = next((cfg for cfg in resolved_configs if cfg.name == "Cargo.toml" and cfg.path), None)
        cargo_toml = cargo_config.path if cargo_config and cargo_config.path else project_path / "Cargo.toml"
        cargo_data = self._load_cargo_toml(cargo_toml)
        tools["cargo-audit"] = bool(cargo_data and self._has_cargo_audit_dependency(cargo_data))

        # Check for GitHub Actions workflows
        workflows_dir = project_path / ".github" / "workflows"
        if workflows_dir.exists():
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
            workflow_markers = {
                "cargo clippy": "clippy",
                "cargo fmt": "rustfmt",
                "cargo audit": "cargo-audit",
                "cargo deny": "cargo-deny",
                "cargo tarpaulin": "cargo-tarpaulin",
            }
            for workflow in workflow_files:
                content = workflow.read_text()
                for marker, tool_name in workflow_markers.items():
                    if marker in content:
                        tools[tool_name] = True

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
        dependencies: list[str] = []
        resolved_configs = config_files or self.detect_config_files(project_path)
        cargo_config = next((cfg for cfg in resolved_configs if cfg.name == "Cargo.toml" and cfg.path), None)
        cargo_toml = cargo_config.path if cargo_config and cargo_config.path else project_path / "Cargo.toml"

        cargo_data = self._load_cargo_toml(cargo_toml)
        if cargo_data:
            deps = self._coerce_str_mapping(cargo_data.get("dependencies"))
            if deps:
                self._extend_with_keys(dependencies, deps)

            dev_deps = self._coerce_str_mapping(cargo_data.get("dev-dependencies"))
            if dev_deps:
                self._extend_with_keys(dependencies, dev_deps)

        return dependencies

    def _has_cargo_audit_dependency(self, cargo_data: dict[str, Any]) -> bool:
        dev_deps = self._coerce_str_mapping(cargo_data.get("dev-dependencies"))
        return "cargo-audit" in dev_deps

    def _load_cargo_toml(self, path: Path) -> dict[str, Any] | None:
        loader = tomllib
        if loader is None or not path.exists():
            return None
        active_loader = cast(Any, loader)
        try:
            with path.open("rb") as f:
                raw_data: object = active_loader.load(f)
        except Exception as exc:  # pragma: no cover - defensive
            debug(f"Failed to parse Cargo.toml at {path}: {exc}")
            return None
        if not isinstance(raw_data, dict):
            return None
        return cast(dict[str, Any], raw_data)

    @staticmethod
    def _extend_with_keys(target: list[str], mapping: dict[str, Any]) -> None:
        target.extend(str(name) for name in mapping)
