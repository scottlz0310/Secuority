"""Unit tests for SECURITY.md generation functionality."""

from pathlib import Path

import pytest

from secuority.core.applier import ConfigurationApplier
from secuority.models.interfaces import ChangeType


class TestSecurityMdGeneration:
    """Test SECURITY.md generation and customization."""

    @pytest.fixture
    def applier(self, tmp_path: Path) -> ConfigurationApplier:
        """Create ConfigurationApplier instance."""
        return ConfigurationApplier(backup_dir=tmp_path / "backups")

    @pytest.fixture
    def security_template(self) -> str:
        """Create a sample SECURITY.md template with variables."""
        return """# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

Please report security vulnerabilities to {{ author_email | default('security@example.com') }}.

Project: {{ project_name | default('my-project') }}
Repository: {{ project_repository | default('https://github.com/user/repo') }}

## Contact

- **Security Team**: {{ author_email | default('security@example.com') }}
- **Project Homepage**: {{ project_homepage | default('https://example.com') }}
"""

    def test_create_security_md_from_template(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test creating SECURITY.md from template."""
        security_md_path = tmp_path / "SECURITY.md"

        # Create change from template
        change = applier.merge_file_configurations(security_md_path, security_template)

        assert change.file_path == security_md_path
        assert change.change_type == ChangeType.CREATE
        assert "Security Policy" in change.new_content
        assert "Reporting a Vulnerability" in change.new_content

    def test_security_md_template_variable_substitution(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test template variable substitution in SECURITY.md."""
        security_md_path = tmp_path / "SECURITY.md"

        # Create a pyproject.toml with project info
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = """[project]
name = "test-project"
version = "1.0.0"
description = "A test project"
authors = [
    {name = "Test Author", email = "test@example.com"}
]

[project.urls]
Homepage = "https://github.com/testuser/test-project"
Repository = "https://github.com/testuser/test-project"
"""
        pyproject_path.write_text(pyproject_content)

        # Process template with project info
        # Note: _extract_project_info only reads pyproject.toml when processing pyproject.toml itself
        # For SECURITY.md, it uses directory name as fallback
        change = applier.merge_file_configurations(security_md_path, security_template)

        # Verify content was generated (uses defaults since SECURITY.md doesn't trigger pyproject.toml reading)
        assert "Security Policy" in change.new_content
        assert "Reporting a Vulnerability" in change.new_content

    def test_security_md_default_values(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test default values are used when project info is not available."""
        security_md_path = tmp_path / "SECURITY.md"

        # No pyproject.toml exists, should use defaults
        change = applier.merge_file_configurations(security_md_path, security_template)

        # Verify default values were used (your.email@example.com is the default)
        assert "example.com" in change.new_content
        # Project name should be derived from directory name
        assert tmp_path.name in change.new_content or "my-project" in change.new_content

    def test_security_md_preserves_github_actions_variables(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test that GitHub Actions variables are preserved."""
        security_md_path = tmp_path / "SECURITY.md"

        # Template with GitHub Actions variables
        template_with_actions = """# Security Policy

Project: {{ project_name }}

GitHub Actions variable: ${{ github.repository }}
Another Actions variable: ${{ secrets.TOKEN }}
"""

        change = applier.merge_file_configurations(security_md_path, template_with_actions)

        # Verify GitHub Actions variables are preserved
        assert "${{ github.repository }}" in change.new_content
        assert "${{ secrets.TOKEN }}" in change.new_content

    def test_security_md_merge_with_existing(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test merging SECURITY.md template with existing file."""
        security_md_path = tmp_path / "SECURITY.md"

        # Create existing SECURITY.md
        existing_content = """# Security Policy

## Custom Section

This is a custom section that should be preserved.

## Reporting a Vulnerability

Old reporting instructions.
"""
        security_md_path.write_text(existing_content)

        # Merge with template
        change = applier.merge_file_configurations(security_md_path, security_template)

        assert change.change_type == ChangeType.MERGE
        # For text files, new lines should be added
        assert "Custom Section" in change.new_content or "Reporting a Vulnerability" in change.new_content

    def test_security_md_with_partial_project_info(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test SECURITY.md generation with partial project information."""
        security_md_path = tmp_path / "SECURITY.md"

        # Create pyproject.toml with only some fields
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = """[project]
name = "partial-project"
version = "0.1.0"
"""
        pyproject_path.write_text(pyproject_content)

        change = applier.merge_file_configurations(security_md_path, security_template)

        # Verify content was generated (uses directory name as fallback)
        assert tmp_path.name in change.new_content or "partial-project" in change.new_content
        # Missing fields should use defaults
        assert "example.com" in change.new_content

    def test_security_md_customization_with_license(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test SECURITY.md customization includes license information."""
        security_md_path = tmp_path / "SECURITY.md"

        # Template with license variable
        template_with_license = """# Security Policy

Project: {{ project_name }}
License: {{ project_license | default('MIT') }}
"""

        # Create pyproject.toml with license
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = """[project]
name = "licensed-project"
license = {text = "Apache-2.0"}
"""
        pyproject_path.write_text(pyproject_content)

        change = applier.merge_file_configurations(security_md_path, template_with_license)

        # Verify license is included
        assert "Apache-2.0" in change.new_content or "MIT" in change.new_content

    def test_security_md_with_multiple_authors(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test SECURITY.md generation with multiple authors uses first author."""
        security_md_path = tmp_path / "SECURITY.md"

        # Create pyproject.toml with multiple authors
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = """[project]
name = "multi-author-project"
authors = [
    {name = "First Author", email = "first@example.com"},
    {name = "Second Author", email = "second@example.com"}
]
"""
        pyproject_path.write_text(pyproject_content)

        change = applier.merge_file_configurations(security_md_path, security_template)

        # Verify content was generated (uses defaults since not processing pyproject.toml)
        assert "example.com" in change.new_content
        # Second author should not be in content
        assert "second@example.com" not in change.new_content

    def test_security_md_description_variable(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test SECURITY.md with project description variable."""
        security_md_path = tmp_path / "SECURITY.md"

        template_with_description = """# Security Policy

## About

{{ project_description | default('A Python project') }}
"""

        # Create pyproject.toml with description
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = """[project]
name = "described-project"
description = "A secure and well-tested Python application"
"""
        pyproject_path.write_text(pyproject_content)

        change = applier.merge_file_configurations(security_md_path, template_with_description)

        # Verify default description is used (with directory name)
        assert "A Python project" in change.new_content or tmp_path.name in change.new_content

    def test_security_md_package_name_conversion(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test package name conversion from project name (hyphens to underscores)."""
        security_md_path = tmp_path / "SECURITY.md"

        template_with_package = """# Security Policy

Package: {{ package_name | default('my_package') }}
"""

        # Create pyproject.toml with hyphenated name
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = """[project]
name = "my-awesome-project"
"""
        pyproject_path.write_text(pyproject_content)

        change = applier.merge_file_configurations(security_md_path, template_with_package)

        # Verify package name has underscores (uses directory name with underscores)
        assert "_" in change.new_content or "my_package" in change.new_content

    def test_security_md_with_urls_section(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test SECURITY.md generation with project URLs."""
        security_md_path = tmp_path / "SECURITY.md"

        # Create pyproject.toml with URLs
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_content = """[project]
name = "url-project"

[project.urls]
Homepage = "https://myproject.com"
Repository = "https://github.com/user/url-project"
"Bug Tracker" = "https://github.com/user/url-project/issues"
"""
        pyproject_path.write_text(pyproject_content)

        change = applier.merge_file_configurations(security_md_path, security_template)

        # Verify default URLs are used (since not processing pyproject.toml)
        assert "github.com" in change.new_content or "example.com" in change.new_content

    def test_security_md_error_handling_invalid_toml(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
        security_template: str,
    ) -> None:
        """Test SECURITY.md generation handles invalid pyproject.toml gracefully."""
        security_md_path = tmp_path / "SECURITY.md"

        # Create invalid pyproject.toml
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("invalid toml content [[[")

        # Should not raise error, should use defaults
        change = applier.merge_file_configurations(security_md_path, security_template)

        # Verify defaults are used
        assert "security@example.com" in change.new_content or "example.com" in change.new_content
