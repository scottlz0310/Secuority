# Secuority 使用ガイド

Secuority は、Pythonプロジェクトのセキュリティと品質設定を自動化・標準化するCLIツールです。

## 📋 目次

- [インストール](#インストール)
- [基本的な使い方](#基本的な使い方)
- [コマンドリファレンス](#コマンドリファレンス)
- [設定ファイル](#設定ファイル)
- [テンプレート管理](#テンプレート管理)
- [実用例](#実用例)
- [トラブルシューティング](#トラブルシューティング)

## 📦 インストール

### 通常のプロジェクトでの使用

```bash
# uvを使用してGitHubから直接インストール（推奨）
uv add git+https://github.com/scottlz0310/Secuority.git

# pipを使用してGitHubから直接インストール
pip install git+https://github.com/scottlz0310/Secuority.git

# 特定のブランチやタグを指定
uv add git+https://github.com/scottlz0310/Secuority.git@main
uv add git+https://github.com/scottlz0310/Secuority.git@v1.0.0

# グローバルにインストール（システム全体で使用、pipxが必要）
pipx install git+https://github.com/scottlz0310/Secuority.git

# pipxがない場合は先にインストール
# pip install pipx
```

**注意**: インストール後は `secuority` コマンドが利用可能になります。プロジェクトの仮想環境内にインストールした場合は、その環境をアクティブにしてから使用してください。

### 開発・コントリビューション用

```bash
# リポジトリをクローンして開発環境をセットアップ
git clone https://github.com/scottlz0310/Secuority.git
cd Secuority
uv sync

# 開発モードで実行
uv run python -m secuority.cli.main --help

# テストの実行
uv run pytest
```

## 🚀 基本的な使い方

### 1. 初期設定

まず、Secuorityを初期化してテンプレートファイルをセットアップします：

```bash
# インストール済みの場合
secuority init

# 開発環境の場合
uv run python -m secuority.cli.main init
```

これにより、以下のディレクトリ構造が作成されます：

```
~/.config/secuority/          # Linux/macOS
%APPDATA%\secuority\          # Windows
├── templates/
│   ├── pyproject.toml.template
│   ├── .gitignore.template
│   ├── .pre-commit-config.yaml.template
│   └── workflows/
│       ├── security-check.yml
│       ├── quality-check.yml
│       ├── ci-cd.yml
│       └── dependency-update.yml
├── config.yaml
└── version.json
```

### 2. プロジェクト分析

現在のプロジェクトの設定状況を分析します：

```bash
# 基本分析（インストール済み）
secuority check

# 開発環境での実行
uv run python -m secuority.cli.main check

# 詳細情報付き
secuority check --verbose

# 特定のプロジェクトを分析
secuority check --project-path /path/to/project
```

### 3. 設定の適用

分析結果に基づいて推奨設定を適用します：

```bash
# 変更内容をプレビュー（実際には変更しない）
secuority apply --dry-run

# 開発環境での実行
uv run python -m secuority.cli.main apply --dry-run

# 対話的に設定を適用
secuority apply

# 確認なしで自動適用
secuority apply --force
```

## 📚 コマンドリファレンス

### `secuority check`

プロジェクトの設定状況を分析し、推奨事項を表示します。

```bash
secuority check [OPTIONS]
```

**オプション:**
- `--verbose, -v`: 詳細な分析情報を表示
- `--project-path, -p PATH`: 分析するプロジェクトのパス（デフォルト: カレントディレクトリ）
- `--structured`: 構造化されたJSONログを出力

**出力例:**
```
Secuority Analysis Report
Project: /home/user/my-project

                         Configuration Files                         
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ File                    ┃  Status   ┃ Notes                       ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ pyproject.toml          │ ✓ Found   │ Modern Python configuration │
│ requirements.txt        │ ✗ Missing │ Legacy dependency format    │
│ setup.py                │ ✗ Missing │ Legacy setup configuration  │
│ .gitignore              │ ✓ Found   │ Git ignore patterns         │
│ .pre-commit-config.yaml │ ✗ Missing │ Pre-commit hooks            │
└─────────────────────────┴───────────┴─────────────────────────────┘
```

### `secuority apply`

プロジェクトに設定変更を適用します。

```bash
secuority apply [OPTIONS]
```

**オプション:**
- `--dry-run, -n`: 変更内容をプレビューのみ（実際には適用しない）
- `--force, -f`: 確認なしで変更を適用
- `--project-path, -p PATH`: 対象プロジェクトのパス
- `--verbose, -v`: 詳細情報を表示
- `--structured`: 構造化されたJSONログを出力
- `--security-only`: セキュリティ関連の設定のみ適用
- `--templates-only`: テンプレートベースの設定のみ適用

**使用例:**
```bash
# 変更内容を事前確認
secuority apply --dry-run

# セキュリティ設定のみ適用
secuority apply --security-only

# 特定のプロジェクトに適用
secuority apply --project-path /path/to/project --force
```

### `secuority init`

Secuorityの設定ディレクトリとテンプレートファイルを初期化します。

```bash
secuority init [OPTIONS]
```

**オプション:**
- `--verbose, -v`: 詳細な初期化情報を表示
- `--structured`: 構造化されたJSONログを出力

### `secuority template`

テンプレートファイルを管理します。

#### `secuority template list`

利用可能なテンプレートを一覧表示します。

```bash
secuority template list [OPTIONS]
```

**オプション:**
- `--verbose, -v`: テンプレートの詳細情報を表示
- `--structured`: 構造化されたJSONログを出力

#### `secuority template update`

リモートソースからテンプレートを更新します。

```bash
secuority template update [OPTIONS]
```

**オプション:**
- `--verbose, -v`: 更新の詳細情報を表示
- `--structured`: 構造化されたJSONログを出力

## ⚙️ 設定ファイル

### config.yaml

ユーザー設定ファイル（`~/.config/secuority/config.yaml`）：

```yaml
version: '1.0'
templates:
  source: github:secuority/templates
  last_update: null
preferences:
  auto_backup: true
  confirm_changes: true
  github_integration: true
tool_preferences:
  ruff:
    line_length: 88
    target_version: py38
  mypy:
    strict: true
  bandit:
    skip_tests: true
```

### 環境変数

- `SECUORITY_TEMPLATES_DIR`: テンプレートディレクトリのカスタムパス
- `GITHUB_TOKEN`: GitHub API認証用トークン（GitHub統合機能用）

## 📄 テンプレート管理

### 利用可能なテンプレート

Secuorityには以下のテンプレートが含まれています：

1. **pyproject.toml.template**: モダンなPython設定
2. **.gitignore.template**: Python用の標準的な除外パターン
3. **.pre-commit-config.yaml.template**: pre-commitフック設定
4. **workflows/security-check.yml**: GitHub Actionsセキュリティワークフロー
5. **workflows/quality-check.yml**: GitHub Actions品質チェックワークフロー
6. **workflows/ci-cd.yml**: 基本的なCI/CDワークフロー
7. **workflows/dependency-update.yml**: 依存関係更新ワークフロー

### テンプレートのカスタマイズ

テンプレートファイルは直接編集できます：

```bash
# テンプレートディレクトリを開く
cd ~/.config/secuority/templates

# pyproject.tomlテンプレートを編集
nano pyproject.toml.template
```

### テンプレートの更新

```bash
# リモートから最新テンプレートを取得
secuority template update

# 更新履歴を確認
secuority template list --verbose
```

## 💡 実用例

### 新しいプロジェクトのセットアップ

```bash
# 新しいプロジェクトディレクトリを作成
mkdir my-new-project
cd my-new-project

# Secuorityで分析
secuority check

# 推奨設定を適用
secuority apply

# 結果を確認
secuority check --verbose
```

### 既存プロジェクトの現代化

```bash
# 既存プロジェクトに移動
cd /path/to/existing-project

# 現在の状況を分析
secuority check --verbose

# 変更内容をプレビュー
secuority apply --dry-run

# セキュリティ設定のみ適用
secuority apply --security-only

# 残りの設定を適用
secuority apply
```

### CI/CDパイプラインでの使用

```yaml
# .github/workflows/secuority-check.yml
name: Secuority Check
on: [push, pull_request]

jobs:
  security-audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Install Secuority
        run: uv add git+https://github.com/scottlz0310/Secuority.git
      - name: Run Secuority Check
        run: uv run secuority check --structured
```

### バッチ処理

```bash
# 複数プロジェクトの一括チェック
for project in /path/to/projects/*; do
  echo "Checking $project"
  secuority check --project-path "$project" --structured
done

# 複数プロジェクトの一括適用
for project in /path/to/projects/*; do
  echo "Applying to $project"
  secuority apply --project-path "$project" --force --security-only
done
```

## 🔧 トラブルシューティング

### よくある問題

#### 1. テンプレートが見つからない

```bash
# エラー: Templates directory not found
secuority init  # テンプレートを再初期化
```

#### 2. GitHub統合が動作しない

```bash
# GitHub トークンを設定
export GITHUB_TOKEN="your_token_here"
secuority check  # 再実行
```

#### 3. 設定の競合

```bash
# 競合がある場合は --force で非競合部分のみ適用
secuority apply --force

# または --dry-run で詳細を確認
secuority apply --dry-run --verbose
```

#### 4. カスタムテンプレートディレクトリ

```bash
# カスタムディレクトリを使用
export SECUORITY_TEMPLATES_DIR="/custom/path"
secuority init
```

### ログとデバッグ

```bash
# 詳細ログを有効化
secuority check --verbose

# 構造化ログでデバッグ
secuority check --structured

# 特定のプロジェクトパスでテスト
secuority check --project-path /path/to/test/project --verbose
```

### バックアップと復元

Secuorityは自動的にバックアップを作成します：

```bash
# バックアップファイルの場所
ls ~/.config/secuority/templates_backup_*

# 手動でバックアップを作成
cp -r ~/.config/secuority/templates ~/.config/secuority/templates_backup_manual
```

## 📞 サポート

- **Issues**: [GitHub Issues](https://github.com/scottlz0310/Secuority/issues)
- **Repository**: [GitHub Repository](https://github.com/scottlz0310/Secuority)
- **Documentation**: このREADME.mdとusage.md

---

**注意**: このツールはプロジェクトファイルを変更します。重要なプロジェクトでは事前に `--dry-run` オプションで変更内容を確認することを強く推奨します。