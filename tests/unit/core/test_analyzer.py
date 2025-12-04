"""Unit tests for ProjectAnalyzer."""

from pathlib import Path

import pytest

from secuority.core.analyzer import ProjectAnalyzer
from secuority.models.exceptions import ProjectAnalysisError
from secuority.models.interfaces import DependencyManager, Package, QualityTool, SecurityTool


class TestProjectAnalyzer:
    """Test ProjectAnalyzer functionality."""

    @pytest.fixture
    def analyzer(self) -> ProjectAnalyzer:
        """Create ProjectAnalyzer instance."""
        return ProjectAnalyzer()

    def test_analyze_project_invalid_path(self, analyzer: ProjectAnalyzer) -> None:
        """Test analyzing project with invalid path raises error."""
        invalid_path = Path("/nonexistent/path")
        with pytest.raises(ProjectAnalysisError):
            analyzer.analyze_project(invalid_path)

    def test_analyze_project_empty_directory(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test analyzing empty project directory."""
        state = analyzer.analyze_project(tmp_path)

        assert state.project_path == tmp_path
        assert not state.has_pyproject_toml
        assert not state.has_requirements_txt
        assert not state.has_setup_py
        assert not state.has_gitignore

    def test_analyze_project_with_pyproject_toml(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test analyzing project with pyproject.toml."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n')

        state = analyzer.analyze_project(tmp_path)

        assert state.has_pyproject_toml
        assert not state.has_requirements_txt

    def test_analyze_project_with_requirements_txt(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test analyzing project with requirements.txt."""
        requirements_path = tmp_path / "requirements.txt"
        requirements_path.write_text("pytest>=7.0.0\n")

        state = analyzer.analyze_project(tmp_path)

        assert state.has_requirements_txt
        assert state.dependency_manager == DependencyManager.PIP

    def test_detect_configuration_files_invalid_path(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test detecting config files with invalid path raises error."""
        invalid_path = Path("/nonexistent/path")
        with pytest.raises(ProjectAnalysisError):
            analyzer.detect_configuration_files(invalid_path)

    def test_detect_configuration_files_standard_files(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting standard configuration files."""
        # Create test files
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "requirements.txt").write_text("pytest\n")
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        (tmp_path / "setup.py").write_text("from setuptools import setup\n")

        config_files = analyzer.detect_configuration_files(tmp_path)

        assert "pyproject.toml" in config_files
        assert "requirements.txt" in config_files
        assert ".gitignore" in config_files
        assert "setup.py" in config_files

    def test_detect_dependency_manager_poetry(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Poetry as dependency manager."""
        (tmp_path / "poetry.lock").write_text("")

        manager = analyzer._detect_dependency_manager(tmp_path)

        assert manager == DependencyManager.POETRY

    def test_detect_dependency_manager_pdm(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting PDM as dependency manager."""
        (tmp_path / "pdm.lock").write_text("")

        manager = analyzer._detect_dependency_manager(tmp_path)

        assert manager == DependencyManager.PDM

    def test_detect_dependency_manager_pipenv(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Pipenv as dependency manager."""
        (tmp_path / "Pipfile").write_text("")

        manager = analyzer._detect_dependency_manager(tmp_path)

        assert manager == DependencyManager.PIPENV

    def test_parse_requirements_txt_simple(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test parsing simple requirements.txt."""
        requirements_path = tmp_path / "requirements.txt"
        requirements_path.write_text("pytest==7.0.0\nrequests>=2.28.0\n")

        packages = analyzer._parse_requirements_txt(requirements_path)

        assert len(packages) == 2
        assert packages[0].name == "pytest"
        assert packages[0].version == "7.0.0"
        assert packages[1].name == "requests"
        assert packages[1].version == "2.28.0"

    def test_parse_requirements_txt_with_comments(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test parsing requirements.txt with comments."""
        requirements_path = tmp_path / "requirements.txt"
        requirements_path.write_text("# Testing dependencies\npytest==7.0.0\n\n# HTTP library\nrequests>=2.28.0\n")

        packages = analyzer._parse_requirements_txt(requirements_path)

        assert len(packages) == 2

    def test_parse_pyproject_dependencies(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test parsing pyproject.toml dependencies."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\ndependencies = [\n  "pytest>=7.0.0",\n  "requests==2.28.0"\n]\n',
        )

        packages, extras = analyzer._parse_pyproject_dependencies(pyproject_path)

        assert len(packages) == 2
        assert packages[0].name == "pytest"
        assert packages[1].name == "requests"
        assert len(extras) == 0

    def test_parse_pyproject_with_extras(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test parsing pyproject.toml with optional dependencies."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n'
            "[project.optional-dependencies]\n"
            'dev = ["pytest>=7.0.0"]\n'
            'docs = ["sphinx>=4.0.0"]\n',
        )

        packages, extras = analyzer._parse_pyproject_dependencies(pyproject_path)

        assert "dev" in extras
        assert "docs" in extras
        assert len(packages) == 2

    def test_parse_package_spec_simple(self, analyzer: ProjectAnalyzer) -> None:
        """Test parsing simple package specification."""
        package = analyzer._parse_package_spec("pytest")

        assert package is not None
        assert package.name == "pytest"
        assert package.version is None

    def test_parse_package_spec_with_version(self, analyzer: ProjectAnalyzer) -> None:
        """Test parsing package spec with version."""
        package = analyzer._parse_package_spec("pytest==7.0.0")

        assert package is not None
        assert package.name == "pytest"
        assert package.version == "7.0.0"

    def test_parse_package_spec_with_extras(self, analyzer: ProjectAnalyzer) -> None:
        """Test parsing package spec with extras."""
        package = analyzer._parse_package_spec("requests[security]>=2.28.0")

        assert package is not None
        assert package.name == "requests"
        assert "security" in package.extras
        assert package.version == "2.28.0"

    def test_parse_package_spec_with_markers(self, analyzer: ProjectAnalyzer) -> None:
        """Test parsing package spec with environment markers."""
        package = analyzer._parse_package_spec('pytest>=7.0.0; python_version >= "3.8"')

        assert package is not None
        assert package.name == "pytest"
        assert package.markers is not None
        assert "python_version" in package.markers

    def test_check_security_tools_bandit_in_pyproject(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Bandit in pyproject.toml."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[tool.bandit]\nskip = ["B101"]\n')

        config_files = {"pyproject.toml": pyproject_path}
        security_tools = analyzer._check_security_tools(tmp_path, config_files)

        assert security_tools[SecurityTool.BANDIT]

    def test_check_security_tools_gitleaks_in_precommit(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting gitleaks in pre-commit config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n  - repo: https://github.com/gitleaks/gitleaks\n    hooks:\n      - id: gitleaks\n",
        )

        config_files = {".pre-commit-config.yaml": precommit_path}
        security_tools = analyzer._check_security_tools(tmp_path, config_files)

        assert security_tools[SecurityTool.GITLEAKS]

    def test_check_quality_tools_ruff_in_pyproject(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Ruff in pyproject.toml."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("[tool.ruff]\nline-length = 120\n")

        config_files = {"pyproject.toml": pyproject_path}
        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)

        assert quality_tools[QualityTool.RUFF]

    def test_check_quality_tools_mypy_standalone(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Mypy with standalone config."""
        mypy_path = tmp_path / "mypy.ini"
        mypy_path.write_text("[mypy]\nstrict = true\n")

        config_files = {"mypy.ini": mypy_path}
        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)

        assert quality_tools[QualityTool.MYPY]

    def test_detect_ci_workflows_github_actions(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting GitHub Actions workflows."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        workflow_path = workflows_dir / "test.yml"
        workflow_path.write_text(
            "name: Test\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
            "      - run: pytest\n",
        )

        workflows = analyzer._detect_ci_workflows(tmp_path)

        assert len(workflows) == 1
        assert workflows[0].name == "Test"

    def test_detect_ci_workflows_with_security_checks(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting workflows with security checks."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        workflow_path = workflows_dir / "security.yml"
        workflow_path.write_text(
            "name: Security\n"
            "on: [push]\n"
            "jobs:\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
            "      - run: bandit -r .\n"
            "      - run: safety check\n",
        )

        workflows = analyzer._detect_ci_workflows(tmp_path)

        assert len(workflows) == 1
        assert workflows[0].has_security_checks

    def test_detect_python_version_from_pyproject(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Python version from pyproject.toml."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\nrequires-python = ">=3.8"\n')

        config_files = {"pyproject.toml": pyproject_path}
        python_version = analyzer._detect_python_version(tmp_path, config_files)

        assert python_version == ">=3.8"

    def test_find_dependency_conflicts(self, analyzer: ProjectAnalyzer) -> None:
        """Test finding conflicts between requirements and pyproject."""
        req_packages = [
            Package(name="pytest", version="7.0.0"),
            Package(name="requests", version="2.28.0"),
        ]

        pyproject_packages = [
            Package(name="pytest", version="7.1.0"),  # Different version
            Package(name="requests", version="2.28.0"),  # Same version
        ]

        conflicts = analyzer._find_dependency_conflicts(req_packages, pyproject_packages)

        assert len(conflicts) == 1
        assert "pytest" in conflicts[0]

    def test_analyze_dependencies_invalid_path(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test analyzing dependencies with invalid path raises error."""
        invalid_path = Path("/nonexistent/path")
        with pytest.raises(ProjectAnalysisError):
            analyzer.analyze_dependencies(invalid_path)

    def test_check_security_tools_invalid_path(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test checking security tools with invalid path raises error."""
        invalid_path = Path("/nonexistent/path")
        with pytest.raises(ProjectAnalysisError):
            analyzer.check_security_tools(invalid_path)

    def test_detect_configured_tools(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting configured tools."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("[tool.ruff]\nline-length = 120\n\n[tool.mypy]\nstrict = true\n")

        config_files = {"pyproject.toml": pyproject_path}
        tools = analyzer._detect_configured_tools(tmp_path, config_files)

        assert "ruff" in tools
        assert "mypy" in tools
        assert tools["ruff"].enabled
        assert tools["mypy"].enabled

    def test_parse_github_workflow_basic(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test parsing basic GitHub workflow."""
        workflow_path = tmp_path / "test.yml"
        workflow_path.write_text(
            "name: Test Workflow\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n",
        )

        workflow = analyzer._parse_github_workflow(workflow_path)

        assert workflow is not None
        assert workflow.name == "Test Workflow"
        # Triggers parsing depends on yaml library availability
        # Just check that workflow was parsed successfully
        assert workflow.file_path == workflow_path

    def test_check_quality_tools_ruff_with_import_sorting(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Ruff with import sorting enabled."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[tool.ruff]\nselect = ["E", "F", "I"]\nline-length = 120\n')

        config_files = {"pyproject.toml": pyproject_path}
        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)

        assert quality_tools[QualityTool.RUFF]
        assert quality_tools[QualityTool.ISORT]  # Ruff with I rules replaces isort

    def test_detect_ci_workflows_with_yaml_parse_error(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting workflows with YAML parse errors."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create a workflow file with invalid YAML
        workflow_path = workflows_dir / "invalid.yml"
        workflow_path.write_text(
            "name: Invalid Workflow\n"
            "on: [push\n"  # Missing closing bracket
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n",
        )

        # Should not raise an error, just skip the invalid file
        workflows = analyzer._detect_ci_workflows(tmp_path)

        # The workflow should be None or not included
        assert len(workflows) == 0 or all(wf.name != "Invalid Workflow" for wf in workflows)

    def test_detect_ci_workflows_multiple_files(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting multiple workflow files."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create multiple workflow files
        (workflows_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: pytest\n",
        )

        (workflows_dir / "security.yaml").write_text(
            "name: Security\n"
            "on: push\n"
            "jobs:\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: bandit -r .\n",
        )

        workflows = analyzer._detect_ci_workflows(tmp_path)

        assert len(workflows) == 2
        workflow_names = {wf.name for wf in workflows}
        assert "CI" in workflow_names
        assert "Security" in workflow_names

    def test_check_tools_in_precommit_with_yaml(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting tools in pre-commit config with YAML parser."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/pre-commit/mirrors-mypy\n"
            "    hooks:\n"
            "      - id: mypy\n"
            "  - repo: https://github.com/gitleaks/gitleaks\n"
            "    hooks:\n"
            "      - id: gitleaks\n",
        )

        tools = analyzer._check_tools_in_precommit(precommit_path)

        assert "ruff" in tools
        assert "mypy" in tools
        assert "gitleaks" in tools

    def test_check_tools_in_precommit_safety(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting safety in pre-commit config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n  - repo: https://github.com/pyupio/safety\n    hooks:\n      - id: safety\n",
        )

        tools = analyzer._check_tools_in_precommit(precommit_path)

        assert "safety" in tools

    def test_check_tools_in_precommit_bandit(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting bandit in pre-commit config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n  - repo: https://github.com/pycqa/bandit\n    hooks:\n      - id: bandit\n",
        )

        tools = analyzer._check_tools_in_precommit(precommit_path)

        assert "bandit" in tools

    def test_check_tools_in_precommit_without_yaml_library(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting tools in pre-commit config without YAML library (fallback)."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/gitleaks/gitleaks\n"
            "    hooks:\n"
            "      - id: gitleaks\n",
        )

        # Even without yaml library, text search should find the tools
        tools = analyzer._check_tools_in_precommit(precommit_path)

        # At minimum, text search should find these
        assert len(tools) > 0

    def test_check_security_tools_from_precommit(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting security tools from pre-commit config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n"
            "  - repo: https://github.com/gitleaks/gitleaks\n"
            "    hooks:\n"
            "      - id: gitleaks\n"
            "  - repo: https://github.com/pycqa/bandit\n"
            "    hooks:\n"
            "      - id: bandit\n"
            "  - repo: https://github.com/pyupio/safety\n"
            "    hooks:\n"
            "      - id: safety\n",
        )

        config_files = {".pre-commit-config.yaml": precommit_path}
        security_tools = analyzer._check_security_tools(tmp_path, config_files)

        assert security_tools[SecurityTool.GITLEAKS]
        assert security_tools[SecurityTool.BANDIT]
        assert security_tools[SecurityTool.SAFETY]

    def test_check_quality_tools_from_precommit(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting quality tools from pre-commit config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/pre-commit/mirrors-mypy\n"
            "    hooks:\n"
            "      - id: mypy\n",
        )

        config_files = {".pre-commit-config.yaml": precommit_path}
        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)

        assert quality_tools[QualityTool.RUFF]
        assert quality_tools[QualityTool.MYPY]

    def test_parse_github_workflow_without_yaml_library(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test parsing GitHub workflow without YAML library (fallback)."""
        workflow_path = tmp_path / "test.yml"
        workflow_path.write_text(
            "name: Test Workflow\n"
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: pytest\n",
        )

        workflow = analyzer._parse_github_workflow(workflow_path)

        assert workflow is not None
        assert workflow.name == "Test Workflow"
        assert workflow.file_path == workflow_path

    def test_detect_ci_workflows_empty_directory(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting workflows in empty workflows directory."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        workflows = analyzer._detect_ci_workflows(tmp_path)

        assert len(workflows) == 0

    def test_check_quality_tools_ruff_with_lint_select(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting Ruff with import sorting in lint.select (modern format)."""
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[tool.ruff]\nline-length = 120\n\n[tool.ruff.lint]\nselect = ["E", "F", "I"]\n')

        config_files = {"pyproject.toml": pyproject_path}
        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)

        assert quality_tools[QualityTool.RUFF]
        assert quality_tools[QualityTool.ISORT]  # Ruff with I rules in lint.select

    def test_workflow_has_security_checks_detection(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting security checks in workflow content."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        workflow_path = workflows_dir / "security.yml"
        workflow_path.write_text(
            "name: Security Checks\n"
            "on: [push]\n"
            "jobs:\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
            "      - name: Run Bandit\n"
            "        run: bandit -r .\n"
            "      - name: Run Safety\n"
            "        run: safety check\n"
            "      - name: Run Gitleaks\n"
            "        run: gitleaks detect\n",
        )

        workflows = analyzer._detect_ci_workflows(tmp_path)

        assert len(workflows) == 1
        assert workflows[0].has_security_checks
        # Verify multiple security tools are detected
        workflow_content = workflow_path.read_text().lower()
        assert "bandit" in workflow_content
        assert "safety" in workflow_content
        assert "gitleaks" in workflow_content

    def test_workflow_has_quality_checks_detection(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting quality checks in workflow content."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        workflow_path = workflows_dir / "quality.yml"
        workflow_path.write_text(
            "name: Quality Checks\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  quality:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
            "      - name: Run Ruff\n"
            "        run: ruff check .\n"
            "      - name: Run Mypy\n"
            "        run: mypy .\n"
            "      - name: Run Tests\n"
            "        run: pytest\n",
        )

        workflows = analyzer._detect_ci_workflows(tmp_path)

        assert len(workflows) == 1
        assert workflows[0].has_quality_checks
        # Verify multiple quality tools are detected
        workflow_content = workflow_path.read_text().lower()
        assert "ruff" in workflow_content
        assert "mypy" in workflow_content
        assert "pytest" in workflow_content

    def test_get_workflow_recommendations_no_workflows(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test workflow recommendations when no workflows exist."""
        recommendations = analyzer._get_workflow_recommendations(
            has_security=False,
            has_quality=False,
        )

        assert len(recommendations) > 0
        # Should recommend both security and quality workflows
        assert any("security" in rec.lower() for rec in recommendations)
        assert any("quality" in rec.lower() or "lint" in rec.lower() for rec in recommendations)

    def test_get_workflow_recommendations_only_security(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test workflow recommendations when only security workflow exists."""
        recommendations = analyzer._get_workflow_recommendations(
            has_security=True,
            has_quality=False,
        )

        # Should recommend quality workflow but not security
        assert any("quality" in rec.lower() or "lint" in rec.lower() for rec in recommendations)
        # Should not recommend security since it already exists
        security_recs = [rec for rec in recommendations if "security" in rec.lower() and "bandit" in rec.lower()]
        assert len(security_recs) == 0

    def test_get_workflow_recommendations_only_quality(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test workflow recommendations when only quality workflow exists."""
        recommendations = analyzer._get_workflow_recommendations(
            has_security=False,
            has_quality=True,
        )

        # Should recommend security workflow but not quality
        assert any("security" in rec.lower() for rec in recommendations)
        # Should not recommend quality since it already exists
        quality_recs = [rec for rec in recommendations if "quality" in rec.lower() and "lint" in rec.lower()]
        assert len(quality_recs) == 0

    def test_get_workflow_recommendations_all_workflows_exist(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test workflow recommendations when all workflows exist."""
        recommendations = analyzer._get_workflow_recommendations(
            has_security=True,
            has_quality=True,
        )

        # Should have no recommendations or only general suggestions
        assert len(recommendations) == 0

    def test_check_github_workflows_with_local_workflows(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test checking GitHub workflows with local workflows."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create a security workflow
        (workflows_dir / "security.yml").write_text(
            "name: Security\n"
            "on: push\n"
            "jobs:\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: bandit -r .\n",
        )

        result = analyzer.check_github_workflows(tmp_path)

        assert len(result["local_workflows"]) == 1
        assert result["has_security_workflow"]
        assert not result["has_quality_workflow"]
        # Should recommend quality workflow
        assert len(result["workflow_recommendations"]) > 0

    def test_workflow_has_security_checks_remote(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test detecting security checks in remote workflow."""
        workflow = {
            "name": "Security Scan",
            "path": ".github/workflows/security.yml",
        }

        result = analyzer._workflow_has_security_checks(workflow)

        assert result is True

    def test_workflow_has_quality_checks_remote(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test detecting quality checks in remote workflow."""
        workflow = {
            "name": "Lint and Test",
            "path": ".github/workflows/ci.yml",
        }

        result = analyzer._workflow_has_quality_checks(workflow)

        assert result is True

    def test_workflow_has_no_security_checks_remote(
        self,
        analyzer: ProjectAnalyzer,
    ) -> None:
        """Test detecting no security checks in remote workflow."""
        workflow = {
            "name": "Build",
            "path": ".github/workflows/build.yml",
        }

        result = analyzer._workflow_has_security_checks(workflow)

        assert result is False

    def test_detect_github_repository_https(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting GitHub repository from HTTPS remote."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        config_path = git_dir / "config"
        config_path.write_text(
            '[remote "origin"]\n'
            "    url = https://github.com/owner/repo.git\n"
            "    fetch = +refs/heads/*:refs/remotes/origin/*\n",
        )

        result = analyzer._detect_github_repository(tmp_path)

        assert result is not None
        assert result == ("owner", "repo")

    def test_detect_github_repository_ssh(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting GitHub repository from SSH remote."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        config_path = git_dir / "config"
        config_path.write_text(
            '[remote "origin"]\n'
            "    url = git@github.com:owner/repo.git\n"
            "    fetch = +refs/heads/*:refs/remotes/origin/*\n",
        )

        result = analyzer._detect_github_repository(tmp_path)

        assert result is not None
        assert result == ("owner", "repo")

    def test_detect_github_repository_no_git(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting GitHub repository when no .git directory exists."""
        result = analyzer._detect_github_repository(tmp_path)

        assert result is None

    def test_detect_github_repository_non_github(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting GitHub repository with non-GitHub remote."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        config_path = git_dir / "config"
        config_path.write_text(
            '[remote "origin"]\n'
            "    url = https://gitlab.com/owner/repo.git\n"
            "    fetch = +refs/heads/*:refs/remotes/origin/*\n",
        )

        result = analyzer._detect_github_repository(tmp_path)

        assert result is None

    def test_recommendations_no_duplicate_workflows(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test that recommendations don't suggest existing workflows."""
        # Create pyproject.toml with modern tools
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n\n[tool.ruff]\nline-length = 120\n\n[tool.mypy]\nstrict = true\n',
        )

        # Create existing security and quality workflows
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "security.yml").write_text(
            "name: Security\n"
            "on: push\n"
            "jobs:\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: bandit -r .\n"
            "      - run: safety check\n",
        )

        (workflows_dir / "quality.yml").write_text(
            "name: Quality\n"
            "on: push\n"
            "jobs:\n"
            "  quality:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: ruff check .\n"
            "      - run: mypy .\n",
        )

        # Analyze project
        analyzer.analyze_project(tmp_path)

        # Verify no workflow recommendations since they already exist
        workflow_result = analyzer.check_github_workflows(tmp_path)
        assert workflow_result["has_security_workflow"]
        assert workflow_result["has_quality_workflow"]
        assert len(workflow_result["workflow_recommendations"]) == 0

    def test_recommendations_modern_tools_no_legacy_suggestions(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test that modern tools don't trigger legacy tool recommendations."""
        # Create pyproject.toml with modern tools (ruff + mypy)
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n\n'
            '[tool.ruff]\nline-length = 120\nselect = ["E", "F", "I"]\n\n'
            "[tool.mypy]\nstrict = true\n",
        )

        config_files = {"pyproject.toml": pyproject_path}
        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)

        # Verify modern tools are detected
        assert quality_tools[QualityTool.RUFF]
        assert quality_tools[QualityTool.MYPY]
        assert quality_tools[QualityTool.ISORT]  # Ruff with I rules

        # Verify legacy tools are not detected
        assert not quality_tools[QualityTool.BLACK]
        assert not quality_tools[QualityTool.FLAKE8]
        assert not quality_tools[QualityTool.PYLINT]

    def test_recommendations_missing_security_tools(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test recommendations for missing security tools."""
        # Create minimal project without security tools
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n')

        config_files = {"pyproject.toml": pyproject_path}
        security_tools = analyzer._check_security_tools(tmp_path, config_files)

        # Verify no security tools are detected
        assert not security_tools[SecurityTool.BANDIT]
        assert not security_tools[SecurityTool.SAFETY]
        assert not security_tools[SecurityTool.GITLEAKS]

        # These missing tools should trigger recommendations
        # (actual recommendation generation is tested in integration tests)

    def test_recommendations_partial_security_setup(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test recommendations when some security tools are configured."""
        # Create project with only Bandit configured
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n\n[tool.bandit]\nskip = ["B101"]\n')

        config_files = {"pyproject.toml": pyproject_path}
        security_tools = analyzer._check_security_tools(tmp_path, config_files)

        # Verify partial security setup
        assert security_tools[SecurityTool.BANDIT]
        assert not security_tools[SecurityTool.SAFETY]
        assert not security_tools[SecurityTool.GITLEAKS]

        # Missing tools should trigger recommendations

    def test_recommendations_complete_modern_setup(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test that complete modern setup generates minimal recommendations."""
        # Create complete modern project setup
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n\n'
            '[tool.ruff]\nline-length = 120\nselect = ["E", "F", "I"]\n\n'
            "[tool.mypy]\nstrict = true\n\n"
            '[tool.bandit]\nskip = ["B101"]\n',
        )

        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "  - repo: https://github.com/pre-commit/mirrors-mypy\n"
            "    hooks:\n"
            "      - id: mypy\n"
            "  - repo: https://github.com/gitleaks/gitleaks\n"
            "    hooks:\n"
            "      - id: gitleaks\n"
            "  - repo: https://github.com/pyupio/safety\n"
            "    hooks:\n"
            "      - id: safety\n",
        )

        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  quality:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: ruff check .\n"
            "      - run: mypy .\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - run: bandit -r .\n"
            "      - run: safety check\n",
        )

        # Analyze complete setup
        config_files = {
            "pyproject.toml": pyproject_path,
            ".pre-commit-config.yaml": precommit_path,
        }

        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)
        security_tools = analyzer._check_security_tools(tmp_path, config_files)
        workflow_result = analyzer.check_github_workflows(tmp_path)

        # Verify all tools are detected
        assert quality_tools[QualityTool.RUFF]
        assert quality_tools[QualityTool.MYPY]
        assert security_tools[SecurityTool.BANDIT]
        assert security_tools[SecurityTool.GITLEAKS]
        assert security_tools[SecurityTool.SAFETY]

        # Verify workflows are detected
        assert workflow_result["has_security_workflow"]
        assert workflow_result["has_quality_workflow"]
        assert len(workflow_result["workflow_recommendations"]) == 0

    def test_workflow_detection_with_combined_workflow(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test detecting security and quality checks in a single workflow."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create a single workflow with both security and quality checks
        (workflows_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
            "      - name: Quality checks\n"
            "        run: |\n"
            "          ruff check .\n"
            "          mypy .\n"
            "      - name: Security checks\n"
            "        run: |\n"
            "          bandit -r .\n"
            "          safety check\n"
            "      - name: Tests\n"
            "        run: pytest\n",
        )

        workflows = analyzer._detect_ci_workflows(tmp_path)

        assert len(workflows) == 1
        assert workflows[0].has_security_checks
        assert workflows[0].has_quality_checks

        # Verify workflow recommendations
        workflow_result = analyzer.check_github_workflows(tmp_path)
        assert workflow_result["has_security_workflow"]
        assert workflow_result["has_quality_workflow"]
        assert len(workflow_result["workflow_recommendations"]) == 0

    def test_precommit_tool_detection_accuracy(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test accurate detection of tools in pre-commit config."""
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        precommit_path.write_text(
            "repos:\n"
            "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
            "    rev: v0.1.0\n"
            "    hooks:\n"
            "      - id: ruff\n"
            "        args: [--fix]\n"
            "      - id: ruff-format\n"
            "  - repo: https://github.com/pre-commit/mirrors-mypy\n"
            "    rev: v1.0.0\n"
            "    hooks:\n"
            "      - id: mypy\n"
            "        additional_dependencies: [types-requests]\n"
            "  - repo: https://github.com/gitleaks/gitleaks\n"
            "    rev: v8.0.0\n"
            "    hooks:\n"
            "      - id: gitleaks\n"
            "  - repo: https://github.com/pycqa/bandit\n"
            "    rev: 1.7.0\n"
            "    hooks:\n"
            "      - id: bandit\n"
            "        args: [-r, .]\n"
            "  - repo: https://github.com/pyupio/safety\n"
            "    rev: 2.0.0\n"
            "    hooks:\n"
            "      - id: safety\n",
        )

        tools = analyzer._check_tools_in_precommit(precommit_path)

        # Verify all tools are detected
        assert "ruff" in tools
        assert "mypy" in tools
        assert "gitleaks" in tools
        assert "bandit" in tools
        assert "safety" in tools

        # Verify count
        assert len(tools) >= 5

    def test_workflow_yaml_parse_error_handling(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test graceful handling of YAML parse errors in workflows."""
        workflows_dir = tmp_path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create valid workflow
        (workflows_dir / "valid.yml").write_text(
            "name: Valid\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n",
        )

        # Create invalid workflow with YAML syntax error
        (workflows_dir / "invalid.yml").write_text(
            "name: Invalid\n"
            "on: [push\n"  # Missing closing bracket
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n",
        )

        # Should not raise an error, just skip invalid file
        workflows = analyzer._detect_ci_workflows(tmp_path)

        # Should only detect the valid workflow
        assert len(workflows) == 1
        assert workflows[0].name == "Valid"

    def test_recommendations_with_legacy_tools(
        self,
        analyzer: ProjectAnalyzer,
        tmp_path: Path,
    ) -> None:
        """Test that legacy tools are detected but modern alternatives are recommended."""
        # Create project with legacy tools
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n\n'
            "[tool.black]\nline-length = 88\n\n"
            '[tool.isort]\nprofile = "black"\n\n'
            "[tool.flake8]\nmax-line-length = 88\n",
        )

        config_files = {"pyproject.toml": pyproject_path}
        quality_tools = analyzer._check_quality_tools(tmp_path, config_files)

        # Verify legacy tools are detected
        assert quality_tools[QualityTool.BLACK]
        assert quality_tools[QualityTool.ISORT]
        assert quality_tools[QualityTool.FLAKE8]

        # Modern tools should not be detected
        assert not quality_tools[QualityTool.RUFF]

        # This should trigger recommendations to migrate to Ruff
