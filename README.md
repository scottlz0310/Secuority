# Secuority

**Secuority** は、Pythonプロジェクトのコード品質とセキュリティ設定を自動化・標準化するCLIツールです。

## 🎯 解決する問題

* **設定の分散**: プロジェクトごとに異なるlint/security設定
* **古い慣習**: requirements.txt依存、セキュリティツール未導入
* **手動作業**: 毎回同じ設定を手動で追加する非効率性

## 🎯 目標

* pyproject.toml中心の現代的な設定への移行
* セキュリティベストプラクティスの自動適用
* 設定漏れの検出と修正提案

---

## 📦 機能（優先度順）

### Phase 1: 基本設定
* **依存関係管理**: requirements.txt → pyproject.toml移行支援、extras → dependency-groups移行、uv プロジェクト設定の検出と同期
* **Lint設定**: Ruff/Mypy/Black の標準設定を pyproject.toml に統合
* **.gitignore**: Python標準テンプレートとの差分検出・追加

### Phase 2: セキュリティ
* **セキュリティツール**: Bandit/Safety の設定追加
* **機密漏洩防止**: pre-commit hooks (gitleaks) + CI検証 + GitHub Push Protection の3段構え

### Phase 3: CI/CD
* **GitHub Actions**: 品質・セキュリティワークフローの存在確認
* **Dependabot**: 推奨設定との比較・修正提案

## ⚙️ 実装計画

### 設定ファイル構造
```
~/.secuority/
├── templates/
│   ├── pyproject.toml.template
│   ├── .gitignore.template
│   └── .pre-commit-config.yaml.template
└── config.yaml  # ユーザー設定
```

### 処理フロー
1. **検出**: pyproject.toml, requirements.txt, 既存設定の解析
2. **評価**: 標準テンプレートとの差分計算
3. **提案**: 自動適用可能/手動対応必要な変更を分類
4. **適用**: ユーザー確認後に設定ファイルを更新

---

## 🚀 CLIコマンド

```bash
# 現在のプロジェクトを分析
secuority check [--verbose]

# 設定を自動適用（確認プロンプト付き）
secuority apply [--dry-run] [--force]

# テンプレート管理
secuority template list
secuority template update

# 設定初期化
secuority init
```

## ✅ 重要機能チェックリスト

**依存関係の現代化**
- [ ] requirements.txt → pyproject.toml 移行警告
- [ ] extras → dependency-groups 移行（PEP 735対応）
- [ ] uv による依存管理設定の検出と同期
- [ ] setup.py → pyproject.toml 移行提案

**セキュリティ必須項目**
- [ ] .env ファイルの .gitignore 追加確認
- [ ] pre-commit hooks (gitleaks) 設定
- [ ] CI での機密情報検証ワークフロー
- [ ] GitHub Push Protection 有効化確認
- [ ] Bandit/Safety の pyproject.toml 統合

## 📋 実装マイルストーン

- [ ] **v0.1**: pyproject.toml解析・基本lint設定・extras検出
- [ ] **v0.2**: .gitignore管理・requirements.txt検出
- [ ] **v0.3**: セキュリティツール統合
- [ ] **v0.4**: GitHub Actions/Dependabot検証
- [ ] **v1.0**: 安定版リリース

## 🔮 将来の拡張

* **多言語対応**: Node.js (package.json/ESLint), Rust (Cargo.toml/Clippy), Go (go.mod/golangci-lint) などへの対応を予定

---

## 🗂 関連プロジェクト

* [sysup](https://github.com/scottlz0310/sysup) — パッケージ更新の自動化
* [setup-repo](https://github.com/scottlz0310/setup-repo) — リポジトリ管理・一括pull
* **secuority** — コード品質 & セキュリティポリシー適用

---
