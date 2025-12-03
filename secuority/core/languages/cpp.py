"""C++ language analyzer implementation."""

from pathlib import Path

from .base import ConfigFile, LanguageAnalyzer, LanguageDetectionResult, ToolRecommendation


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
        indicators = []
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
        config_files = []
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
                    )
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
                )
            )

        return config_files

    def _determine_file_type(self, filename: str) -> str:
        """Infer file type for configuration files."""
        if filename.endswith(".json"):
            return "json"
        if filename.endswith(".py"):
            return "python"
        if filename.endswith(".txt"):
            return "text"
        if filename in {"CMakeLists.txt"}:
            return "cmake"
        if filename == "Makefile":
            return "make"
        if filename.startswith(".clang") or filename == ".cppcheck":
            return "yaml"
        return "unknown"

    def detect_tools(self, project_path: Path, config_files: list[ConfigFile] | None = None) -> dict[str, bool]:
        """Detect which tools are configured in the project.

        Args:
            project_path: Path to the project directory
            config_files: List of configuration files detected

        Returns:
            Dictionary mapping tool names to whether they are configured
        """
        tools = {}

        # Check for clang-format configuration
        tools["clang-format"] = (project_path / ".clang-format").exists()

        # Check for clang-tidy configuration
        tools["clang-tidy"] = (project_path / ".clang-tidy").exists()

        # Check for cppcheck
        tools["cppcheck"] = (project_path / ".cppcheck").exists()

        # Check for CMake
        tools["cmake"] = (project_path / "CMakeLists.txt").exists()

        # Check for vcpkg
        tools["vcpkg"] = (project_path / "vcpkg.json").exists()

        # Check for Conan
        tools["conan"] = (
            (project_path / "conanfile.txt").exists()
            or (project_path / "conanfile.py").exists()
        )

        # Check for GitHub Actions workflows
        workflows_dir = project_path / ".github" / "workflows"
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
        dependencies = []

        # Parse vcpkg.json
        vcpkg_json = project_path / "vcpkg.json"
        if vcpkg_json.exists():
            try:
                import json
                with open(vcpkg_json) as f:
                    vcpkg_data = json.load(f)
                    deps = vcpkg_data.get("dependencies", [])
                    for dep in deps:
                        if isinstance(dep, str):
                            dependencies.append(dep)
                        elif isinstance(dep, dict):
                            dependencies.append(dep.get("name", ""))
            except Exception:
                pass

        # Parse conanfile.txt
        conanfile_txt = project_path / "conanfile.txt"
        if conanfile_txt.exists():
            try:
                content = conanfile_txt.read_text()
                in_requires = False
                for line in content.split('\n'):
                    line = line.strip()
                    if line == "[requires]":
                        in_requires = True
                        continue
                    if line.startswith('['):
                        in_requires = False
                    if in_requires and line:
                        # Format: package/version
                        dep_name = line.split('/')[0]
                        dependencies.append(dep_name)
            except Exception:
                pass

        return dependencies
