"""Unit tests for the security tools integrator."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from secuority.core.security_tools import SecurityToolsIntegrator, tomli_w
from secuority.core.security_tools import tomllib as module_tomllib
from secuority.models.exceptions import ConfigurationError
from secuority.models.interfaces import ChangeType


class TestSecurityToolsIntegrator:
    """Covers Bandit/Safety integration and helper behaviours."""

    def test_integrate_bandit_adds_default_config(self, tmp_path: Path) -> None:
        integrator = SecurityToolsIntegrator()

        change = integrator.integrate_bandit_config(tmp_path, existing_config={})
        assert change.change_type == ChangeType.CREATE
        config = tomllib.loads(change.new_content or "")
        bandit_cfg = config["tool"]["bandit"]
        assert bandit_cfg["exclude_dirs"] == ["tests", "test_*"]
        assert bandit_cfg["assert_used"]["skips"] == ["*_test.py", "test_*.py"]

    def test_integrate_bandit_merges_existing_config(self, tmp_path: Path) -> None:
        integrator = SecurityToolsIntegrator()
        pyproject_path = tmp_path / "pyproject.toml"
        pyproject_path.write_text("[tool.bandit]\nseverity = \"LOW\"\n", encoding="utf-8")
        existing = {"tool": {"bandit": {"skips": ["B900"]}}}

        change = integrator.integrate_bandit_config(tmp_path, existing_config=existing)

        assert change.change_type == ChangeType.UPDATE
        assert change.old_content == "[tool.bandit]\nseverity = \"LOW\"\n"
        config = tomllib.loads(change.new_content or "")
        assert config["tool"]["bandit"]["skips"] == ["B900"]
        assert "exclude_dirs" in config["tool"]["bandit"]

    def test_integrate_safety_creates_nested_structure(self, tmp_path: Path) -> None:
        integrator = SecurityToolsIntegrator()

        change = integrator.integrate_safety_config(tmp_path, existing_config={})

        config = tomllib.loads(change.new_content or "")
        safety_cfg = config["tool"]["secuority"]["safety"]
        assert safety_cfg["full_report"] is True
        assert safety_cfg["ignore"] == []

    def test_integrate_security_tools_updates_shared_config(self, tmp_path: Path) -> None:
        integrator = SecurityToolsIntegrator()
        changes = integrator.integrate_security_tools(tmp_path, ["bandit", "safety"])

        assert len(changes) == 2
        final_config = tomllib.loads(changes[-1].new_content or "")
        assert "bandit" in final_config["tool"]
        assert "safety" in final_config["tool"]["secuority"]

    def test_load_pyproject_config_without_tomllib_raises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        integrator = SecurityToolsIntegrator()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'demo'\n", encoding="utf-8")

        monkeypatch.setattr("secuority.core.security_tools.tomllib", None)

        with pytest.raises(ConfigurationError, match="TOML support not available"):
            integrator._load_pyproject_config(pyproject)

        monkeypatch.setattr("secuority.core.security_tools.tomllib", module_tomllib)

    def test_generate_toml_content_requires_tomli_w(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        integrator = SecurityToolsIntegrator()
        monkeypatch.setattr("secuority.core.security_tools.tomli_w", None)

        with pytest.raises(ConfigurationError, match="tomli_w not available"):
            integrator._generate_toml_content({"tool": {}})

        monkeypatch.setattr("secuority.core.security_tools.tomli_w", tomli_w)

    def test_check_security_tools_status_reads_config(self, tmp_path: Path) -> None:
        integrator = SecurityToolsIntegrator()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.bandit]\n"
            "[tool.secuority.safety]\nignore_vulns = []\n",
            encoding="utf-8",
        )

        status = integrator.check_security_tools_status(tmp_path)

        assert status == {"bandit": True, "safety": True}

    def test_get_security_recommendations_missing_everything(self, tmp_path: Path) -> None:
        integrator = SecurityToolsIntegrator()

        recs = integrator.get_security_recommendations(tmp_path)

        assert "Bandit" in recs[0]
        assert any("Safety" in rec for rec in recs)
        assert any("pre-commit" in rec for rec in recs)

    def test_get_security_recommendations_clear_when_configured(self, tmp_path: Path) -> None:
        integrator = SecurityToolsIntegrator()
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.bandit]\n"
            "[tool.secuority.safety]\nignore_vulns = []\n",
            encoding="utf-8",
        )
        (tmp_path / ".pre-commit-config.yaml").write_text("", encoding="utf-8")

        recs = integrator.get_security_recommendations(tmp_path)

        assert recs == []
