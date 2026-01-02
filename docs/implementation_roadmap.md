# Secuority 多言語対応 実装ロードマップ

**最終更新**: 2025-12-03
**ステータス**: Phase 7 完了

## 📊 進捗状況

| Phase | タイトル | ステータス | 完了日 |
|-------|---------|----------|--------|
| Phase 1 | 言語抽象化層の設計 | ✅ 完了 | 2025-12-02 |
| Phase 2 | Python実装のリファクタリング | ✅ 完了 | 2025-12-02 |
| Phase 3-1 | テンプレート構造の再編成 | ✅ 完了 | 2025-12-02 |
| Phase 3-2 | TemplateManager の更新 | ✅ 完了 | 2025-12-03 |
| Phase 4 | Node.js/Biome サポート追加 | ✅ 完了 | 2025-12-03 |
| Phase 5 | CLI の単一リポジトリ実行最適化 | ✅ 完了 | 2025-12-03 |
| Phase 6 | モダンツールテンプレート追加 | ✅ 完了 | 2025-12-03 |
| Phase 7 | Rust・Go言語サポート追加 | ✅ 完了 | 2025-12-03 |

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
│   └── base/
│       ├── .gitignore.template
│       ├── SECURITY.md.template
│       ├── CONTRIBUTING.md
│       └── .github/         # Issue/PR templates
└── python/              # Python固有テンプレート
    └── base/
        ├── pyproject.toml.template
        ├── .pre-commit-config.yaml.template
        └── workflows/       # Python CI/CD workflows
```

**変更点**:
- 19ファイル移動（git mv で履歴保持）
- 3つの新しい `__init__.py` 追加
- 明確な言語分離

---

### Phase 3-2: TemplateManager の更新

**コミット**: `fd03838`

**ステータス**: ✅ 完了 (2025-12-03)

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

---

### Phase 4: Node.js/Biome サポート追加

**コミット**: `9a5c3bd`

**ステータス**: ✅ 完了 (2025-12-03)

**実装内容**:
- `NodeJSAnalyzer` クラス実装
- Node.js用テンプレート作成（biome.json, tsconfig.json等）
- GitHub Actions workflows（nodejs-ci.yml, nodejs-quality.yml, nodejs-security.yml）
- グローバルレジストリへの登録

**ファイル**:
```
secuority/core/languages/nodejs.py
secuority/templates/nodejs/
├── biome.json.template
├── tsconfig.json.template
└── workflows/
    ├── nodejs-ci.yml
    ├── nodejs-quality.yml
    └── nodejs-security.yml
```

**機能**:
- Node.js言語検出
- 設定ファイル検出（12種類）
- ツール検出（13種類: Biome, ESLint, TypeScript等）
- 推奨ツール（優先度付き）
- 依存関係パース（package.json）

---

---

### Phase 5: CLI の単一リポジトリ実行最適化

**コミット**: (次のコミットで完了予定)

**ステータス**: ✅ 完了 (2025-12-03)

**実装内容**:
- `check`コマンドに`--language`オプション追加
- `apply`コマンドに`--language`オプション追加
- 言語自動検出機能の統合
- マルチ言語プロジェクト対応
- README.mdの更新（uv toolインストール方法の明記）

**変更ファイル**:
```
secuority/cli/main.py
README.md
```

**機能**:
- カレントディレクトリでの実行最適化
- 言語自動検出（confidence > 0.3）
- 複数言語の同時サポート
- 言語別テンプレートの自動ロード
- グローバルインストール推奨の明確化

**使用例**:
```bash
# カレントディレクトリを分析
cd /path/to/project
secuority check

# 特定言語を指定
secuority check --language python
secuority check --language nodejs

# 設定を適用
secuority apply
secuority apply --language nodejs
```

---

---

### Phase 6: モダンツールテンプレート追加

**コミット**: (次のコミットで完了予定)

**ステータス**: ✅ 完了 (2025-12-03)

**実装内容**:
- pyproject.toml.template: hatchling、basedpyright、dependency-groups 追加
- .pre-commit-config.yaml.template: basedpyright、osv-scanner統合
- workflows/security-check.yml: osv-scanner統合とPRコメント追加

**更新ファイル**:
```
secuority/templates/python/base/pyproject.toml.template
secuority/templates/python/base/.pre-commit-config.yaml.template
secuority/templates/python/base/workflows/security-check.yml
```

**主要な変更**:

#### pyproject.toml.template
- build-system: setuptools → hatchling
- dev-dependencies: mypy → basedpyright
- 追加: [tool.uv] セクション
- 追加: [tool.basedpyright] 設定（typeCheckingMode: standard）
- 更新: ruff設定（fix=true、新しいルール追加）

#### .pre-commit-config.yaml.template
- mypy → basedpyright に置き換え
- osv-scanner追加（uv.lockスキャン）
- CI skip設定追加（osv-scanner）

#### workflows/security-check.yml
- osv-scannerステップ追加
- osv-report.jsonアーティファクト追加
- PRコメントにosv-scanner結果を表示

**テスト結果**:
- ✅ 全519テスト合格
- ✅ コードカバレッジ 76% (+4%)
- ✅ 後方互換性維持

---

## 🎯 次のステップと今後の展開

### 実装完了サマリー

Phase 6まで完了し、Secuorityは以下の機能を持つ完全な多言語対応ツールになりました：

**言語サポート**:
- ✅ Python（ruff, basedpyright, pytest, bandit, osv-scanner）
- ✅ Node.js（biome, typescript, jest, npm audit, osv-scanner）
- ✅ Rust（clippy, rustfmt, cargo-audit, cargo-deny）
- ✅ Go（golangci-lint, gofmt, govet, govulncheck, gosec）

**主要機能**:
- ✅ 言語自動検出
- ✅ マルチ言語プロジェクト対応
- ✅ モダンツールチェーン（hatchling, basedpyright, osv-scanner）
- ✅ GitHub Actions統合
- ✅ pre-commit hooks統合

---

### Phase 7: Rust・Go言語サポート追加

**コミット**: (次のコミットで完了予定)

**ステータス**: ✅ 完了 (2025-12-03)

**実装内容**:

#### Rust サポート
- **RustAnalyzer**: Cargo.toml、.rsファイルの検出
- **テンプレート**:
  - Cargo.toml.template: モダンなRust設定
  - rustfmt.toml: フォーマット設定
  - deny.toml: cargo-deny設定
  - workflows/rust-ci.yml: テスト・clippy・rustfmt
  - workflows/rust-security.yml: cargo-audit・cargo-deny

#### Go サポート
- **GoAnalyzer**: go.mod、.goファイルの検出
- **テンプレート**:
  - .golangci.yml: golangci-lint設定
  - workflows/go-ci.yml: ビルド・テスト・lint・fmt
  - workflows/go-security.yml: govulncheck・gosec

**新規ファイル**:
```
secuority/core/languages/rust.py
secuority/core/languages/go.py
secuority/templates/rust/
├── Cargo.toml.template
├── rustfmt.toml
├── deny.toml
└── workflows/
    ├── rust-ci.yml
    └── rust-security.yml
secuority/templates/go/
├── .golangci.yml
└── workflows/
    ├── go-ci.yml
    └── go-security.yml
```

**テスト結果**:
- ✅ 全519テスト合格
- ✅ 抽象メソッド実装完了
- ✅ 言語レジストリ統合完了

---

### ✅ Phase 8: C++/C# サポート【完了: 2025-12-03】

**目的**: エンタープライズ向け主要言語のサポート拡大

#### C++ サポート
- **CppAnalyzer**: CMakeLists.txt、.cpp/.cc/.cxxファイルの検出
- **テンプレート**:
  - .clang-format: Google スタイルベース、100文字制限
  - .clang-tidy: clang-analyzer、cppcoreguidelines、modernize
  - CMakeLists.txt.template: C++20、コンパイルコマンドエクスポート
  - workflows/cpp-ci.yml: マルチOS（Ubuntu/Windows/macOS）、Debug/Release
  - workflows/cpp-security.yml: cppcheck、osv-scanner

#### C# サポート
- **CSharpAnalyzer**: .csproj、.sln、.csファイルの検出
- **テンプレート**:
  - .editorconfig: 命名規則、コーディングスタイル設定
  - Directory.Build.props: StyleCop、Roslyn Analyzers統合
  - workflows/csharp-ci.yml: .NET 8.0/9.0マトリックス、コードカバレッジ
  - workflows/csharp-security.yml: CodeQL、osv-scanner

**新規ファイル**:
```
secuority/core/languages/cpp.py
secuority/core/languages/csharp.py
secuority/templates/cpp/
├── .clang-format
├── .clang-tidy
├── CMakeLists.txt.template
└── workflows/
    ├── cpp-ci.yml
    └── cpp-security.yml
secuority/templates/csharp/
├── .editorconfig
├── Directory.Build.props
└── workflows/
    ├── csharp-ci.yml
    └── csharp-security.yml
```

**レジストリ登録**:
```python
register_language(CppAnalyzer(), priority=30)
register_language(CSharpAnalyzer(), priority=30)
```

**テスト結果**:
- ✅ 全519テスト合格
- ✅ C++ vcpkg.json、conanfile.txt依存解析対応
- ✅ C# .csproj XML解析によるPackageReference抽出
- ✅ 言語検出confidence計算正常動作

**サポート対象ツール**:
- **C++**: clang-format、clang-tidy、cppcheck、cmake、vcpkg
- **C#**: dotnet-format、editorconfig、stylecop、dotnet analyzers

---

### 将来の拡張案

#### Phase 9 (オプション): 追加言語サポート
- Java（Maven/Gradle + SpotBugs）
- Kotlin（kotlinc + detekt）
- Swift（SwiftLint + SwiftFormat）

#### Phase 10 (オプション): 高度な機能
- プロジェクトテンプレート機能
- インタラクティブ設定ウィザード
- CI/CD統合の拡張

---

## 📋 実装タスク（参考）

#### 6-1. Python モダンツール更新

**更新ファイル**: `secuority/templates/python/base/`

**追加/更新内容**:
- `pyproject.toml.template`: basedpyright, dependency-groups 追加
- `.pre-commit-config.yaml.template`: osv-scanner 統合
- `workflows/security-check.yml`: osv-scanner, Semgrep 統合

**pyproject.toml モダン化**:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
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

### 中優先度（完了）
6. ✅ Phase 5: CLI最適化
7. ✅ Phase 6: モダンツール更新
8. ✅ Phase 7: Rust/Goサポート
9. ✅ Phase 8: C++/C#サポート

### 低優先度（将来）
- Java/Kotlin サポート
- Swift サポート
- インタラクティブ設定ウィザード

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
