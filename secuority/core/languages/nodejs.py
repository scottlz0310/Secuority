"""Node.js language analyzer implementation."""

import json
from pathlib import Path

from .base import ConfigFile, LanguageAnalyzer, LanguageDetectionResult, ToolRecommendation


class NodeJSAnalyzer(LanguageAnalyzer):
    """Analyzer for Node.js projects.

    Detects Node.js configuration files, tools, and provides recommendations
    for Node.js-specific quality and security tools, with focus on modern
    tools like Biome.
    """

    def _get_language_name(self) -> str:
        """Get the name of this language."""
        return "nodejs"

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses Node.js.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score
        """
        indicators = []
        confidence = 0.0

        # Check for package.json
        if (project_path / "package.json").exists():
            indicators.append("package.json")
            confidence += 0.5

        # Check for lock files
        if (project_path / "package-lock.json").exists():
            indicators.append("package-lock.json")
            confidence += 0.2
        if (project_path / "yarn.lock").exists():
            indicators.append("yarn.lock")
            confidence += 0.2
        if (project_path / "pnpm-lock.yaml").exists():
            indicators.append("pnpm-lock.yaml")
            confidence += 0.2

        # Check for .js/.ts files
        js_files = list(project_path.glob("**/*.js"))
        ts_files = list(project_path.glob("**/*.ts"))
        if js_files or ts_files:
            total_files = len(js_files) + len(ts_files)
            indicators.append(f"{total_files} .js/.ts files")
            confidence += 0.4

        # Check for node_modules
        if (project_path / "node_modules").exists():
            indicators.append("node_modules/")
            confidence += 0.1

        # Check for tsconfig.json
        if (project_path / "tsconfig.json").exists():
            indicators.append("tsconfig.json")
            confidence += 0.2

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        return LanguageDetectionResult(
            language="nodejs",
            confidence=confidence,
            indicators=indicators,
        )

    def get_config_file_patterns(self) -> dict[str, str]:
        """Get configuration file patterns for Node.js.

        Returns:
            Dictionary mapping file names to descriptions
        """
        return {
            "package.json": "Node.js package configuration",
            "package-lock.json": "npm dependencies lock file",
            "yarn.lock": "Yarn dependencies lock file",
            "pnpm-lock.yaml": "pnpm dependencies lock file",
            "tsconfig.json": "TypeScript configuration",
            "biome.json": "Biome formatter/linter configuration",
            ".eslintrc.json": "ESLint linter configuration",
            ".eslintrc.js": "ESLint linter configuration (JS)",
            ".prettierrc": "Prettier formatter configuration",
            "jest.config.js": "Jest testing configuration",
            "vitest.config.ts": "Vitest testing configuration",
            "playwright.config.ts": "Playwright testing configuration",
        }

    def detect_config_files(self, project_path: Path) -> list[ConfigFile]:
        """Detect configuration files present in the project.

        Args:
            project_path: Path to the project directory

        Returns:
            List of ConfigFile objects for files that exist
        """
        patterns = self.get_config_file_patterns()
        config_files = []

        for filename in patterns:
            file_path = project_path / filename
            file_type = self._determine_file_type(filename)

            config_files.append(
                ConfigFile(
                    name=filename,
                    path=file_path if file_path.exists() else None,
                    exists=file_path.exists(),
                    file_type=file_type,
                ),
            )

        return config_files

    def _determine_file_type(self, filename: str) -> str:
        """Determine file type from filename."""
        if filename.endswith(".json") or filename == ".prettierrc":
            return "json"
        if filename.endswith((".yaml", ".yml")):
            return "yaml"
        if filename.endswith((".js", ".mjs", ".cjs")):
            return "javascript"
        if filename.endswith((".ts", ".mts", ".cts")):
            return "typescript"
        if filename.endswith(".lock"):
            return "lock"
        return "unknown"

    def detect_tools(self, _project_path: Path, config_files: list[ConfigFile]) -> dict[str, bool]:
        """Detect which tools are configured in the project.

        Args:
            _project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            Dictionary mapping tool names to whether they're configured
        """
        tools = {
            # Quality tools
            "biome": False,
            "eslint": False,
            "typescript": False,
            "prettier": False,
            # Security tools
            "npm-audit": False,
            "osv-scanner": False,
            "snyk": False,
            # Testing tools
            "jest": False,
            "vitest": False,
            "playwright": False,
            # Dependency managers
            "npm": False,
            "yarn": False,
            "pnpm": False,
        }

        # Check package.json
        package_json_file = next((f for f in config_files if f.name == "package.json" and f.exists), None)
        if package_json_file and package_json_file.path:
            tools.update(self._detect_tools_in_package_json(package_json_file.path))

        # Check standalone config files
        tools.update(self._detect_tools_from_config_files(config_files))

        return tools

    def _detect_tools_in_package_json(self, package_json_path: Path) -> dict[str, bool]:
        """Detect tools configured in package.json."""
        tools = {}

        try:
            with open(package_json_path, encoding="utf-8") as f:
                data = json.load(f)

            # Check dependencies and devDependencies
            all_deps = {}
            all_deps.update(data.get("dependencies", {}))
            all_deps.update(data.get("devDependencies", {}))

            # Check for tools in dependencies
            tools["biome"] = "@biomejs/biome" in all_deps
            tools["eslint"] = "eslint" in all_deps
            tools["typescript"] = "typescript" in all_deps
            tools["prettier"] = "prettier" in all_deps
            tools["jest"] = "jest" in all_deps
            tools["vitest"] = "vitest" in all_deps
            tools["playwright"] = "@playwright/test" in all_deps or "playwright" in all_deps
            tools["snyk"] = "snyk" in all_deps

            # Check package manager from lockfile indicators
            # (will be overridden by _detect_tools_from_config_files)

        except Exception:
            # If we can't read the file, skip it
            pass

        return tools

    def _detect_tools_from_config_files(self, config_files: list[ConfigFile]) -> dict[str, bool]:
        """Detect tools from standalone configuration files."""
        tools = {}

        file_map = {
            "biome.json": "biome",
            ".eslintrc.json": "eslint",
            ".eslintrc.js": "eslint",
            "tsconfig.json": "typescript",
            ".prettierrc": "prettier",
            "jest.config.js": "jest",
            "vitest.config.ts": "vitest",
            "playwright.config.ts": "playwright",
            "package-lock.json": "npm",
            "yarn.lock": "yarn",
            "pnpm-lock.yaml": "pnpm",
        }

        for config_file in config_files:
            if config_file.exists and config_file.name in file_map:
                tool_name = file_map[config_file.name]
                tools[tool_name] = True

        return tools

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        """Get list of recommended tools for Node.js.

        Returns:
            List of ToolRecommendation objects, ordered by priority
        """
        return [
            ToolRecommendation(
                tool_name="biome",
                category="quality",
                description="Fast formatter and linter (replaces ESLint + Prettier)",
                config_section="biome.json",
                priority=1,
                modern_alternative="eslint + prettier",
            ),
            ToolRecommendation(
                tool_name="typescript",
                category="quality",
                description="Static type checker for JavaScript",
                config_section="tsconfig.json",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="vitest",
                category="testing",
                description="Fast unit test framework (Vite-powered)",
                config_section="vitest.config.ts",
                priority=2,
                modern_alternative="jest",
            ),
            ToolRecommendation(
                tool_name="osv-scanner",
                category="security",
                description="Vulnerability scanner for dependencies",
                config_section="osv-scanner.toml",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="playwright",
                category="testing",
                description="End-to-end testing framework",
                config_section="playwright.config.ts",
                priority=3,
            ),
            ToolRecommendation(
                tool_name="pnpm",
                category="dependency",
                description="Fast, disk space efficient package manager",
                config_section="pnpm-lock.yaml",
                priority=1,
                modern_alternative="npm",
            ),
        ]

    def get_security_tools(self) -> list[str]:
        """Get list of security-focused tools for Node.js."""
        return ["npm-audit", "osv-scanner", "snyk"]

    def get_quality_tools(self) -> list[str]:
        """Get list of code quality tools for Node.js."""
        return ["biome", "eslint", "typescript", "prettier"]

    def get_formatting_tools(self) -> list[str]:
        """Get list of code formatting tools for Node.js."""
        return ["biome", "prettier"]

    def parse_dependencies(self, _project_path: Path, config_files: list[ConfigFile]) -> list[str]:
        """Parse project dependencies.

        Args:
            _project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            List of dependency names
        """
        dependencies = []

        # Parse package.json
        package_json_file = next((f for f in config_files if f.name == "package.json" and f.exists), None)
        if package_json_file and package_json_file.path:
            dependencies.extend(self._parse_package_json_dependencies(package_json_file.path))

        # Remove duplicates
        return list(set(dependencies))

    def _parse_package_json_dependencies(self, package_json_path: Path) -> list[str]:
        """Parse dependencies from package.json."""
        dependencies = []

        try:
            with open(package_json_path, encoding="utf-8") as f:
                data = json.load(f)

            # Get both dependencies and devDependencies
            if "dependencies" in data:
                dependencies.extend(data["dependencies"].keys())

            if "devDependencies" in data:
                dependencies.extend(data["devDependencies"].keys())

        except Exception:
            pass

        return dependencies
