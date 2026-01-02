# Secuority

**Secuority** は、Python・Node.js・Rust・Go・C++・C#プロジェクトのコード品質とセキュリティ設定を自動化・標準化するCLIツールです。

## 📦 インストール

### 推奨: uv tool (グローバルインストール)

```bash
# GitHub Releasesから
uv tool install secuority --from "https://github.com/scottlz0310/Secuority/releases/download/v0.5.0/secuority-0.5.0-py3-none-any.whl"

# または、ソースから
git clone https://github.com/scottlz0310/Secuority.git
cd Secuority
uv tool install .
```

グローバルインストールすることで、どのプロジェクトディレクトリからでも `secuority` コマンドが使用できます。

### 代替: pipx

```bash
pipx install "https://github.com/scottlz0310/Secuority/releases/download/v0.5.0/secuority-0.5.0-py3-none-any.whl"
```

### プロジェクトごとにインストール

特定のプロジェクトに開発依存として追加する場合：

```bash
cd /path/to/your/project
uv add --dev secuority
uv run secuority check
```

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
* **Dependabot**: 自動依存関係更新の検出と推奨

## ⚙️ 実装計画

### 設定ファイル構造
```
~/.secuority/
├── templates/
│   ├── common/
│   │   └── base/
│   └── python/
│       └── base/
└── config.yaml  # ユーザー設定
```

### 処理フロー
1. **検出**: pyproject.toml, requirements.txt, 既存設定の解析
2. **評価**: 標準テンプレートとの差分計算
3. **提案**: 自動適用可能/手動対応必要な変更を分類
4. **適用**: ユーザー確認後に設定ファイルを更新

---

## 🚀 使用方法

プロジェクトディレクトリに移動してコマンドを実行：

```bash
cd /path/to/your/project
secuority check              # プロジェクトを分析
secuority apply              # 推奨設定を適用
```

### 主要コマンド

```bash
# プロジェクトを分析（カレントディレクトリ）
secuority check
secuority check --verbose                    # 詳細表示
secuority check --language python            # 特定言語のみ
secuority check --language python --language nodejs  # 複数言語

# 設定を自動適用（確認プロンプト付き）
secuority apply
secuority apply --dry-run                    # 変更をプレビュー
secuority apply --force                      # 確認なしで適用
secuority apply --language nodejs            # Node.js用テンプレートのみ

# 特定のパスを指定
secuority check --project-path /path/to/project
secuority apply --project-path /path/to/project

# テンプレート管理
secuority template list
secuority template update

# 設定初期化
secuority init
```

### 多言語対応

Secuorityは以下の言語を自動検出します：

- **Python**: pyproject.toml, requirements.txt, .py ファイルから検出
  - ツール: ruff, basedpyright, pytest, bandit, osv-scanner
- **Node.js**: package.json, .js/.ts ファイルから検出
  - ツール: biome, typescript, jest, npm audit, osv-scanner
- **Rust**: Cargo.toml, Cargo.lock, .rs ファイルから検出
  - ツール: clippy, rustfmt, cargo-audit, cargo-deny
- **Go**: go.mod, go.sum, .go ファイルから検出
  - ツール: golangci-lint, gofmt, govet, govulncheck, gosec
- **C++**: CMakeLists.txt, .cpp/.cc/.cxx ファイルから検出
  - ツール: clang-format, clang-tidy, cppcheck, cmake, vcpkg
- **C#**: .csproj, .sln, .cs ファイルから検出
  - ツール: dotnet-format, editorconfig, stylecop, dotnet analyzers

言語は自動検出されますが、`--language` オプションで明示的に指定することもできます。

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

* **追加言語対応**: Rust (Cargo.toml/Clippy), Go (go.mod/golangci-lint), C++ (CMakeLists.txt/clang-tidy) などへの対応を予定
* **高度なCI/CD統合**: より複雑なワークフローテンプレートの追加
* **プロジェクトテンプレート**: 新規プロジェクト作成時のスキャフォールディング

---

## 🗂 関連プロジェクト

* [sysup](https://github.com/scottlz0310/sysup) — パッケージ更新の自動化
* [setup-repo](https://github.com/scottlz0310/setup-repo) — リポジトリ管理・一括pull
* **secuority** — コード品質 & セキュリティポリシー適用

---
