"""Project analyzer for detecting configuration files and project state."""

import contextlib
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict, cast

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

from ..models.exceptions import GitHubAPIError, ProjectAnalysisError
from ..models.interfaces import (
    DependencyAnalysis,
    DependencyManager,
    GitHubAnalysisResult,
    GitHubWorkflowSummary,
    Package,
    ProjectAnalyzerInterface,
    ProjectState,
    QualityTool,
    SecurityTool,
    ToolConfig,
    Workflow,
    validate_project_path,
)
from ..utils.logger import get_logger
from .github_client import GitHubClient
from .languages import LanguageAnalysisResult, get_global_registry

logger = get_logger(__name__)

ConfigFiles = dict[str, Path]


class ProjectInfo(TypedDict, total=False):
    name: str
    version: str
    description: str
    license: str
    author_name: str
    author_email: str
    homepage: str
    repository: str
    issues: str


PRECOMMIT_TOOL_PATTERNS: dict[str, list[str]] = {
    "ruff": ["ruff", "astral-sh/ruff"],
    "mypy": ["mypy", "pre-commit/mirrors-mypy"],
    "black": ["black", "psf/black"],
    "isort": ["isort", "pycqa/isort"],
    "flake8": ["flake8", "pycqa/flake8"],
    "pylint": ["pylint", "pycqa/pylint"],
    "bandit": ["bandit", "pycqa/bandit"],
    "safety": ["safety", "pyupio/safety"],
    "gitleaks": ["gitleaks", "zricethezav/gitleaks"],
}


class ProjectAnalyzer(ProjectAnalyzerInterface):
    """Analyzes Python projects to detect configuration files and project state."""

    def analyze_project(self, project_path: Path) -> ProjectState:
        """Analyze a Python project and return its current state."""
        if not validate_project_path(project_path):
            raise ProjectAnalysisError(f"Invalid project path: {project_path}")

        # Initialize project state
        project_state = ProjectState(project_path=project_path)

        # Detect configuration files
        config_files = self.detect_configuration_files(project_path)
        project_state.has_pyproject_toml = "pyproject.toml" in config_files
        project_state.has_requirements_txt = "requirements.txt" in config_files
        project_state.has_setup_py = "setup.py" in config_files
        project_state.has_gitignore = ".gitignore" in config_files
        project_state.has_pre_commit_config = ".pre-commit-config.yaml" in config_files
        project_state.has_security_md = "SECURITY.md" in config_files

        # Detect dependency manager
        project_state.dependency_manager = self._detect_dependency_manager(project_path)

        # Analyze dependencies if files exist
        if project_state.has_requirements_txt or project_state.has_pyproject_toml:
            dependency_analysis = self._analyze_dependencies_internal(project_path)
            project_state.dependency_analysis = dependency_analysis

        # Detect configured tools
        project_state.current_tools = self._detect_configured_tools(project_path, config_files)

        # Check security and quality tools
        project_state.security_tools = self._check_security_tools(project_path, config_files)
        project_state.quality_tools = self._check_quality_tools(project_path, config_files)

        # Detect CI workflows
        project_state.ci_workflows = self._detect_ci_workflows(project_path)

        # Detect Python version
        project_state.python_version = self._detect_python_version(project_path, config_files)
        project_state.language_analysis = self._analyze_languages(project_path)

        return project_state

    def detect_configuration_files(self, project_path: Path) -> ConfigFiles:
        """Detect existing configuration files in the project."""
        if not validate_project_path(project_path):
            raise ProjectAnalysisError(f"Invalid project path: {project_path}")

        config_files: ConfigFiles = {}

        # Standard Python configuration files
        standard_files = [
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "setup.cfg",
            ".gitignore",
            ".pre-commit-config.yaml",
            ".pre-commit-config.yml",
            "SECURITY.md",
            "tox.ini",
            "pytest.ini",
            "mypy.ini",
            ".flake8",
            ".pylintrc",
            "bandit.yaml",
            "bandit.yml",
        ]

        for filename in standard_files:
            file_path = project_path / filename
            if file_path.exists() and file_path.is_file():
                config_files[filename] = file_path

        # Check for additional dependency manager files
        dependency_files = [
            "poetry.lock",
            "Pipfile",
            "Pipfile.lock",
            "pdm.lock",
            "environment.yml",
            "environment.yaml",
            "conda.yml",
            "conda.yaml",
        ]

        for filename in dependency_files:
            file_path = project_path / filename
            if file_path.exists() and file_path.is_file():
                config_files[filename] = file_path

        return config_files

    def analyze_dependencies(self, project_path: Path) -> DependencyAnalysis:
        """Analyze project dependencies and their configuration."""
        if not validate_project_path(project_path):
            raise ProjectAnalysisError(f"Invalid project path: {project_path}")

        return self._analyze_dependencies_internal(project_path)

    def check_security_tools(self, project_path: Path) -> dict[str, bool]:
        """Check which security tools are configured in the project."""
        if not validate_project_path(project_path):
            raise ProjectAnalysisError(f"Invalid project path: {project_path}")

        config_files = self.detect_configuration_files(project_path)
        security_tools = self._check_security_tools(project_path, config_files)
        return {tool.value: status for tool, status in security_tools.items()}

    def _detect_dependency_manager(self, project_path: Path) -> DependencyManager | None:
        """Detect the dependency manager used by the project."""
        detectors: list[Callable[[Path], DependencyManager | None]] = [
            self._detect_poetry_manager,
            self._detect_pdm_manager,
            self._detect_pipenv_manager,
            self._detect_conda_manager,
            self._detect_setuptools_scm_manager,
        ]

        for detector in detectors:
            manager = detector(project_path)
            if manager:
                return manager

        return self._detect_pip_manager(project_path)

    @staticmethod
    def _detect_poetry_manager(project_path: Path) -> DependencyManager | None:
        return DependencyManager.POETRY if (project_path / "poetry.lock").exists() else None

    @staticmethod
    def _detect_pdm_manager(project_path: Path) -> DependencyManager | None:
        return DependencyManager.PDM if (project_path / "pdm.lock").exists() else None

    @staticmethod
    def _detect_pipenv_manager(project_path: Path) -> DependencyManager | None:
        return DependencyManager.PIPENV if (project_path / "Pipfile").exists() else None

    @staticmethod
    def _detect_conda_manager(project_path: Path) -> DependencyManager | None:
        conda_files = ["environment.yml", "environment.yaml", "conda.yml", "conda.yaml"]
        if any((project_path / filename).exists() for filename in conda_files):
            return DependencyManager.CONDA
        return None

    @staticmethod
    def _detect_setuptools_scm_manager(project_path: Path) -> DependencyManager | None:
        pyproject_path = project_path / "pyproject.toml"
        if not pyproject_path.exists():
            return None

        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError):
            return None

        if "tool" in data and "setuptools_scm" in data["tool"]:
            return DependencyManager.SETUPTOOLS_SCM
        return None

    @staticmethod
    def _detect_pip_manager(project_path: Path) -> DependencyManager | None:
        return DependencyManager.PIP if (project_path / "requirements.txt").exists() else None

    def _analyze_dependencies_internal(self, project_path: Path) -> DependencyAnalysis:
        """Internal method to analyze dependencies."""
        analysis = DependencyAnalysis()

        # Analyze requirements.txt
        requirements_path = project_path / "requirements.txt"
        if requirements_path.exists():
            analysis.requirements_packages = self._parse_requirements_txt(requirements_path)

        # Analyze pyproject.toml dependencies
        pyproject_path = project_path / "pyproject.toml"
        if pyproject_path.exists():
            pyproject_deps, extras = self._parse_pyproject_dependencies(pyproject_path)
            analysis.pyproject_dependencies = pyproject_deps
            analysis.extras_found = extras

        # Determine if migration is needed
        analysis.migration_needed = bool(analysis.requirements_packages) and not bool(analysis.pyproject_dependencies)

        # Check for conflicts (same package with different versions)
        analysis.conflicts = self._find_dependency_conflicts(
            analysis.requirements_packages,
            analysis.pyproject_dependencies,
        )

        return analysis

    def _parse_requirements_txt(self, requirements_path: Path) -> list[Package]:
        """Parse requirements.txt file and extract packages."""
        packages: list[Package] = []

        try:
            with requirements_path.open(encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith("#") or stripped_line.startswith("-"):
                    continue

                # Parse package specification
                package = self._parse_package_spec(stripped_line)
                if package:
                    packages.append(package)

        except (OSError, UnicodeDecodeError) as e:
            raise ProjectAnalysisError(f"Error reading requirements.txt: {e}") from e

        return packages

    def _parse_pyproject_dependencies(self, pyproject_path: Path) -> tuple[list[Package], list[str]]:
        """Parse pyproject.toml dependencies and return packages and extras."""
        packages: list[Package] = []
        extras: list[str] = []

        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            # Parse project dependencies
            if "project" in data and "dependencies" in data["project"]:
                for dep_spec in data["project"]["dependencies"]:
                    package = self._parse_package_spec(dep_spec)
                    if package:
                        packages.append(package)

            # Parse optional dependencies (extras)
            if "project" in data and "optional-dependencies" in data["project"]:
                optional_deps = data["project"]["optional-dependencies"]
                for extra_name, deps in optional_deps.items():
                    extras.append(extra_name)
                    for dep_spec in deps:
                        package = self._parse_package_spec(dep_spec)
                        if package:
                            package.extras = [extra_name]
                            packages.append(package)

        except (tomllib.TOMLDecodeError, OSError) as e:
            raise ProjectAnalysisError(f"Error reading pyproject.toml: {e}") from e

        return packages, extras

    def _parse_package_spec(self, spec: str) -> Package | None:
        """Parse a package specification string into a Package object."""
        # Remove inline comments
        spec = spec.split("#")[0].strip()
        if not spec:
            return None

        # Basic regex for package specification
        # Handles: package, package==1.0, package>=1.0, package[extra], etc.
        pattern = r"^([a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]|[a-zA-Z0-9])(\[[^\]]+\])?(.*?)(?:;(.*))?$"
        match = re.match(pattern, spec)

        if not match:
            return None

        name = match.group(1)
        extras_str = match.group(2)
        version_spec = match.group(3).strip() if match.group(3) else None
        markers = match.group(4).strip() if match.group(4) else None

        # Parse extras
        extras: list[str] = []
        if extras_str:
            extras_content = extras_str.strip("[]")
            extras = [e.strip() for e in extras_content.split(",") if e.strip()]

        # Extract version from version specification
        version = None
        if version_spec:
            # Simple version extraction (==, >=, <=, >, <, ~=)
            version_match = re.search(r"[=><~!]+([0-9][0-9a-zA-Z._-]*)", version_spec)
            if version_match:
                version = version_match.group(1)

        return Package(name=name, version=version, extras=extras, markers=markers)

    def _find_dependency_conflicts(
        self,
        requirements_packages: list[Package],
        pyproject_packages: list[Package],
    ) -> list[str]:
        """Find conflicts between requirements.txt and pyproject.toml dependencies."""
        conflicts: list[str] = []

        # Create a mapping of package names to versions
        req_packages = {pkg.name.lower(): pkg.version for pkg in requirements_packages}
        pyproject_packages_map = {pkg.name.lower(): pkg.version for pkg in pyproject_packages}

        # Check for version conflicts
        for name, req_version in req_packages.items():
            if name in pyproject_packages_map:
                pyproject_version = pyproject_packages_map[name]
                if req_version and pyproject_version and req_version != pyproject_version:
                    conflicts.append(
                        f"{name}: requirements.txt has {req_version}, pyproject.toml has {pyproject_version}",
                    )

        return conflicts

    def _detect_configured_tools(self, _project_path: Path, config_files: ConfigFiles) -> dict[str, ToolConfig]:
        """Detect configured development tools."""
        tools: dict[str, ToolConfig] = {}

        # Check pyproject.toml for tool configurations
        if "pyproject.toml" in config_files:
            pyproject_tools = self._parse_pyproject_tools(config_files["pyproject.toml"])
            tools.update(pyproject_tools)

        # Check for standalone tool configuration files
        standalone_configs = {
            ".flake8": "flake8",
            ".pylintrc": "pylint",
            "mypy.ini": "mypy",
            "bandit.yaml": "bandit",
            "bandit.yml": "bandit",
            "tox.ini": "tox",
            "pytest.ini": "pytest",
        }

        for filename, tool_name in standalone_configs.items():
            if filename in config_files:
                tools[tool_name] = ToolConfig(
                    name=tool_name,
                    config={"config_file": str(config_files[filename])},
                    enabled=True,
                )

        return tools

    def _parse_pyproject_tools(self, pyproject_path: Path) -> dict[str, ToolConfig]:
        """Parse tool configurations from pyproject.toml."""
        tools: dict[str, ToolConfig] = {}

        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            if "tool" not in data:
                return tools

            # Common tools that might be configured in pyproject.toml
            tool_names = [
                "ruff",
                "mypy",
                "black",
                "isort",
                "flake8",
                "pylint",
                "bandit",
                "safety",
                "pytest",
                "coverage",
                "tox",
            ]

            for tool_name in tool_names:
                if tool_name in data["tool"]:
                    tools[tool_name] = ToolConfig(name=tool_name, config=data["tool"][tool_name], enabled=True)

        except (tomllib.TOMLDecodeError, OSError):
            # If we can't parse the file, just return empty dict
            pass

        return tools

    def _check_security_tools(self, _project_path: Path, config_files: ConfigFiles) -> dict[SecurityTool, bool]:
        """Check which security tools are configured."""
        security_tools = dict.fromkeys(SecurityTool, False)

        if self._bandit_config_present(config_files):
            security_tools[SecurityTool.BANDIT] = True

        if self._bandit_in_pyproject(config_files.get("pyproject.toml")):
            security_tools[SecurityTool.BANDIT] = True

        self._mark_precommit_security_tools(security_tools, config_files)

        return security_tools

    @staticmethod
    def _bandit_config_present(config_files: dict[str, Path]) -> bool:
        bandit_configs = ["bandit.yaml", "bandit.yml"]
        return any(name in config_files for name in bandit_configs)

    @staticmethod
    def _bandit_in_pyproject(pyproject_path: Path | None) -> bool:
        if pyproject_path is None:
            return False

        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError):
            return False

        tool_config = data.get("tool", {})
        return isinstance(tool_config, dict) and "bandit" in tool_config

    def _mark_precommit_security_tools(
        self,
        security_tools: dict[SecurityTool, bool],
        config_files: ConfigFiles,
    ) -> None:
        precommit_files = [".pre-commit-config.yaml", ".pre-commit-config.yml"]
        for filename in precommit_files:
            path = config_files.get(filename)
            if not path:
                continue

            if self._check_gitleaks_in_precommit(path):
                security_tools[SecurityTool.GITLEAKS] = True

            tools = self._check_tools_in_precommit(path)
            if "bandit" in tools:
                security_tools[SecurityTool.BANDIT] = True
            if "safety" in tools:
                security_tools[SecurityTool.SAFETY] = True
            if "gitleaks" in tools:
                security_tools[SecurityTool.GITLEAKS] = True

    def _check_quality_tools(self, _project_path: Path, config_files: ConfigFiles) -> dict[QualityTool, bool]:
        """Check which quality tools are configured."""
        quality_tools = dict.fromkeys(QualityTool, False)
        self._mark_quality_tools_from_files(quality_tools, config_files)
        self._mark_quality_tools_from_pyproject(quality_tools, config_files.get("pyproject.toml"))
        self._mark_quality_tools_from_precommit(quality_tools, config_files)
        return quality_tools

    @staticmethod
    def _mark_quality_tools_from_files(
        quality_tools: dict[QualityTool, bool],
        config_files: ConfigFiles,
    ) -> None:
        tool_file_mapping = {
            ".flake8": QualityTool.FLAKE8,
            ".pylintrc": QualityTool.PYLINT,
            "mypy.ini": QualityTool.MYPY,
        }
        for filename, tool in tool_file_mapping.items():
            if filename in config_files:
                quality_tools[tool] = True

    def _mark_quality_tools_from_pyproject(
        self,
        quality_tools: dict[QualityTool, bool],
        pyproject_path: Path | None,
    ) -> None:
        if pyproject_path is None:
            return

        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
        except (tomllib.TOMLDecodeError, OSError):
            return

        tool_config_section = data.get("tool")
        if not isinstance(tool_config_section, dict):
            return
        tool_config: dict[str, object] = cast(dict[str, object], tool_config_section)

        tool_mapping = {
            "ruff": QualityTool.RUFF,
            "mypy": QualityTool.MYPY,
            "black": QualityTool.BLACK,
            "isort": QualityTool.ISORT,
            "flake8": QualityTool.FLAKE8,
            "pylint": QualityTool.PYLINT,
        }

        for tool_name, tool_enum in tool_mapping.items():
            if tool_name in tool_config:
                quality_tools[tool_enum] = True

        if "ruff" not in tool_config:
            return

        ruff_section = tool_config.get("ruff")
        if not isinstance(ruff_section, dict):
            return
        ruff_config: dict[str, object] = cast(dict[str, object], ruff_section)

        lint_config = ruff_config.get("lint")
        lint_select_source: object | None = None
        if isinstance(lint_config, dict):
            lint_section: dict[str, object] = cast(dict[str, object], lint_config)
            lint_select_source = lint_section.get("select")

        lint_select = self._ensure_str_list(lint_select_source)
        select_rules = self._ensure_str_list(ruff_config.get("select"))
        all_rules = select_rules + lint_select
        if any(rule.startswith("I") for rule in all_rules):
            quality_tools[QualityTool.ISORT] = True

    def _mark_quality_tools_from_precommit(
        self,
        quality_tools: dict[QualityTool, bool],
        config_files: ConfigFiles,
    ) -> None:
        precommit_files = [".pre-commit-config.yaml", ".pre-commit-config.yml"]
        tool_mapping = {
            "ruff": QualityTool.RUFF,
            "mypy": QualityTool.MYPY,
            "black": QualityTool.BLACK,
            "isort": QualityTool.ISORT,
            "flake8": QualityTool.FLAKE8,
            "pylint": QualityTool.PYLINT,
        }
        for filename in precommit_files:
            path = config_files.get(filename)
            if not path:
                continue
            tools = self._check_tools_in_precommit(path)
            for tool_name, tool_enum in tool_mapping.items():
                if tool_name in tools:
                    quality_tools[tool_enum] = True

    def _check_gitleaks_in_precommit(self, precommit_path: Path) -> bool:
        """Check if gitleaks is configured in pre-commit config."""
        yaml_module = yaml
        try:
            if yaml_module is None:
                return self._gitleaks_text_search(precommit_path)

            with precommit_path.open(encoding="utf-8") as f:
                parsed = yaml_module.safe_load(f)

            return self._gitleaks_from_yaml_data(parsed)
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug(f"Failed to read pre-commit config: {exc}")
            return False
        except Exception as exc:
            logger.debug(f"Unexpected error checking gitleaks in pre-commit: {exc}")
            return False

    def _gitleaks_from_yaml_data(self, data: object) -> bool:
        if not isinstance(data, dict):
            return False
        parsed_dict: dict[str, object] = cast(dict[str, object], data)

        repos_raw = parsed_dict.get("repos")
        if not isinstance(repos_raw, list):
            return False
        repos_data: list[object] = cast(list[object], repos_raw)

        for repo in repos_data:
            if not isinstance(repo, dict):
                continue
            repo_dict: dict[str, object] = cast(dict[str, object], repo)
            repo_url = repo_dict.get("repo")
            if isinstance(repo_url, str) and "gitleaks" in repo_url.lower():
                return True

        return False

    def _gitleaks_text_search(self, precommit_path: Path) -> bool:
        content = precommit_path.read_text(encoding="utf-8").lower()
        return "gitleaks" in content

    def _check_tools_in_precommit(self, precommit_path: Path) -> list[str]:
        """Check which tools are configured in pre-commit config."""
        try:
            if yaml is None:
                return self._parse_precommit_text(precommit_path)
            return self._parse_precommit_yaml(precommit_path)
        except (OSError, UnicodeDecodeError) as exc:
            logger.debug(f"Failed to read pre-commit config for tools: {exc}")
            return []
        except Exception as exc:
            logger.debug(f"Unexpected error checking tools in pre-commit: {exc}")
            return []

    def _parse_precommit_yaml(self, precommit_path: Path) -> list[str]:
        yaml_module = yaml
        if yaml_module is None:
            return []
        with precommit_path.open(encoding="utf-8") as f:
            parsed = yaml_module.safe_load(f)

        if not isinstance(parsed, dict):
            return []
        parsed_dict: dict[str, object] = cast(dict[str, object], parsed)

        repos_raw = parsed_dict.get("repos")
        if not isinstance(repos_raw, list):
            return []
        repos_data: list[object] = cast(list[object], repos_raw)

        tools: set[str] = set()
        for repo in repos_data:
            if not isinstance(repo, dict):
                continue
            repo_dict: dict[str, object] = cast(dict[str, object], repo)

            repo_url = repo_dict.get("repo")
            if isinstance(repo_url, str):
                self._collect_tools_from_string(tools, repo_url.lower())

            hooks_raw = repo_dict.get("hooks")
            if not isinstance(hooks_raw, list):
                continue
            hooks: list[object] = cast(list[object], hooks_raw)
            for hook in hooks:
                if not isinstance(hook, dict):
                    continue
                hook_dict: dict[str, object] = cast(dict[str, object], hook)
                hook_id = hook_dict.get("id")
                if isinstance(hook_id, str):
                    self._collect_tools_from_string(tools, hook_id.lower())

        return list(tools)

    def _parse_precommit_text(self, precommit_path: Path) -> list[str]:
        with precommit_path.open(encoding="utf-8") as f:
            content = f.read().lower()

        return [tool_name for tool_name in PRECOMMIT_TOOL_PATTERNS if tool_name in content]

    def _collect_tools_from_string(self, tools: set[str], target: str) -> None:
        for tool_name, patterns in PRECOMMIT_TOOL_PATTERNS.items():
            if any(pattern in target for pattern in patterns):
                tools.add(tool_name)

    @staticmethod
    def _ensure_str_list(value: object) -> list[str]:
        if isinstance(value, list):
            typed_items: list[object] = cast(list[object], value)
            return [item for item in typed_items if isinstance(item, str)]
        return []

    def _detect_ci_workflows(self, project_path: Path) -> list[Workflow]:
        """Detect CI/CD workflows in the project."""
        workflows: list[Workflow] = []

        # Check for GitHub Actions workflows
        github_workflows_dir = project_path / ".github" / "workflows"
        if github_workflows_dir.exists() and github_workflows_dir.is_dir():
            for workflow_file in github_workflows_dir.glob("*.yml"):
                workflow = self._parse_github_workflow(workflow_file)
                if workflow:
                    workflows.append(workflow)

            for workflow_file in github_workflows_dir.glob("*.yaml"):
                workflow = self._parse_github_workflow(workflow_file)
                if workflow:
                    workflows.append(workflow)

        return workflows

    def _parse_github_workflow(self, workflow_path: Path) -> Workflow | None:
        """Parse a GitHub Actions workflow file."""
        try:
            if yaml is None:
                return self._parse_workflow_text(workflow_path)
            workflow = self._parse_workflow_yaml(workflow_path)
            return workflow or self._parse_workflow_text(workflow_path)
        except (OSError, UnicodeDecodeError):
            return None
        except Exception:
            return None

    def _parse_workflow_yaml(self, workflow_path: Path) -> Workflow | None:
        yaml_module = yaml
        if yaml_module is None:
            return None

        with workflow_path.open(encoding="utf-8") as f:
            raw_content = f.read()
        parsed = yaml_module.safe_load(raw_content)
        if not isinstance(parsed, dict):
            return None
        data: dict[str, Any] = cast(dict[str, Any], parsed)

        name = data.get("name", workflow_path.stem)
        name_str = str(name) if name is not None else workflow_path.stem
        triggers = self._extract_yaml_triggers(data)
        jobs = self._extract_yaml_jobs(data)
        return self._build_workflow_result(workflow_path, name_str, triggers, jobs, raw_content)

    def _extract_yaml_triggers(self, data: dict[str, Any]) -> list[str]:
        triggers: list[str] = []
        on_data: Any = data.get("on")
        if isinstance(on_data, str):
            triggers.append(on_data)
        elif isinstance(on_data, list):
            list_entries: list[object] = cast(list[object], on_data)
            triggers.extend(str(item) for item in list_entries)
        elif isinstance(on_data, dict):
            on_dict: dict[str, object] = cast(dict[str, object], on_data)
            triggers.extend(str(key) for key in on_dict)
        return triggers

    def _extract_yaml_jobs(self, data: dict[str, Any]) -> list[str]:
        jobs_data: Any = data.get("jobs")
        if isinstance(jobs_data, dict):
            jobs_dict: dict[str, object] = cast(dict[str, object], jobs_data)
            return list(jobs_dict.keys())
        return []

    def _parse_workflow_text(self, workflow_path: Path) -> Workflow | None:
        content = workflow_path.read_text(encoding="utf-8")
        name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
        name = name_match.group(1).strip().strip("\"'") if name_match else workflow_path.stem
        triggers = self._extract_text_triggers(content)
        jobs = self._extract_text_jobs(content)
        return self._build_workflow_result(workflow_path, name, triggers, jobs, content)

    @staticmethod
    def _extract_text_triggers(content: str) -> list[str]:
        triggers: list[str] = []
        on_match = re.search(r"^on:\s*(.+)$", content, re.MULTILINE)
        if on_match:
            on_line = on_match.group(1).strip()
            if on_line and not on_line.startswith("[") and not on_line.startswith("{"):
                triggers.append(on_line)
        return triggers

    @staticmethod
    def _extract_text_jobs(content: str) -> list[str]:
        jobs_match = re.search(r"^jobs:\s*$", content, re.MULTILINE)
        if not jobs_match:
            return []
        jobs_section = content[jobs_match.end() :]
        return re.findall(r"^\s{2}([a-zA-Z_][a-zA-Z0-9_-]*):", jobs_section, re.MULTILINE)

    def _build_workflow_result(
        self,
        workflow_path: Path,
        name: str,
        triggers: list[str],
        jobs: list[str],
        raw_content: str,
    ) -> Workflow:
        workflow_content = raw_content.lower()
        has_security_checks = any(tool in workflow_content for tool in ["bandit", "safety", "gitleaks", "semgrep"])
        has_quality_checks = any(
            tool in workflow_content for tool in ["ruff", "mypy", "black", "flake8", "pylint", "pytest"]
        )

        return Workflow(
            name=name,
            file_path=workflow_path,
            triggers=triggers,
            jobs=jobs,
            has_security_checks=has_security_checks,
            has_quality_checks=has_quality_checks,
        )

    def _detect_python_version(self, _project_path: Path, config_files: dict[str, Path]) -> str | None:
        """Detect the Python version requirement for the project."""
        # Check pyproject.toml first
        pyproject_path = config_files.get("pyproject.toml")
        if pyproject_path:
            try:
                with pyproject_path.open("rb") as f:
                    loaded = cast(object, tomllib.load(f))

                if isinstance(loaded, dict):
                    pyproject_data: dict[str, object] = cast(dict[str, object], loaded)
                    project_section = pyproject_data.get("project")
                    if isinstance(project_section, dict):
                        project_data: dict[str, object] = cast(dict[str, object], project_section)
                        requires_python = project_data.get("requires-python")
                        if isinstance(requires_python, str):
                            return requires_python

            except (tomllib.TOMLDecodeError, OSError):
                pass

        # Check setup.py (simplified - would need AST parsing for full support)
        if "setup.py" in config_files:
            try:
                content = config_files["setup.py"].read_text(encoding="utf-8")
                # Look for python_requires in setup.py
                match = re.search(r'python_requires\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    return match.group(1)
            except (OSError, UnicodeDecodeError):
                pass

        return None

    def _analyze_languages(self, project_path: Path) -> dict[str, LanguageAnalysisResult]:
        """Run language analyzers and return structured results."""
        try:
            registry = get_global_registry()
        except Exception as exc:  # pragma: no cover - registry import issues
            logger.warning("Language registry unavailable", error=str(exc))
            return {}

        try:
            analysis = registry.analyze_project(project_path)
            logger.debug("Language analysis completed", languages=list(analysis.keys()))
            return analysis
        except Exception as exc:
            logger.warning("Language analysis failed", error=str(exc))
            return {}

    def analyze_github_repository(self, project_path: Path) -> "GitHubAnalysisResult":
        """Analyze GitHub repository settings and configuration.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary containing GitHub repository analysis results
        """
        if not validate_project_path(project_path):
            raise ProjectAnalysisError(f"Invalid project path: {project_path}")

        # Try to detect GitHub repository from git remote
        repo_info = self._detect_github_repository(project_path)
        if not repo_info:
            return {"is_github_repo": False, "error": "Not a GitHub repository or no remote origin found"}

        owner, repo = repo_info
        github_client = GitHubClient()

        if not github_client.is_authenticated():
            return {
                "is_github_repo": True,
                "owner": owner,
                "repo": repo,
                "authenticated": False,
                "error": "GitHub token not available or invalid",
            }

        try:
            # Get security settings
            security_settings = github_client.check_security_settings(owner, repo)

            # Get push protection status
            push_protection = github_client.check_push_protection(owner, repo)

            # Get Dependabot configuration
            dependabot_config = github_client.get_dependabot_config(owner, repo)

            # Get workflows
            workflows = github_client.list_workflows(owner, repo)

            return {
                "is_github_repo": True,
                "owner": owner,
                "repo": repo,
                "authenticated": True,
                "security_settings": security_settings,
                "push_protection": push_protection,
                "dependabot": dependabot_config,
                "workflows": workflows,
                "analysis_successful": True,
            }

        except GitHubAPIError as e:
            return {
                "is_github_repo": True,
                "owner": owner,
                "repo": repo,
                "authenticated": True,
                "error": str(e),
                "analysis_successful": False,
            }

    def check_github_workflows(self, project_path: Path) -> dict[str, Any]:
        """Check GitHub Actions workflows for security and quality checks.

        Args:
            project_path: Path to the project directory

        Returns:
            Dictionary containing workflow analysis results
        """
        if not validate_project_path(project_path):
            raise ProjectAnalysisError(f"Invalid project path: {project_path}")

        # First check local workflows
        local_workflows = self._detect_ci_workflows(project_path)

        # Try to get remote workflows via GitHub API
        repo_info = self._detect_github_repository(project_path)
        remote_workflows = []

        if repo_info:
            owner, repo = repo_info
            github_client = GitHubClient()

            if github_client.is_authenticated():
                # Continue with local analysis only if API fails
                with contextlib.suppress(GitHubAPIError):
                    remote_workflows = github_client.list_workflows(owner, repo)

        # Analyze workflow coverage
        has_security_workflow = any(wf.has_security_checks for wf in local_workflows) or any(
            self._workflow_has_security_checks(wf) for wf in remote_workflows
        )

        has_quality_workflow = any(wf.has_quality_checks for wf in local_workflows) or any(
            self._workflow_has_quality_checks(wf) for wf in remote_workflows
        )

        return {
            "local_workflows": [
                {
                    "name": wf.name,
                    "file_path": str(wf.file_path),
                    "triggers": wf.triggers,
                    "jobs": wf.jobs,
                    "has_security_checks": wf.has_security_checks,
                    "has_quality_checks": wf.has_quality_checks,
                }
                for wf in local_workflows
            ],
            "remote_workflows": [
                {
                    "name": wf.get("name", ""),
                    "path": wf.get("path", ""),
                    "state": wf.get("state", ""),
                    "created_at": wf.get("created_at", ""),
                    "updated_at": wf.get("updated_at", ""),
                }
                for wf in remote_workflows
            ],
            "has_security_workflow": has_security_workflow,
            "has_quality_workflow": has_quality_workflow,
            "workflow_recommendations": self._get_workflow_recommendations(has_security_workflow, has_quality_workflow),
        }

    def _detect_github_repository(self, project_path: Path) -> tuple[str, str] | None:
        """Detect GitHub repository owner and name from git remote.

        Args:
            project_path: Path to the project directory

        Returns:
            Tuple of (owner, repo) if GitHub repository detected, None otherwise
        """
        git_dir = project_path / ".git"
        if not git_dir.exists():
            return None

        # Try to read git config
        git_config_path = git_dir / "config"
        if not git_config_path.exists():
            return None

        try:
            with git_config_path.open(encoding="utf-8") as f:
                config_content = f.read()

            # Look for GitHub remote origin URL
            # Matches both HTTPS and SSH formats
            patterns = [
                r"url = https://github\.com/([^/]+)/([^/\s]+?)(?:\.git)?(?:\s|$)",
                r"url = git@github\.com:([^/]+)/([^/\s]+?)(?:\.git)?(?:\s|$)",
            ]

            for pattern in patterns:
                match = re.search(pattern, config_content)
                if match:
                    owner = match.group(1)
                    repo = match.group(2)
                    return (owner, repo)

        except (OSError, UnicodeDecodeError):
            pass

        return None

    def _workflow_has_security_checks(self, workflow: GitHubWorkflowSummary) -> bool:
        """Check if a remote workflow has security checks.

        Args:
            workflow: Workflow summary from GitHub API

        Returns:
            True if workflow likely contains security checks
        """
        workflow_name = workflow.get("name", "").lower()
        workflow_path = workflow.get("path", "").lower()

        security_keywords = [
            "security",
            "bandit",
            "safety",
            "gitleaks",
            "semgrep",
            "snyk",
            "codeql",
            "dependabot",
            "vulnerability",
        ]

        return any(keyword in workflow_name or keyword in workflow_path for keyword in security_keywords)

    def _workflow_has_quality_checks(self, workflow: GitHubWorkflowSummary) -> bool:
        """Check if a remote workflow has quality checks.

        Args:
            workflow: Workflow summary from GitHub API

        Returns:
            True if workflow likely contains quality checks
        """
        workflow_name = workflow.get("name", "").lower()
        workflow_path = workflow.get("path", "").lower()

        quality_keywords = [
            "test",
            "lint",
            "quality",
            "ruff",
            "mypy",
            "black",
            "flake8",
            "pylint",
            "pytest",
            "coverage",
            "ci",
            "check",
        ]

        return any(keyword in workflow_name or keyword in workflow_path for keyword in quality_keywords)

    def _get_workflow_recommendations(self, has_security: bool, has_quality: bool) -> list[str]:
        """Get workflow recommendations based on current setup.

        Args:
            has_security: Whether security workflows are present
            has_quality: Whether quality workflows are present

        Returns:
            List of recommendation strings
        """
        recommendations: list[str] = []

        if not has_security:
            recommendations.append("Add security workflow with Bandit, Safety, and gitleaks checks")

        if not has_quality:
            recommendations.append("Add quality workflow with linting, type checking, and testing")

        if not has_security and not has_quality:
            recommendations.append("Consider using GitHub's security features like Dependabot and CodeQL")

        return recommendations
