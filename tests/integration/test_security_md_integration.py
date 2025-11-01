"""Integration tests for SECURITY.md generation with real templates."""

from pathlib import Path

import pytest

from secuority.core.applier import ConfigurationApplier
from secuority.core.template_manager import TemplateManager
from secuority.models.interfaces import ChangeType


class TestSecurityMdIntegration:
    """Integration tests for SECURITY.md generation."""

    @pytest.fixture
    def template_manager(self, tmp_path: Path) -> TemplateManager:
        """Create TemplateManager with test templates."""
        manager = TemplateManager()
        manager._template_dir = tmp_path

        # Create templates directory structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)

        # Copy the actual SECURITY.md template
        security_template_content = """# Security Policy

## Supported Versions

We release patches for security vulnerabilities. Which versions are eligible for
receiving such patches depends on the CVSS v3.0 Rating:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of our software seriously. If you believe you have found a
security vulnerability, please report it to us as described below.

### Where to Report

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via one of the following methods:

1. **Email**: Send an email to
   [{{ author_email | default('security@example.com') }}](mailto:{{ author_email | default('security@example.com') }})
2. **GitHub Security Advisories**: Use the [GitHub Security Advisory](../../security/advisories/new) feature

### What to Include

Please include the following information in your report:

- Type of issue (e.g., buffer overflow, SQL injection, cross-site scripting, etc.)
- Full paths of source file(s) related to the manifestation of the issue
- The location of the affected source code (tag/branch/commit or direct URL)
- Any special configuration required to reproduce the issue
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the issue, including how an attacker might exploit it

### Response Timeline

- **Initial Response**: We will acknowledge receipt of your vulnerability report within 48 hours
- **Status Updates**: We will send you regular updates about our progress, at least every 7 days
- **Resolution**: We aim to resolve critical vulnerabilities within 30 days of the initial report

### Disclosure Policy

- We request that you give us reasonable time to investigate and mitigate an issue before public disclosure
- We will credit you in our security advisory (unless you prefer to remain anonymous)
- We will coordinate the disclosure timeline with you

## Security Update Process

When we receive a security bug report, we will:

1. Confirm the problem and determine affected versions
2. Audit code to find any similar problems
3. Prepare fixes for all supported versions
4. Release new security patch versions as soon as possible

## Security Best Practices

When using this project, we recommend:

- Always use the latest stable version
- Keep all dependencies up to date
- Follow the principle of least privilege
- Enable all available security features
- Review and follow our security guidelines in the documentation

## Security Features

This project includes the following security measures:

- Automated dependency vulnerability scanning with Safety and Dependabot
- Static code analysis with Bandit
- Secret scanning with gitleaks
- Regular security audits
- Secure coding practices enforcement

## Contact

For any security-related questions or concerns, please contact:

- **Security Team**:
  [{{ author_email | default('security@example.com') }}](mailto:{{ author_email | default('security@example.com') }})
- **Project Maintainers**: See [MAINTAINERS.md](MAINTAINERS.md) or [CODEOWNERS](.github/CODEOWNERS)

## Acknowledgments

We would like to thank the following individuals for responsibly disclosing security vulnerabilities:

<!-- Security researchers will be listed here -->

---

**Note**: This security policy is subject to change. Please check back regularly for updates.
"""
        (templates_dir / "SECURITY.md.template").write_text(security_template_content)

        return manager

    @pytest.fixture
    def applier(self, tmp_path: Path) -> ConfigurationApplier:
        """Create ConfigurationApplier instance."""
        return ConfigurationApplier(backup_dir=tmp_path / "backups")

    def test_generate_security_md_with_real_template(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test generating SECURITY.md with real template."""
        # Load templates
        templates = template_manager.load_templates()
        assert "SECURITY.md.template" in templates

        # Create project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        security_md_path = project_dir / "SECURITY.md"
        template_content = templates["SECURITY.md.template"]

        # Generate SECURITY.md
        change = applier.merge_file_configurations(security_md_path, template_content)

        assert change.change_type == ChangeType.CREATE
        assert "Security Policy" in change.new_content
        assert "Reporting a Vulnerability" in change.new_content
        assert "example.com" in change.new_content

    def test_generate_security_md_with_project_info(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test generating SECURITY.md with project information."""
        # Load templates
        templates = template_manager.load_templates()

        # Create project with pyproject.toml
        project_dir = tmp_path / "my_secure_project"
        project_dir.mkdir()

        pyproject_path = project_dir / "pyproject.toml"
        pyproject_content = """[project]
name = "my-secure-project"
version = "1.0.0"
description = "A highly secure Python application"
authors = [
    {name = "Security Team", email = "security@mysecureproject.com"}
]

[project.urls]
Homepage = "https://mysecureproject.com"
Repository = "https://github.com/secteam/my-secure-project"
Issues = "https://github.com/secteam/my-secure-project/issues"
"""
        pyproject_path.write_text(pyproject_content)

        security_md_path = project_dir / "SECURITY.md"
        template_content = templates["SECURITY.md.template"]

        # Generate SECURITY.md
        change = applier.merge_file_configurations(security_md_path, template_content)

        # Verify content was generated (uses defaults since not processing pyproject.toml)
        assert "example.com" in change.new_content
        assert "Security Policy" in change.new_content

    def test_apply_security_md_change(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test applying SECURITY.md change to filesystem."""
        # Load templates
        templates = template_manager.load_templates()

        # Create project directory
        project_dir = tmp_path / "apply_test_project"
        project_dir.mkdir()

        security_md_path = project_dir / "SECURITY.md"
        template_content = templates["SECURITY.md.template"]

        # Generate change
        change = applier.merge_file_configurations(security_md_path, template_content)

        # Apply change
        result = applier.apply_changes([change], dry_run=False)

        # Verify file was created
        assert security_md_path.exists()
        assert len(result.successful_changes) == 1
        assert len(result.failed_changes) == 0

        # Verify content
        content = security_md_path.read_text()
        assert "Security Policy" in content
        assert "Reporting a Vulnerability" in content

    def test_merge_security_md_with_existing_content(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test merging SECURITY.md template with existing file."""
        # Load templates
        templates = template_manager.load_templates()

        # Create project with existing SECURITY.md
        project_dir = tmp_path / "merge_test_project"
        project_dir.mkdir()

        security_md_path = project_dir / "SECURITY.md"
        existing_content = """# Security Policy

## Our Custom Policy

We have a custom security policy.

## Reporting

Please email us at custom@example.com
"""
        security_md_path.write_text(existing_content)

        template_content = templates["SECURITY.md.template"]

        # Generate merge change
        change = applier.merge_file_configurations(security_md_path, template_content)

        assert change.change_type == ChangeType.MERGE
        # Text merge should preserve or combine content
        assert change.new_content is not None

    def test_security_md_dry_run(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test SECURITY.md generation in dry-run mode."""
        # Load templates
        templates = template_manager.load_templates()

        # Create project directory
        project_dir = tmp_path / "dry_run_project"
        project_dir.mkdir()

        security_md_path = project_dir / "SECURITY.md"
        template_content = templates["SECURITY.md.template"]

        # Generate change
        change = applier.merge_file_configurations(security_md_path, template_content)

        # Apply in dry-run mode
        result = applier.apply_changes([change], dry_run=True)

        # Verify file was NOT created
        assert not security_md_path.exists()
        assert len(result.successful_changes) == 1
        assert result.dry_run is True

    def test_security_md_with_backup(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test SECURITY.md update creates backup."""
        # Load templates
        templates = template_manager.load_templates()

        # Create project with existing SECURITY.md
        project_dir = tmp_path / "backup_test_project"
        project_dir.mkdir()

        security_md_path = project_dir / "SECURITY.md"
        original_content = "# Original Security Policy\n\nOld content."
        security_md_path.write_text(original_content)

        template_content = templates["SECURITY.md.template"]

        # Generate merge change
        change = applier.merge_file_configurations(security_md_path, template_content)

        # Apply change
        result = applier.apply_changes([change], dry_run=False)

        # Verify file was updated (backup is created internally by file_ops)
        assert len(result.successful_changes) == 1
        assert security_md_path.exists()

        # Verify content was merged
        content = security_md_path.read_text()
        assert "Security Policy" in content

    def test_security_md_template_not_found(
        self,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test handling when SECURITY.md template is not found."""
        # Create empty template manager
        manager = TemplateManager()
        manager._template_dir = tmp_path

        # Create empty templates directory
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True)

        # Load templates - should succeed but not include SECURITY.md.template
        templates = manager.load_templates()

        # Verify SECURITY.md.template is not in templates
        assert "SECURITY.md.template" not in templates

    def test_security_md_with_minimal_project_info(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test SECURITY.md generation with minimal project information."""
        # Load templates
        templates = template_manager.load_templates()

        # Create project with minimal pyproject.toml
        project_dir = tmp_path / "minimal_project"
        project_dir.mkdir()

        pyproject_path = project_dir / "pyproject.toml"
        pyproject_content = """[project]
name = "minimal"
"""
        pyproject_path.write_text(pyproject_content)

        security_md_path = project_dir / "SECURITY.md"
        template_content = templates["SECURITY.md.template"]

        # Generate SECURITY.md
        change = applier.merge_file_configurations(security_md_path, template_content)

        # Should use defaults for missing fields
        assert "example.com" in change.new_content
        # Content should be generated
        assert "Security Policy" in change.new_content

    def test_security_md_preserves_github_actions_syntax(
        self,
        template_manager: TemplateManager,
        applier: ConfigurationApplier,
        tmp_path: Path,
    ) -> None:
        """Test that GitHub Actions syntax is preserved in SECURITY.md."""
        # Create custom template with GitHub Actions variables
        manager = TemplateManager()
        manager._template_dir = tmp_path

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        template_with_actions = """# Security Policy

Project: {{ project_name }}

GitHub Actions: ${{ github.repository }}
Secret: ${{ secrets.TOKEN }}
"""
        (templates_dir / "SECURITY.md.template").write_text(template_with_actions)

        templates = manager.load_templates()

        # Create project
        project_dir = tmp_path / "actions_project"
        project_dir.mkdir()

        security_md_path = project_dir / "SECURITY.md"
        template_content = templates["SECURITY.md.template"]

        # Generate SECURITY.md
        change = applier.merge_file_configurations(security_md_path, template_content)

        # Verify GitHub Actions variables are preserved
        assert "${{ github.repository }}" in change.new_content
        assert "${{ secrets.TOKEN }}" in change.new_content
