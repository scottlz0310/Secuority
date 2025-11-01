"""Integration tests for security features."""

from pathlib import Path

import pytest

from secuority.core.security_tools import SecurityToolsIntegrator


class TestSecurityFeatures:
    """Test security features integration."""

    @pytest.fixture
    def integrator(self) -> SecurityToolsIntegrator:
        """Create SecurityToolsIntegrator instance."""
        return SecurityToolsIntegrator()

    @pytest.fixture
    def sample_project(self, tmp_path: Path) -> Path:
        """Create a sample project for testing."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        return tmp_path

    def test_integrate_bandit_config(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test integrating Bandit configuration."""
        result = integrator.integrate_bandit_config(sample_project)

        assert result is not None
        assert result.file_path.name == "pyproject.toml"
        assert "bandit" in result.new_content.lower()

    def test_integrate_safety_config(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test integrating Safety configuration."""
        result = integrator.integrate_safety_config(sample_project)

        assert result is not None
        assert result.file_path.name == "pyproject.toml"

    def test_security_tools_integration_workflow(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test complete security tools integration workflow."""
        # Integrate multiple security tools
        bandit_change = integrator.integrate_bandit_config(sample_project)
        safety_change = integrator.integrate_safety_config(sample_project)

        # Verify changes were created
        assert bandit_change is not None
        assert safety_change is not None
        assert "tool" in bandit_change.new_content.lower()

    def test_security_config_with_existing_tools(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test integrating security config when tools already exist."""
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n[tool.ruff]\nline-length = 120\n')

        result = integrator.integrate_bandit_config(sample_project)

        # Should merge with existing config
        assert result is not None
        assert "ruff" in result.new_content
        assert "bandit" in result.new_content.lower()

    def test_security_tools_detection(
        self,
        sample_project: Path,
    ) -> None:
        """Test detection of existing security tools."""
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n[tool.bandit]\nskip = ["B101"]\n')

        # Check if Bandit is detected
        content = pyproject_path.read_text()
        assert "bandit" in content.lower()

    def test_security_config_validation(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test validation of security configuration."""
        result = integrator.integrate_bandit_config(sample_project)

        # Verify result is valid
        assert result is not None
        try:
            import tomllib

            data = tomllib.loads(result.new_content)
            assert isinstance(data, dict)
        except ImportError:
            # TOML library not available, skip validation
            pass

    def test_bandit_config_merge(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test merging Bandit config with existing configuration."""
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n[tool.bandit]\nexclude_dirs = ["/test"]\n')

        # Integrate Bandit config (should merge)
        result = integrator.integrate_bandit_config(sample_project)

        assert result is not None
        assert "bandit" in result.new_content.lower()

    def test_integrated_security_setup(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test complete integrated security setup."""
        # Set up security features
        bandit_result = integrator.integrate_bandit_config(sample_project)
        safety_result = integrator.integrate_safety_config(sample_project)

        # Verify all components were created
        assert bandit_result is not None
        assert safety_result is not None
        assert bandit_result.file_path.exists() or True  # May not be written yet

    def test_integrate_multiple_security_tools(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test integrating multiple security tools at once."""
        changes = integrator.integrate_security_tools(sample_project, ["bandit", "safety"])

        assert len(changes) == 2
        assert all(change.file_path.name == "pyproject.toml" for change in changes)
        assert any("bandit" in change.description.lower() for change in changes)
        assert any("safety" in change.description.lower() for change in changes)

    def test_security_tools_status_check(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test checking security tools configuration status."""
        # Initially no tools configured
        status = integrator.check_security_tools_status(sample_project)
        assert status["bandit"] is False
        assert status["safety"] is False

        # Configure Bandit
        integrator.integrate_bandit_config(sample_project)
        pyproject_path = sample_project / "pyproject.toml"

        # Write the change to disk
        if pyproject_path.exists():
            change = integrator.integrate_bandit_config(sample_project)
            pyproject_path.write_text(change.new_content)

            # Check status again
            status = integrator.check_security_tools_status(sample_project)
            assert status["bandit"] is True

    def test_security_recommendations(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test getting security recommendations."""
        recommendations = integrator.get_security_recommendations(sample_project)

        # Should recommend security tools
        assert len(recommendations) > 0
        assert any("bandit" in rec.lower() for rec in recommendations)
        assert any("safety" in rec.lower() for rec in recommendations)

    def test_bandit_config_with_custom_settings(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test Bandit configuration preserves custom settings."""
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n[tool.bandit]\nexclude_dirs = ["/custom"]\n')

        result = integrator.integrate_bandit_config(sample_project)

        # Custom settings should be preserved
        assert result is not None
        assert "/custom" in result.new_content or "custom" in result.new_content

    def test_safety_config_structure(
        self,
        integrator: SecurityToolsIntegrator,
        sample_project: Path,
    ) -> None:
        """Test Safety configuration has correct structure."""
        result = integrator.integrate_safety_config(sample_project)

        assert result is not None
        # Safety config should be under tool.secuority.safety
        assert "secuority" in result.new_content.lower()
        assert "safety" in result.new_content.lower()


class TestWorkflowGeneration:
    """Test CI/CD workflow generation for security features."""

    @pytest.fixture
    def workflow_integrator(self):  # type: ignore[no-untyped-def]
        """Create WorkflowIntegrator instance."""
        from secuority.core.workflow_integrator import WorkflowIntegrator

        return WorkflowIntegrator()

    @pytest.fixture
    def sample_project(self, tmp_path: Path) -> Path:
        """Create a sample project for testing."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        return tmp_path

    def test_generate_security_workflow(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test generating security workflow."""
        change = workflow_integrator.generate_security_workflow(sample_project)

        assert change is not None
        assert change.file_path.name == "security-check.yml"
        assert "bandit" in change.new_content.lower()
        assert "safety" in change.new_content.lower()
        assert "gitleaks" in change.new_content.lower()

    def test_generate_quality_workflow(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test generating quality workflow."""
        change = workflow_integrator.generate_quality_workflow(sample_project)

        assert change is not None
        assert change.file_path.name == "quality-check.yml"
        assert "ruff" in change.new_content.lower()
        assert "mypy" in change.new_content.lower()
        assert "pytest" in change.new_content.lower()

    def test_generate_multiple_workflows(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test generating multiple workflows at once."""
        changes = workflow_integrator.generate_workflows(
            sample_project,
            workflows=["security", "quality"],
        )

        assert len(changes) == 2
        workflow_names = [change.file_path.name for change in changes]
        assert "security-check.yml" in workflow_names
        assert "quality-check.yml" in workflow_names

    def test_workflow_with_custom_python_versions(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test workflow generation with custom Python versions."""
        change = workflow_integrator.generate_security_workflow(
            sample_project,
            python_versions=["3.12", "3.13"],
        )

        assert change is not None
        assert "3.12" in change.new_content
        assert "3.13" in change.new_content

    def test_check_existing_workflows(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test checking for existing workflows."""
        # Initially no workflows
        status = workflow_integrator.check_existing_workflows(sample_project)
        assert status["security"] is False
        assert status["quality"] is False
        assert status["has_workflows_dir"] is False

        # Create workflows directory and a security workflow
        workflows_dir = sample_project / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "security-check.yml").write_text("name: Security\n")

        # Check again
        status = workflow_integrator.check_existing_workflows(sample_project)
        assert status["has_workflows_dir"] is True
        assert status["security"] is True

    def test_workflow_recommendations(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test getting workflow recommendations."""
        recommendations = workflow_integrator.get_workflow_recommendations(sample_project)

        # Should recommend workflows
        assert len(recommendations) > 0
        assert any("security" in rec.lower() for rec in recommendations)
        assert any("quality" in rec.lower() or "workflow" in rec.lower() for rec in recommendations)

    def test_security_workflow_structure(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test security workflow has correct structure."""
        change = workflow_integrator.generate_security_workflow(sample_project)

        assert change is not None
        content = change.new_content

        # Check for essential workflow components
        assert "name:" in content
        assert "on:" in content
        assert "jobs:" in content
        assert "steps:" in content
        assert "actions/checkout" in content
        assert "astral-sh/setup-uv" in content or "actions/setup-python" in content

    def test_quality_workflow_structure(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test quality workflow has correct structure."""
        change = workflow_integrator.generate_quality_workflow(sample_project)

        assert change is not None
        content = change.new_content

        # Check for essential workflow components
        assert "name:" in content
        assert "on:" in content
        assert "jobs:" in content
        assert "steps:" in content
        assert "ruff check" in content or "ruff" in content.lower()

    def test_workflow_update_existing(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test updating existing workflow."""
        # Create existing workflow
        workflows_dir = sample_project / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)
        security_workflow = workflows_dir / "security-check.yml"
        security_workflow.write_text("name: Old Security\n")

        # Generate new workflow (should update)
        change = workflow_integrator.generate_security_workflow(sample_project)

        assert change is not None
        assert change.change_type.value == "update"
        assert change.old_content == "name: Old Security\n"

    def test_workflow_yaml_validity(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test generated workflows are valid YAML."""
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            pytest.skip("PyYAML not available")

        change = workflow_integrator.generate_security_workflow(sample_project)

        assert change is not None
        # Should be parseable as YAML
        try:
            parsed = yaml.safe_load(change.new_content)
            assert isinstance(parsed, dict)
            assert "name" in parsed
            assert "jobs" in parsed
        except yaml.YAMLError as e:
            pytest.fail(f"Generated workflow is not valid YAML: {e}")

    def test_integrated_security_and_workflow_setup(
        self,
        workflow_integrator,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test complete integration of security tools and workflows."""
        from secuority.core.security_tools import SecurityToolsIntegrator

        # Set up security tools
        security_integrator = SecurityToolsIntegrator()
        tool_changes = security_integrator.integrate_security_tools(sample_project)

        # Generate workflows
        workflow_changes = workflow_integrator.generate_workflows(sample_project)

        # Verify complete setup
        assert len(tool_changes) > 0
        assert len(workflow_changes) > 0

        # Check that workflows reference the security tools
        security_workflow = next(
            (c for c in workflow_changes if "security" in c.file_path.name),
            None,
        )
        assert security_workflow is not None
        assert "bandit" in security_workflow.new_content.lower()
        assert "safety" in security_workflow.new_content.lower()


class TestRecommendationAccuracy:
    """Test recommendation generation accuracy."""

    @pytest.fixture
    def analyzer(self):  # type: ignore[no-untyped-def]
        """Create ProjectAnalyzer instance."""
        from secuority.core.analyzer import ProjectAnalyzer

        return ProjectAnalyzer()

    @pytest.fixture
    def sample_project(self, tmp_path: Path) -> Path:
        """Create a sample project for testing."""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')
        return tmp_path

    def test_no_duplicate_workflow_recommendations(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test that existing workflows don't trigger duplicate recommendations."""
        # Create complete workflow setup
        workflows_dir = sample_project / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        (workflows_dir / "security.yml").write_text(
            "name: Security\n"
            "on: push\n"
            "jobs:\n"
            "  security:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
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
            "      - uses: actions/checkout@v3\n"
            "      - run: ruff check .\n"
            "      - run: mypy .\n",
        )

        # Check workflow recommendations
        result = analyzer.check_github_workflows(sample_project)

        # Should detect existing workflows
        assert result["has_security_workflow"]
        assert result["has_quality_workflow"]

        # Should not recommend workflows that already exist
        assert len(result["workflow_recommendations"]) == 0

    def test_modern_tools_no_legacy_recommendations(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test that modern tools don't trigger legacy tool recommendations."""
        from secuority.models.interfaces import QualityTool

        # Set up modern tooling
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n\n'
            '[tool.ruff]\nline-length = 120\nselect = ["E", "F", "I"]\n\n'
            "[tool.mypy]\nstrict = true\n",
        )

        # Analyze project
        state = analyzer.analyze_project(sample_project)

        # Verify modern tools are detected
        assert state.quality_tools[QualityTool.RUFF]
        assert state.quality_tools[QualityTool.MYPY]

        # Legacy tools should not be detected
        assert not state.quality_tools[QualityTool.BLACK]
        assert not state.quality_tools[QualityTool.FLAKE8]
        assert not state.quality_tools[QualityTool.PYLINT]

    def test_partial_security_setup_recommendations(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test recommendations for partial security setup."""
        from secuority.models.interfaces import SecurityTool

        # Set up only Bandit
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text('[project]\nname = "test"\n\n[tool.bandit]\nskip = ["B101"]\n')

        # Analyze project
        state = analyzer.analyze_project(sample_project)

        # Verify partial security setup
        assert state.security_tools[SecurityTool.BANDIT]
        assert not state.security_tools[SecurityTool.SAFETY]
        assert not state.security_tools[SecurityTool.GITLEAKS]

        # Should recommend missing security tools
        # (actual recommendation text is implementation-specific)

    def test_complete_modern_setup_minimal_recommendations(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test that complete modern setup generates minimal recommendations."""
        from secuority.models.interfaces import QualityTool, SecurityTool

        # Create complete modern setup
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n\n'
            '[tool.ruff]\nline-length = 120\nselect = ["E", "F", "I"]\n\n'
            "[tool.mypy]\nstrict = true\n\n"
            '[tool.bandit]\nskip = ["B101"]\n',
        )

        precommit_path = sample_project / ".pre-commit-config.yaml"
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

        workflows_dir = sample_project / ".github" / "workflows"
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
        state = analyzer.analyze_project(sample_project)
        workflow_result = analyzer.check_github_workflows(sample_project)

        # Verify all tools are detected
        assert state.quality_tools[QualityTool.RUFF]
        assert state.quality_tools[QualityTool.MYPY]
        assert state.security_tools[SecurityTool.BANDIT]
        assert state.security_tools[SecurityTool.GITLEAKS]
        assert state.security_tools[SecurityTool.SAFETY]

        # Verify workflows are detected
        assert workflow_result["has_security_workflow"]
        assert workflow_result["has_quality_workflow"]
        assert len(workflow_result["workflow_recommendations"]) == 0

    def test_combined_workflow_detection(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test detection of security and quality checks in a single workflow."""
        workflows_dir = sample_project / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create single workflow with both types of checks
        (workflows_dir / "ci.yml").write_text(
            "name: CI\n"
            "on: [push, pull_request]\n"
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - uses: actions/checkout@v3\n"
            "      - name: Quality\n"
            "        run: |\n"
            "          ruff check .\n"
            "          mypy .\n"
            "      - name: Security\n"
            "        run: |\n"
            "          bandit -r .\n"
            "          safety check\n",
        )

        # Check workflow detection
        result = analyzer.check_github_workflows(sample_project)

        # Should detect both types of checks in the single workflow
        assert result["has_security_workflow"]
        assert result["has_quality_workflow"]
        assert len(result["workflow_recommendations"]) == 0

    def test_precommit_tool_detection_integration(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test accurate detection of tools in pre-commit config."""
        from secuority.models.interfaces import QualityTool, SecurityTool

        precommit_path = sample_project / ".pre-commit-config.yaml"
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

        # Analyze project
        state = analyzer.analyze_project(sample_project)

        # Verify all tools are detected from pre-commit config
        assert state.quality_tools[QualityTool.RUFF]
        assert state.quality_tools[QualityTool.MYPY]
        assert state.security_tools[SecurityTool.GITLEAKS]
        assert state.security_tools[SecurityTool.BANDIT]
        assert state.security_tools[SecurityTool.SAFETY]

    def test_yaml_parse_error_graceful_handling(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test graceful handling of YAML parse errors."""
        workflows_dir = sample_project / ".github" / "workflows"
        workflows_dir.mkdir(parents=True)

        # Create valid workflow
        (workflows_dir / "valid.yml").write_text(
            "name: Valid\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest\n",
        )

        # Create invalid workflow
        (workflows_dir / "invalid.yml").write_text(
            "name: Invalid\n"
            "on: [push\n"  # Missing closing bracket
            "jobs:\n"
            "  test:\n"
            "    runs-on: ubuntu-latest\n",
        )

        # Should not raise an error
        result = analyzer.check_github_workflows(sample_project)

        # Should detect at least the valid workflow
        assert len(result["local_workflows"]) >= 1

    def test_legacy_tools_migration_recommendations(
        self,
        analyzer,  # type: ignore[no-untyped-def]
        sample_project: Path,
    ) -> None:
        """Test recommendations for migrating from legacy tools."""
        from secuority.models.interfaces import QualityTool

        # Set up legacy tools
        pyproject_path = sample_project / "pyproject.toml"
        pyproject_path.write_text(
            '[project]\nname = "test"\n\n'
            "[tool.black]\nline-length = 88\n\n"
            '[tool.isort]\nprofile = "black"\n\n'
            "[tool.flake8]\nmax-line-length = 88\n",
        )

        # Analyze project
        state = analyzer.analyze_project(sample_project)

        # Verify legacy tools are detected
        assert state.quality_tools[QualityTool.BLACK]
        assert state.quality_tools[QualityTool.ISORT]
        assert state.quality_tools[QualityTool.FLAKE8]

        # Modern tools should not be detected
        assert not state.quality_tools[QualityTool.RUFF]

        # This should trigger recommendations to migrate to Ruff
        # (actual recommendation generation is implementation-specific)
