"""Project analyzer for detecting configuration files and project state."""

import contextlib
import re
import tomllib
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

from ..models.exceptions import GitHubAPIError, ProjectAnalysisError
from ..models.interfaces import (
    DependencyAnalysis,
    DependencyManager,
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

logger = get_logger(__name__)


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

        return project_state

    def detect_configuration_files(self, project_path: Path) -> dict[str, Path]:
        """Detect existing configuration files in the project."""
        if not validate_project_path(project_path):
            raise ProjectAnalysisError(f"Invalid project path: {project_path}")

        config_files = {}

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
        # Check for Poetry
        if (project_path / "poetry.lock").exists():
            return DependencyManager.POETRY

        # Check for PDM
        if (project_path / "pdm.lock").exists():
            return DependencyManager.PDM

        # Check for Pipenv
        if (project_path / "Pipfile").exists():
            return DependencyManager.PIPENV

        # Check for Conda
        conda_files = ["environment.yml", "environment.yaml", "conda.yml", "conda.yaml"]
        if any((project_path / f).exists() for f in conda_files):
            return DependencyManager.CONDA

        # Check for setuptools-scm in pyproject.toml
        pyproject_path = project_path / "pyproject.toml"
        if pyproject_path.exists():
            try:
                with pyproject_path.open("rb") as f:
                    data = tomllib.load(f)
                    if "tool" in data and "setuptools_scm" in data["tool"]:
                        return DependencyManager.SETUPTOOLS_SCM
            except (tomllib.TOMLDecodeError, OSError):
                pass

        # Default to pip if requirements.txt exists
        if (project_path / "requirements.txt").exists():
            return DependencyManager.PIP

        return None

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
        packages = []

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
        packages = []
        extras = []

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
        extras = []
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
        conflicts = []

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

    def _detect_configured_tools(self, _project_path: Path, config_files: dict[str, Path]) -> dict[str, ToolConfig]:
        """Detect configured development tools."""
        tools = {}

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

    def _check_security_tools(self, _project_path: Path, config_files: dict[str, Path]) -> dict[SecurityTool, bool]:
        """Check which security tools are configured."""
        security_tools = dict.fromkeys(SecurityTool, False)

        # Check for Bandit configuration
        bandit_configs = ["bandit.yaml", "bandit.yml"]
        if any(config in config_files for config in bandit_configs):
            security_tools[SecurityTool.BANDIT] = True

        # Check for Bandit in pyproject.toml
        if "pyproject.toml" in config_files:
            try:
                with open(config_files["pyproject.toml"], "rb") as f:
                    data = tomllib.load(f)
                    if "tool" in data and "bandit" in data["tool"]:
                        security_tools[SecurityTool.BANDIT] = True
            except (tomllib.TOMLDecodeError, OSError):
                pass

        # Check for gitleaks in pre-commit config
        precommit_configs = [".pre-commit-config.yaml", ".pre-commit-config.yml"]
        for config_name in precommit_configs:
            if config_name in config_files and self._check_gitleaks_in_precommit(config_files[config_name]):
                security_tools[SecurityTool.GITLEAKS] = True

        # Check for security tools in pre-commit config
        for config_name in precommit_configs:
            if config_name in config_files:
                precommit_tools = self._check_tools_in_precommit(config_files[config_name])
                if "bandit" in precommit_tools:
                    security_tools[SecurityTool.BANDIT] = True
                if "safety" in precommit_tools:
                    security_tools[SecurityTool.SAFETY] = True
                if "gitleaks" in precommit_tools:
                    security_tools[SecurityTool.GITLEAKS] = True

        return security_tools

    def _check_quality_tools(self, _project_path: Path, config_files: dict[str, Path]) -> dict[QualityTool, bool]:
        """Check which quality tools are configured."""
        quality_tools = dict.fromkeys(QualityTool, False)

        # Check standalone config files
        tool_file_mapping = {
            ".flake8": QualityTool.FLAKE8,
            ".pylintrc": QualityTool.PYLINT,
            "mypy.ini": QualityTool.MYPY,
        }

        for filename, tool in tool_file_mapping.items():
            if filename in config_files:
                quality_tools[tool] = True

        # Check pyproject.toml for tool configurations
        if "pyproject.toml" in config_files:
            try:
                with open(config_files["pyproject.toml"], "rb") as f:
                    data = tomllib.load(f)
                    if "tool" in data:
                        tool_mapping = {
                            "ruff": QualityTool.RUFF,
                            "mypy": QualityTool.MYPY,
                            "black": QualityTool.BLACK,
                            "isort": QualityTool.ISORT,
                            "flake8": QualityTool.FLAKE8,
                            "pylint": QualityTool.PYLINT,
                        }

                        for tool_name, tool_enum in tool_mapping.items():
                            if tool_name in data["tool"]:
                                quality_tools[tool_enum] = True

                        # Check if ruff has import sorting enabled (modern replacement for isort)
                        if "ruff" in data["tool"]:
                            ruff_config = data["tool"]["ruff"]
                            # Check if ruff is configured for import sorting
                            if isinstance(ruff_config, dict):
                                # Check top-level select rules
                                select_rules = ruff_config.get("select", [])
                                # Check lint.select rules (newer ruff format)
                                lint_config = ruff_config.get("lint", {})
                                lint_select = lint_config.get("select", []) if isinstance(lint_config, dict) else []

                                all_rules = select_rules + lint_select

                                # Check for import sorting rules (I001, etc.)
                                has_import_rules = any(
                                    rule.startswith("I") for rule in all_rules if isinstance(rule, str)
                                )

                                if has_import_rules:
                                    quality_tools[QualityTool.ISORT] = True
            except (tomllib.TOMLDecodeError, OSError):
                pass

        # Check for quality tools in pre-commit config
        precommit_configs = [".pre-commit-config.yaml", ".pre-commit-config.yml"]
        for config_name in precommit_configs:
            if config_name in config_files:
                precommit_tools = self._check_tools_in_precommit(config_files[config_name])
                # Map pre-commit tools to quality tools
                tool_mapping = {
                    "ruff": QualityTool.RUFF,
                    "mypy": QualityTool.MYPY,
                    "black": QualityTool.BLACK,
                    "isort": QualityTool.ISORT,
                    "flake8": QualityTool.FLAKE8,
                    "pylint": QualityTool.PYLINT,
                }

                for tool_name, tool_enum in tool_mapping.items():
                    if tool_name in precommit_tools:
                        quality_tools[tool_enum] = True

        return quality_tools

    def _check_gitleaks_in_precommit(self, precommit_path: Path) -> bool:
        """Check if gitleaks is configured in pre-commit config."""
        try:
            # Try to import yaml, if not available, fall back to text search
            if yaml is not None:
                # Use YAML parser for accurate parsing
                with precommit_path.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict) or "repos" not in data:
                    return False

                for repo in data["repos"]:
                    if isinstance(repo, dict) and "repo" in repo:
                        repo_url = repo["repo"]
                        if "gitleaks" in repo_url.lower():
                            return True
            else:
                # Fallback to text search
                with precommit_path.open(encoding="utf-8") as f:
                    content = f.read().lower()
                    return "gitleaks" in content

        except (OSError, UnicodeDecodeError) as e:
            # If file can't be read, return False
            logger.debug(f"Failed to read pre-commit config: {e}")
            return False
        except Exception as e:
            # For any other errors, return False
            logger.debug(f"Unexpected error checking gitleaks in pre-commit: {e}")
            return False

        return False

    def _check_tools_in_precommit(self, precommit_path: Path) -> list[str]:
        """Check which tools are configured in pre-commit config."""
        tools = []

        try:
            # Try to import yaml, if not available, fall back to text search
            if yaml is not None:
                # Use YAML parser for accurate parsing
                with precommit_path.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if isinstance(data, dict) and "repos" in data:
                    for repo in data["repos"]:
                        if isinstance(repo, dict):
                            # Check repo URL for tool names
                            repo_url = repo.get("repo", "").lower()

                            # Common tool patterns in repo URLs
                            tool_patterns = {
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

                            for tool_name, patterns in tool_patterns.items():
                                if any(pattern in repo_url for pattern in patterns):
                                    tools.append(tool_name)

                            # Check hooks for tool names
                            hooks = repo.get("hooks", [])
                            for hook in hooks:
                                if isinstance(hook, dict):
                                    hook_id = hook.get("id", "").lower()
                                    for tool_name, patterns in tool_patterns.items():
                                        if any(pattern in hook_id for pattern in patterns):
                                            tools.append(tool_name)
            else:
                # Fallback to text search
                with precommit_path.open(encoding="utf-8") as f:
                    content = f.read().lower()

                    # Search for common tool names in the content
                    tool_names = ["ruff", "mypy", "black", "isort", "flake8", "pylint", "bandit", "safety", "gitleaks"]
                    tools.extend(tool_name for tool_name in tool_names if tool_name in content)

        except (OSError, UnicodeDecodeError) as e:
            # If file can't be read, return empty list
            logger.debug(f"Failed to read pre-commit config for tools: {e}")
            return []
        except Exception as e:
            # For any other errors, return empty list
            logger.debug(f"Unexpected error checking tools in pre-commit: {e}")
            return []

        return list(set(tools))  # Remove duplicates

    def _detect_ci_workflows(self, project_path: Path) -> list[Workflow]:
        """Detect CI/CD workflows in the project."""
        workflows = []

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
            # Try to import yaml, if not available, fall back to basic parsing
            if yaml is not None:
                # Use YAML parser for full parsing
                with workflow_path.open(encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict):
                    return None

                name = data.get("name", workflow_path.stem)

                # Extract triggers
                triggers = []
                if "on" in data:
                    on_data = data["on"]
                    if isinstance(on_data, str):
                        triggers.append(on_data)
                    elif isinstance(on_data, list):
                        triggers.extend(on_data)
                    elif isinstance(on_data, dict):
                        triggers.extend(on_data.keys())

                # Extract job names
                jobs = []
                if "jobs" in data and isinstance(data["jobs"], dict):
                    jobs = list(data["jobs"].keys())
            else:
                # Fallback to basic text parsing
                with workflow_path.open(encoding="utf-8") as f:
                    content = f.read()

                # Extract name using regex
                name_match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
                name = name_match.group(1).strip().strip("\"'") if name_match else workflow_path.stem

                # Extract triggers (basic)
                triggers = []
                on_match = re.search(r"^on:\s*(.+)$", content, re.MULTILINE)
                if on_match:
                    on_line = on_match.group(1).strip()
                    if on_line and not on_line.startswith("[") and not on_line.startswith("{"):
                        triggers.append(on_line)

                # Extract job names (basic)
                jobs_match = re.search(r"^jobs:\s*$", content, re.MULTILINE)
                jobs = []
                if jobs_match:
                    # Find job names after jobs: line
                    jobs_section = content[jobs_match.end() :]
                    job_matches = re.findall(r"^\s{2}([a-zA-Z_][a-zA-Z0-9_-]*):", jobs_section, re.MULTILINE)
                    jobs = job_matches

            # Check for security and quality checks (works for both methods)
            workflow_content = workflow_path.read_text(encoding="utf-8").lower()
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

        except (OSError, UnicodeDecodeError):
            # If file can't be read, return None
            return None
        except Exception:
            # For any other parsing errors, return None
            return None

    def _detect_python_version(self, _project_path: Path, config_files: dict[str, Path]) -> str | None:
        """Detect the Python version requirement for the project."""
        # Check pyproject.toml first
        if "pyproject.toml" in config_files:
            try:
                with open(config_files["pyproject.toml"], "rb") as f:
                    data = tomllib.load(f)

                if "project" in data and "requires-python" in data["project"]:
                    project_data = data["project"]
                    if isinstance(project_data, dict):
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

    def analyze_github_repository(self, project_path: Path) -> dict[str, Any]:
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

    def _workflow_has_security_checks(self, workflow: dict[str, Any]) -> bool:
        """Check if a remote workflow has security checks.

        Args:
            workflow: Workflow dictionary from GitHub API

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

    def _workflow_has_quality_checks(self, workflow: dict[str, Any]) -> bool:
        """Check if a remote workflow has quality checks.

        Args:
            workflow: Workflow dictionary from GitHub API

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
        recommendations = []

        if not has_security:
            recommendations.append("Add security workflow with Bandit, Safety, and gitleaks checks")

        if not has_quality:
            recommendations.append("Add quality workflow with linting, type checking, and testing")

        if not has_security and not has_quality:
            recommendations.append("Consider using GitHub's security features like Dependabot and CodeQL")

        return recommendations
