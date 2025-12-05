"""C++ language analyzer implementation."""

import json
from pathlib import Path
from typing import Any, cast

from secuority.utils.logger import debug

from .base import (
    ConfigFile,
    LanguageAnalyzer,
    LanguageDetectionResult,
    ToolRecommendation,
    ToolStatusMap,
)


class CppAnalyzer(LanguageAnalyzer):
    """Analyzer for C++ projects.

    Detects C++ configuration files, tools, and provides recommendations
    for C++-specific quality and security tools.
    """

    def _get_language_name(self) -> str:
        """Get the name of this language."""
        return "cpp"

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        """Detect if the project uses C++.

        Args:
            project_path: Path to the project directory

        Returns:
            LanguageDetectionResult with confidence score
        """
        indicators: list[str] = []
        confidence = 0.0

        # Check for CMakeLists.txt (primary indicator)
        if (project_path / "CMakeLists.txt").exists():
            indicators.append("CMakeLists.txt")
            confidence += 0.6

        # Check for .cpp/.cc/.cxx files
        cpp_files = (
            list(project_path.glob("**/*.cpp"))
            + list(project_path.glob("**/*.cc"))
            + list(project_path.glob("**/*.cxx"))
        )
        if cpp_files:
            total_files = len(cpp_files)
            indicators.append(f"{total_files} .cpp/.cc/.cxx files")
            confidence += 0.4

        # Check for header files
        header_files = (
            list(project_path.glob("**/*.h"))
            + list(project_path.glob("**/*.hpp"))
            + list(project_path.glob("**/*.hxx"))
        )
        if header_files:
            total_headers = len(header_files)
            indicators.append(f"{total_headers} .h/.hpp/.hxx files")
            confidence += 0.2

        # Check for Makefile
        if (project_path / "Makefile").exists():
            indicators.append("Makefile")
            confidence += 0.2

        # Check for build directory
        if (project_path / "build").exists():
            indicators.append("build/")
            confidence += 0.1

        # Check for vcpkg (package manager)
        if (project_path / "vcpkg.json").exists():
            indicators.append("vcpkg.json")
            confidence += 0.1

        # Check for Conan (package manager)
        if (project_path / "conanfile.txt").exists() or (project_path / "conanfile.py").exists():
            indicators.append("conanfile")
            confidence += 0.1

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        return LanguageDetectionResult(
            language="cpp",
            confidence=confidence,
            indicators=indicators,
        )

    def get_config_file_patterns(self) -> dict[str, str]:
        """Get configuration file patterns for C++.

        Returns:
            Dictionary mapping file names to descriptions
        """
        return {
            "CMakeLists.txt": "CMake build configuration",
            "Makefile": "Make build configuration",
            ".clang-format": "Clang-Format formatter configuration",
            ".clang-tidy": "Clang-Tidy linter configuration",
            "compile_commands.json": "Compilation database",
            "vcpkg.json": "vcpkg package manager manifest",
            "conanfile.txt": "Conan package manager configuration",
            "conanfile.py": "Conan package manager configuration (Python)",
            ".cppcheck": "Cppcheck configuration",
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
            if file_path.exists() and file_path.is_file():
                config_files.append(
                    ConfigFile(
                        name=pattern,
                        path=file_path,
                        exists=True,
                        file_type=self._determine_file_type(pattern),
                    ),
                )

        # Check for compile_commands.json in build directory
        build_compile_commands = project_path / "build" / "compile_commands.json"
        if build_compile_commands.exists():
            config_files.append(
                ConfigFile(
                    name="build/compile_commands.json",
                    path=build_compile_commands,
                    exists=True,
                    file_type="json",
                ),
            )

        return config_files

    def _determine_file_type(self, filename: str) -> str:
        """Infer file type for configuration files."""
        suffix_map = {
            ".json": "json",
            ".py": "python",
            ".txt": "text",
        }
        for suffix, file_type in suffix_map.items():
            if filename.endswith(suffix):
                return file_type

        special_map = {
            "CMakeLists.txt": "cmake",
            "Makefile": "make",
        }
        if filename in special_map:
            return special_map[filename]

        if filename.startswith(".clang") or filename == ".cppcheck":
            return "yaml"

        return "unknown"

    def detect_tools(self, project_path: Path, config_files: list[ConfigFile]) -> ToolStatusMap:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            Dictionary mapping tool names to whether they are configured
        """
        resolved_configs = config_files or self.detect_config_files(project_path)
        existing_configs = {cfg.name: cfg for cfg in resolved_configs if cfg.exists and cfg.path is not None}

        def has_config(*names: str) -> bool:
            return any(name in existing_configs for name in names)

        tools: ToolStatusMap = {
            "clang-format": has_config(".clang-format"),
            "clang-tidy": has_config(".clang-tidy"),
            "cppcheck": has_config(".cppcheck"),
            "cmake": has_config("CMakeLists.txt"),
            "vcpkg": has_config("vcpkg.json"),
            "conan": has_config("conanfile.txt", "conanfile.py"),
        }

        workflows_dir = project_path / ".github" / "workflows"
        workflow_files: list[Path] = []
        if workflows_dir.exists():
            workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        for workflow in workflow_files:
            content = workflow.read_text()
            if "clang-format" in content:
                tools["clang-format"] = True
            if "clang-tidy" in content:
                tools["clang-tidy"] = True
            if "cppcheck" in content:
                tools["cppcheck"] = True

        return tools

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        """Get recommended tools for C++ projects.

        Returns:
            List of tool recommendations
        """
        return [
            ToolRecommendation(
                tool_name="clang-format",
                category="quality",
                description="LLVM code formatter for C++",
                config_section=".clang-format",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="clang-tidy",
                category="quality",
                description="LLVM-based C++ linter",
                config_section=".clang-tidy",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="cppcheck",
                category="quality",
                description="Static analysis tool for C/C++",
                config_section=".cppcheck",
                priority=2,
            ),
            ToolRecommendation(
                tool_name="cmake",
                category="build",
                description="Cross-platform build system",
                config_section="CMakeLists.txt",
                priority=1,
            ),
            ToolRecommendation(
                tool_name="vcpkg",
                category="dependency",
                description="C++ package manager from Microsoft",
                config_section="vcpkg.json",
                priority=2,
            ),
        ]

    def get_security_tools(self) -> list[str]:
        """Get list of security-focused tools for C++.

        Returns:
            List of tool names
        """
        return ["clang-tidy", "cppcheck"]

    def get_quality_tools(self) -> list[str]:
        """Get list of code quality tools for C++.

        Returns:
            List of tool names
        """
        return ["clang-tidy", "cppcheck"]

    def get_formatting_tools(self) -> list[str]:
        """Get list of code formatting tools for C++.

        Returns:
            List of tool names
        """
        return ["clang-format"]

    def parse_dependencies(self, project_path: Path, config_files: list[ConfigFile]) -> list[str]:
        """Parse project dependencies from vcpkg.json or conanfile.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            List of dependency names
        """
        dependencies: list[str] = []
        resolved_configs = config_files or self.detect_config_files(project_path)

        def get_config_path(name: str) -> Path | None:
            for cfg in resolved_configs:
                if cfg.name == name and cfg.path is not None and cfg.exists:
                    return cfg.path
            return None

        vcpkg_json = get_config_path("vcpkg.json") or (project_path / "vcpkg.json")
        if vcpkg_json.exists():
            dependencies.extend(self._collect_vcpkg_dependencies(vcpkg_json))

        conanfile_txt = get_config_path("conanfile.txt") or (project_path / "conanfile.txt")
        if conanfile_txt.exists():
            dependencies.extend(self._collect_conan_dependencies(conanfile_txt))

        return dependencies

    def _collect_vcpkg_dependencies(self, manifest_path: Path) -> list[str]:
        deps: list[str] = []
        try:
            with manifest_path.open(encoding="utf-8") as f:
                vcpkg_raw: Any = json.load(f)
                if isinstance(vcpkg_raw, dict):
                    vcpkg_data = cast(dict[str, object], vcpkg_raw)
                    deps_field = vcpkg_data.get("dependencies")
                    if isinstance(deps_field, list):
                        deps_list = cast(list[object], deps_field)
                        for dep in deps_list:
                            if isinstance(dep, str):
                                deps.append(dep)
                            elif isinstance(dep, dict):
                                dep_map = cast(dict[str, object], dep)
                                dep_name = dep_map.get("name")
                                if isinstance(dep_name, str) and dep_name:
                                    deps.append(dep_name)
        except (OSError, json.JSONDecodeError) as exc:
            debug(f"Failed to parse vcpkg.json at {manifest_path}: {exc}")
        return deps

    def _collect_conan_dependencies(self, conanfile_path: Path) -> list[str]:
        deps: list[str] = []
        try:
            content = conanfile_path.read_text(encoding="utf-8")
            in_requires = False
            for raw_line in content.split("\n"):
                line = raw_line.strip()
                if line == "[requires]":
                    in_requires = True
                    continue
                if line.startswith("["):
                    in_requires = False
                if in_requires and line:
                    deps.append(line.split("/", 1)[0])
        except OSError as exc:
            debug(f"Failed to parse conanfile {conanfile_path}: {exc}")
        return deps
