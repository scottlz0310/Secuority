# Secuority 多言語対応 実装ロードマップ

**最終更新**: 2025-12-02
**ステータス**: Phase 3 (Part 1) 完了

## 📊 進捗状況

| Phase | タイトル | ステータス | 完了日 |
|-------|---------|----------|--------|
| Phase 1 | 言語抽象化層の設計 | ✅ 完了 | 2025-12-02 |
| Phase 2 | Python実装のリファクタリング | ✅ 完了 | 2025-12-02 |
| Phase 3-1 | テンプレート構造の再編成 | ✅ 完了 | 2025-12-02 |
| Phase 3-2 | TemplateManager の更新 | 🔄 進行中 | - |
| Phase 4 | Node.js/Biome サポート追加 | 📋 計画中 | - |
| Phase 5 | CLI の単一リポジトリ実行最適化 | 📋 計画中 | - |
| Phase 6 | モダンツールテンプレート追加 | 📋 計画中 | - |

---

## ✅ 完了済みフェーズ

### Phase 1: 言語抽象化層の設計

**コミット**: `1c54d53`

**実装内容**:
- `LanguageAnalyzer` 抽象基底クラス
- `LanguageRegistry` (言語検出・管理システム)
- データ構造: `ToolRecommendation`, `ConfigFile`, `LanguageDetectionResult`

**ファイル**:
```
secuority/core/languages/
├── __init__.py
├── base.py
└── registry.py
```

**主要機能**:
- 言語検出（confidence スコア付き）
- 設定ファイルパターン定義
- ツール検出・推奨インターフェース
- 依存関係パースインターフェース

---

### Phase 2: Python実装のリファクタリング

**コミット**: `b654e64`

**実装内容**:
- `PythonAnalyzer` クラス（400+行）
- LanguageAnalyzer インターフェース完全実装
- グローバルレジストリへの自動登録

**ファイル**:
```
secuority/core/languages/
└── python.py
```

**機能**:
- Python言語検出（90%+ confidence）
- 設定ファイル検出（14種類）
- ツール検出（15種類: ruff, basedpyright, pytest, etc.）
- 推奨ツール（6種類、優先度付き）
- 依存関係パース（pyproject.toml + requirements.txt）

**検出基準**:
- `pyproject.toml`: +0.4 confidence
- `requirements.txt`: +0.3 confidence
- `setup.py`: +0.3 confidence
- `.py` files: +0.5 confidence
- `poetry.lock`/`Pipfile`: +0.2 confidence each

---

### Phase 3-1: テンプレート構造の再編成

**コミット**: `bce5a6a`

**実装内容**:
テンプレートを言語別ディレクトリに再編成

**新構造**:
```
secuority/templates/
├── common/              # 言語共通テンプレート
│   ├── .gitignore.template
│   ├── SECURITY.md.template
│   ├── CONTRIBUTING.md
│   └── .github/         # Issue/PR templates
└── python/              # Python固有テンプレート
    ├── pyproject.toml.template
    ├── .pre-commit-config.yaml.template
    ├── renovate.json
    └── workflows/       # Python CI/CD workflows
```

**変更点**:
- 19ファイル移動（git mv で履歴保持）
- 3つの新しい `__init__.py` 追加
- 明確な言語分離

---

## 🔄 次回作業: Phase 3-2

### Phase 3-2: TemplateManager の更新

**目標**: TemplateManagerを言語対応に更新

**現状の課題**:
- `TemplateManager` が固定的なテンプレートリストを使用
- 言語別ディレクトリを認識しない
- テンプレートパス解決が単一ディレクトリ前提

**実装タスク**:

#### 1. TemplateManager のリファクタリング

**ファイル**: `secuority/core/template_manager.py`

**変更内容**:

```python
class TemplateManager(TemplateManagerInterface):
    def load_templates(self, language: str = "python") -> dict[str, str]:
        """Load templates for specified language.

        Args:
            language: Language name (default: "python")

        Returns:
            Dictionary of template_name -> template_content
        """
        templates = {}

        # Load common templates
        common_path = self.get_template_directory() / "templates" / "common"
        templates.update(self._load_templates_from_dir(common_path))

        # Load language-specific templates
        lang_path = self.get_template_directory() / "templates" / language
        templates.update(self._load_templates_from_dir(lang_path))

        return templates

    def _load_templates_from_dir(self, path: Path) -> dict[str, str]:
        """Load all .template files from directory recursively."""
        # Implementation
        pass

    def get_available_languages(self) -> list[str]:
        """Get list of languages with available templates."""
        template_dir = self.get_template_directory() / "templates"
        languages = []
        for item in template_dir.iterdir():
            if item.is_dir() and item.name != "common":
                languages.append(item.name)
        return languages
```

**新規メソッド**:
- `load_templates(language: str)` - 言語別テンプレート読み込み
- `_load_templates_from_dir(path: Path)` - ディレクトリからテンプレート読み込み
- `get_available_languages()` - 利用可能な言語リスト取得

**後方互換性**:
- デフォルト言語を "python" にして既存コードが動作するようにする
- 既存の `load_templates()` 呼び出しは `load_templates("python")` と同等

#### 2. テンプレート検出ロジックの更新

**影響するファイル**:
- `secuority/core/template_manager.py`
- `secuority/core/applier.py` (テンプレート適用)

**変更内容**:
- テンプレートパス解決を言語対応に
- `common/` と `{language}/` の両方を検索
- テンプレート優先順位: 言語固有 > 共通

#### 3. テストの更新

**ファイル**:
- `tests/unit/core/test_template_manager.py`
- `tests/integration/test_security_features.py`

**更新内容**:
- 新しいテンプレート構造に対応したテスト
- 言語別テンプレート読み込みテスト
- common + python テンプレートの統合テスト

**推定作業時間**: 2-3時間

**想定される課題**:
1. 既存テストが新しいディレクトリ構造に対応していない
2. テンプレートパッケージングの更新が必要（pyproject.toml）
3. 初期化時のテンプレート配置ロジックの更新

---

## 📋 Phase 4: Node.js/Biome サポート追加

### 目標
Node.js プロジェクトの検出と Biome ツールチェーンのサポート

### 実装タスク

#### 4-1. NodeAnalyzer の実装

**新規ファイル**: `secuority/core/languages/nodejs.py`

**実装内容**:
```python
class NodeJSAnalyzer(LanguageAnalyzer):
    """Analyzer for Node.js projects."""

    def detect(self, project_path: Path) -> LanguageDetectionResult:
        # package.json, .js/.ts files, node_modules/
        pass

    def detect_tools(self, ...) -> dict[str, bool]:
        # Biome, ESLint, Prettier, TypeScript, Jest, etc.
        pass

    def get_recommended_tools(self) -> list[ToolRecommendation]:
        return [
            ToolRecommendation(
                tool_name="biome",
                category="quality",
                description="Fast formatter and linter (replaces ESLint + Prettier)",
                config_section="biome.json",
                priority=1,
                modern_alternative="eslint + prettier",
            ),
            ToolRecommendation(
                tool_name="typescript",
                category="quality",
                description="Static type checker for JavaScript",
                config_section="tsconfig.json",
                priority=1,
            ),
            # ... more tools
        ]
```

**検出基準**:
- `package.json`: +0.5 confidence
- `package-lock.json`/`yarn.lock`/`pnpm-lock.yaml`: +0.2 confidence each
- `.js`/`.ts` files: +0.4 confidence
- `node_modules/`: +0.1 confidence
- `tsconfig.json`: +0.2 confidence

**対応ツール**:
- **Quality**: Biome, ESLint, TypeScript, Prettier
- **Security**: npm audit, osv-scanner, Snyk
- **Testing**: Jest, Vitest, Playwright
- **Dependency**: npm, yarn, pnpm

#### 4-2. Node.js テンプレート作成

**新規ディレクトリ**: `secuority/templates/nodejs/`

**テンプレートファイル**:
```
nodejs/
├── package.json.template
├── biome.json.template
├── tsconfig.json.template
├── .eslintrc.json.template (legacy support)
└── workflows/
    ├── nodejs-ci.yml
    ├── nodejs-security.yml
    └── nodejs-quality.yml
```

**biome.json.template**:
```json
{
  "$schema": "https://biomejs.dev/schemas/1.9.4/schema.json",
  "organizeImports": {
    "enabled": true
  },
  "linter": {
    "enabled": true,
    "rules": {
      "recommended": true,
      "suspicious": {
        "noExplicitAny": "error"
      }
    }
  },
  "formatter": {
    "enabled": true,
    "indentStyle": "space",
    "lineWidth": 100
  }
}
```

#### 4-3. レジストリへの登録

**ファイル**: `secuority/core/languages/__init__.py`

```python
from .nodejs import NodeJSAnalyzer

# Auto-register analyzers
register_language(PythonAnalyzer(), priority=10)
register_language(NodeJSAnalyzer(), priority=20)
```

**推定作業時間**: 3-4時間

---

## 📋 Phase 5: CLI の単一リポジトリ実行最適化

### 目標
`uv tool install secuority` でグローバルインストールし、各リポジトリで実行する方式に最適化

### 現状の課題
- 横断的なリポジトリスキャンを想定した設計
- カレントディレクトリ実行が最適化されていない
- マルチリポジトリ対応が不明確

### 実装タスク

#### 5-1. CLI インターフェースの改善

**ファイル**: `secuority/cli/main.py`

**変更内容**:
```python
@app.command()
def check(
    path: Path = typer.Option(
        Path.cwd(),
        "--path", "-p",
        help="Project path to analyze (default: current directory)"
    ),
    languages: list[str] | None = typer.Option(
        None,
        "--language", "-l",
        help="Specific language(s) to analyze (auto-detect if not specified)"
    ),
    verbose: bool = False,
    structured: bool = False,
) -> None:
    """Analyze a project and show configuration status."""
    from secuority.core.languages import get_global_registry

    registry = get_global_registry()

    # Auto-detect or use specified languages
    if languages is None:
        detected = registry.detect_languages(path)
        languages = [d.language for d in detected]

    # Analyze each language
    for lang in languages:
        analyzer = registry.get_analyzer(lang)
        if analyzer:
            result = analyzer.analyze(path)
            # Display results
```

**新しいオプション**:
- `--language` / `-l`: 特定言語を指定（複数可）
- デフォルトはカレントディレクトリ
- マルチ言語プロジェクト対応

#### 5-2. インタラクティブ差分表示の強化

**ファイル**: `secuority/utils/diff.py`

**改善内容**:
- 変更前後の差分をカラー表示
- 個別ファイルごとの承認/拒否
- 一括適用オプション

**ユーザーフロー**:
```bash
$ secuority apply

🔍 Detected languages: Python, Node.js

📋 Proposed changes:

  Python:
    [1/3] .pre-commit-config.yaml
    [2/3] pyproject.toml
    [3/3] workflows/quality-check.yml

  Node.js:
    [1/2] biome.json
    [2/2] package.json

Apply all changes? [y/N/review]: review

--- .pre-commit-config.yaml (existing) ---
+++ .pre-commit-config.yaml (proposed) +++
@@ -1,5 +1,5 @@
-  - repo: https://github.com/psf/black
+  - repo: https://github.com/astral-sh/ruff-pre-commit

Apply this change? [y/n/q]: y
✅ Applied .pre-commit-config.yaml
```

#### 5-3. uv tool インストールの最適化

**ファイル**: `pyproject.toml`, `README.md`

**更新内容**:
- `uv tool install` の明確な説明
- グローバルコマンドとしての使用方法
- 各リポジトリでの実行例

**README.md 更新**:
```markdown
## Installation

### Recommended: uv tool (global installation)

```bash
uv tool install secuority
```

This installs secuority globally, making it available in any project.

### Usage

Navigate to your project directory and run:

```bash
cd /path/to/your/project
secuority check           # Analyze current project
secuority apply           # Apply recommended configurations
```

### Per-project installation

```bash
cd /path/to/your/project
uv add --dev secuority
uv run secuority check
```
```

**推定作業時間**: 2-3時間

---

## 📋 Phase 6: モダンツールテンプレート追加

### 目標
最新のツールチェーンテンプレートを追加・更新

### 実装タスク

#### 6-1. Python モダンツール更新

**更新ファイル**: `secuority/templates/python/`

**追加/更新内容**:
- `pyproject.toml.template`: basedpyright, uv セクション追加
- `.pre-commit-config.yaml.template`: osv-scanner 統合
- `workflows/security-check.yml`: osv-scanner, Semgrep 統合

**pyproject.toml モダン化**:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
    "pytest>=8.0",
    "ruff>=0.9.0",
    "basedpyright>=1.0.0",
]

[tool.ruff]
line-length = 120
target-version = "py313"
fix = true

[tool.ruff.lint]
select = ["ALL"]
ignore = ["D", "ANN"]

[tool.basedpyright]
typeCheckingMode = "strict"
pythonVersion = "3.13"
```

#### 6-2. Node.js モダンツール

**新規テンプレート**:
- `biome.json` (ESLint + Prettier の代替)
- `package.json` with modern scripts
- Workflows with Biome integration

#### 6-3. C++/C# サポート (オプション)

**C++ Analyzer** (簡易版):
```python
class CppAnalyzer(LanguageAnalyzer):
    def detect(self, project_path: Path):
        # CMakeLists.txt, .cpp/.h files
        pass

    def get_recommended_tools(self):
        return [
            ToolRecommendation(
                tool_name="clang-format",
                category="formatting",
                description="C++ code formatter",
                ...
            ),
            ToolRecommendation(
                tool_name="clang-tidy",
                category="quality",
                description="C++ linter",
                ...
            ),
        ]
```

**推定作業時間**: 3-4時間

---

## 🎯 優先順位と推奨実装順序

### 高優先度（必須）
1. ✅ Phase 1: 言語抽象化層
2. ✅ Phase 2: Python実装
3. ✅ Phase 3-1: テンプレート再編成
4. 🔄 **Phase 3-2: TemplateManager更新** ← 次回
5. Phase 4: Node.js/Biome サポート

### 中優先度
6. Phase 5: CLI最適化
7. Phase 6: モダンツール更新

### 低優先度（将来）
- C++/C# サポート
- Rust サポート
- Go サポート

---

## 🚧 想定される課題と対応策

### 1. 後方互換性の維持

**課題**:
- 既存のコードが新しい TemplateManager を呼び出せない
- テストが失敗する

**対応策**:
- デフォルト引数で後方互換性を保つ
- `load_templates()` → `load_templates(language="python")`
- 段階的な移行パスを提供

### 2. テンプレートパッケージング

**課題**:
- `pyproject.toml` の `[tool.hatch.build.targets.wheel.force-include]` が新構造に対応していない

**対応策**:
```toml
[tool.hatch.build.targets.wheel.force-include]
"secuority/templates/common" = "secuority/templates/common"
"secuority/templates/python" = "secuority/templates/python"
"secuority/templates/nodejs" = "secuority/templates/nodejs"
```

### 3. 既存テストの更新

**課題**:
- 519個のテストが新しいテンプレート構造を想定していない

**対応策**:
- テスト内でテンプレートパスを明示的に指定
- モックやフィクスチャの更新
- 段階的なテスト修正

### 4. ドキュメント更新

**課題**:
- README, usage.md が古い構造を参照

**対応策**:
- Phase 3-2 完了時に一括更新
- 新しい使用例を追加
- マルチ言語対応の説明

---

## 📝 次回セッションのチェックリスト

### Phase 3-2 開始前

- [ ] 現在のテストスイートを実行して基準を確認
- [ ] TemplateManager の既存実装を完全に理解
- [ ] 影響範囲を特定（grep で TemplateManager を検索）

### Phase 3-2 実装中

- [ ] `TemplateManager.load_templates(language)` 実装
- [ ] `_load_templates_from_dir()` ヘルパーメソッド実装
- [ ] `get_available_languages()` 実装
- [ ] pyproject.toml のパッケージング更新
- [ ] テストの修正

### Phase 3-2 完了時

- [ ] すべてのテストがパス（519個）
- [ ] ruff チェックがパス
- [ ] basedpyright チェックがパス
- [ ] ドキュメント更新
- [ ] コミット

---

## 🔗 関連ドキュメント

- [技術スタック更新計画](./secuority_upgrade_plan.md)
- [使用方法](../usage.md)
- [README](../README.md)
- [CONTRIBUTING](../templates/common/CONTRIBUTING.md)

---

## 📊 プロジェクト統計（2025-12-02時点）

- **総コミット数**: 5回（本日）
- **追加行数**: ~1,500行
- **新規ファイル**: 6個
- **変更ファイル**: ~40個
- **テストカバレッジ**: 79%
- **コード品質**: Ruff/basedpyright 準拠

---

**次回作業開始時**: この文書の「Phase 3-2」セクションから開始してください。
