# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- テンプレートディレクトリが未初期化でも `secuority apply` や `check` が自動的に内蔵テンプレートを展開するようにし、各言語でテンプレート適用が機能するよう改善。
- pip-auditをセキュリティ依存グループに追加（依存脆弱性スキャン）
- GitHub Actions ワークフローにpip-auditを統合
- Trivy導入（FS/secrets/config横断スキャン）

### Changed

- セキュリティツールのリストを更新: Semgrepを削除し、pip-audit、Trivyを追加
- analyzer.pyとgithub_integration.pyのセキュリティワークフロー検出キーワードを更新

### Fixed

- RuffのIルールが有効なだけの場合でもisortが「構成済み」と誤表示されないようにし、`secuority check`のQuality Tools表では「Ruffでカバー済み」と表示されるよう改善。
- Code QualityワークフローのDependency Reviewを許可リスト方式から拒否リスト方式に変更し、依存更新PRでのライセンス誤検知によるCI失敗を抑制。

### Removed

- Renovateの統合機能とテンプレートを削除し、依存関係更新は外部のrenovate-configへ移管。
- Semgrepを依存関係から削除（LGPL-2.1ライセンス問題および間接依存による運用コスト増加のため）
- renovate.jsonからSemgrep関連のpackageRulesを削除

## [0.5.0] - 2025-11-03

### Added

- **RenovateIntegrator**: Complete Renovate configuration integration for automated dependency updates
  - Generate renovate.json with customizable settings (timezone, assignees, reviewers, automerge)
  - Support for pre-commit hooks, Python dependencies (pep621), and GitHub Actions
  - Automatic detection of existing Renovate configurations with merge support
  - Migration detection from Dependabot to Renovate
  - Status checking for renovate.json and renovate.json5 files

- **Comprehensive Unit Tests**: 26 new tests for RenovateIntegrator with 94% coverage

- **Renovate Template**: Django-style template for renovate.json generation

- **Deprecated File Detection**: Automatic detection of Dependabot-related files for migration
  - dependabot.yml/yaml detection
  - Dependabot automerge workflow detection (multiple filename patterns)
  - Migration recommendations

### Changed

- **GitHub Integration**: Updated to support both Renovate and Dependabot detection
  - Renamed `_analyze_dependabot()` to `_analyze_dependency_management()`
  - Added dual detection with migration recommendations
  - `get_renovate_config()` method in GitHubClient

- **ConfigurationApplier**: Added Renovate integration methods
  - `apply_renovate_integration()` for applying Renovate config
  - `get_renovate_integration_changes()` for preview without applying

- **WorkflowIntegrator**: Removed deprecated dependency workflow generation
  - Default workflows changed from ['security', 'quality', 'cicd', 'dependency'] to ['security', 'quality', 'cicd']
  - Added `detect_deprecated_dependency_files()` method

- **Documentation**: Updated all references from Dependabot to Renovate
  - README.md: Phase 3 CI/CD section
  - SECURITY.md: Automated dependency updates section
  - implementation-decisions.md: Added section 2.1 for Renovate migration
  - Template SECURITY.md: Updated CI/CD security section

### Removed

- **Dependabot Templates**: Removed deprecated Dependabot configuration files
  - `.github/dependabot.yml` template
  - `workflows/dependency-update.yml` template

- **isort Hook**: Removed redundant isort from pre-commit template (Ruff handles import sorting)

### Fixed

- **Mypy Configuration**: Removed deprecated `check_untyped_defs` setting from pyproject.toml template

- **Type Annotations**: Fixed dict type annotations in RenovateIntegrator and tests (dict → dict[str, Any])

- **Test Suite**: Updated tests for renamed methods and removed deprecated workflow generation
  - Fixed `test_analyze_dependabot_*` → `test_analyze_dependency_management_*`
  - Fixed `test_integrated_security_and_workflow_setup` to specify workflows explicitly

### Improved

- **Test Coverage**: Overall project coverage increased from 77% to 79%

- **Code Quality**: All 519 tests passing (493 original + 26 new)

- **Pre-commit Configuration**: Excluded template JSON files from check-json hook to allow Django-style variables

### Migration Guide

For projects using Dependabot:

1. Run `secuority apply` to generate renovate.json configuration
2. Review and remove old Dependabot files:
   - `.github/dependabot.yml`
   - `.github/workflows/dependabot-automerge.yml`
   - `.github/workflows/dependency-update.yml`
3. Commit the new renovate.json and push to enable Renovate

## [0.1.0] - Initial Release

### Features

- Initial project structure
- Basic security tools integration
- Pre-commit hooks configuration
- GitHub Actions workflow templates
- Template management system
- CLI interface with typer

[0.5.0]: https://github.com/scottlz0310/Secuority/releases/tag/v0.5.0
[0.1.0]: https://github.com/scottlz0310/Secuority/releases/tag/v0.1.0
