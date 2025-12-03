# Repository Guidelines

## 言語ルール
- AIは日本語で応答してください。

## プロジェクト構成とモジュール整理
- `secuority/`: コアPythonパッケージ。CLIは `secuority/cli`、オーケストレーションは `secuority/core`、共通ヘルパーは `utils`、テンプレートは `templates`。
- `tests/`: Pytestスイート。`test_*.py`命名でパッケージ構成を反映。
- `docs/`: Sphinxソース。生成物は `docs/_build` に出力。
- `dist/` と `htmlcov/`: ビルド成果物（wheel、カバレッジ）。手動変更はコミットしない。

## ビルド・テスト・開発コマンド
- 開発依存導入: `uv sync --group dev`（テスト・lint・型チェックを追加）。
- ユニットテスト+カバレッジ: `uv run pytest`（HTMLは `htmlcov/index.html`）。
- Lint/フォーマット: `uv run ruff check .` と `uv run ruff format .`（行長120、ダブルクォート）。
- 型チェック: `uv run basedpyright`（strict、Python 3.13ターゲット）。
- pre-commit全実行: `uv run pre-commit run --all-files` をプッシュ前に。
- リリース用ビルド: `uv build`（成果物は `dist/`）。

## コーディングスタイルと命名
- Python 3.13+、4スペース。明示的importとpathlib優先（ruff `PTH`）。
- 関数・変数は`snake_case`、クラスは`PascalCase`、CLIコマンドはkebab-case（Typer）。
- ライブラリコードでの`print`禁止（ruff `T20`）；`rich`のロギングを利用。
- `templates/`のテンプレートは冪等で最小限の主張に保ち、変更時は対応テストも更新。

## テスト指針
- 新機能にはpytestカバレッジ必須。関連モジュール横に`test_*`ファイルと`Test*`クラスを追加。
- パラメータ化とフィクスチャを優先。外部呼び出しはモックで隔離。
- `uv run pytest`後に`htmlcov/index.html`を確認し、カバレッジ低下を避ける。

## コミットとPRガイドライン
- Conventional Commitsを遵守: `feat(scope): ...` `fix(scope): ...`。scopeはディレクトリ名（例: `core`/`cli`/`templates`）。
- PRでは変更要約、実行した検証コマンド、関連Issueを記載。CLI UX変更時はbefore/afterの出力を添付。
- lint・型チェック・テスト・pre-commitを通過させてからレビュー依頼。

## セキュリティと設定のヒント
- 秘密情報やトークンはコミットしない。ローカル検証は環境変数で管理。
- セキュリティテンプレートやスキャナ変更時は期待値を固定するテストも更新し、挙動変更は`CHANGELOG.md`に追記。
- 依存更新時のみ`uv lock`でロック再生成し、主要アップグレードはPR説明に明記。
