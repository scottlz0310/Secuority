# コード品質改善プラン（2025-12-05）

最新の診断コマンドを `uv run ruff check --exit-zero --statistics`、`uv run basedpyright --outputjson`、`uv run pre-commit run bandit --all-files` で採取し、結果を以下に整理する。

## 現状棚卸し

### Ruff（lint）
| ルール | 件数 | 主な発生ファイル | 典型的な課題 |
| --- | --- | --- | --- |
| PLC0415 | 34 | `tests/integration/test_security_features.py:101` 他 | 関数内インポート。遅延 import 依存が多く、可読性とmodule初期化時の副作用が曖昧。 |
| S110 | 11 | `secuority/core/languages/python.py:209` 他 | `try/except/pass` により失敗が握りつぶされ、上位ハンドラ・ログなし。 |
| PLR0912 | 10 | `secuority/cli/main.py:47` 他 | 分岐過多の関数。Typerコマンドなどでロジック集約されすぎ。 |
| ARG002 | 8 | `secuority/core/languages/csharp.py:165` 他 | 使われない引数（将来の拡張用placeholder）が警告に。 |
| PLW2901 | 5 | `secuority/core/languages/go.py:263` 他 | ループ変数の再代入。 |
| PLR0911 | 4 | `secuority/core/languages/python.py:123` 他 | return過多。 |
| PTH123 | 4 | `secuority/core/template_manager.py:613` 他 | `open()` 直接利用。pathlib推奨と乖離。 |
| PLR0915 | 3 | `secuority/cli/main.py:47` 他 | 文が長すぎる関数。 |

**重点ファイル（PLC0415）**: `secuority/core/workflow_integrator.py:32`, `tests/integration/test_security_features.py:101`, `tests/unit/utils/test_logger.py:64` など34箇所。
**重点ファイル（S110）**: `secuority/core/languages/{cpp,csharp,go,nodejs,python,rust}.py` の例外処理部位（11箇所）。

### Basedpyright（型チェック）
2025-12-05に `uv run basedpyright --outputjson` を再取得（46ファイル／1,237 error）。CLI/統合テスト系が Unknown Type を大量に抱えており、言語アナライザ群は20件前後まで縮小した。

| 件数 | ファイル |
| ---: | --- |
| 233 | `secuority/cli/main.py` |
| 175 | `tests/integration/test_end_to_end.py` |
| 168 | `secuority/utils/user_interface.py` |
| 114 | `tests/integration/test_cli_commands.py` |
| 47 | `secuority/utils/github_error_handler.py` |
| 45 | `secuority/core/analyzer.py` |
| 37 | `secuority/core/github_integration.py` |
| 36 | `tests/unit/core/test_precommit_integrator.py` |
| 26 | `secuority/core/security_tools.py` |
| 25 | `secuority/core/languages/rust.py` |

#### 主なルール種別

| ルール | 件数 | 主原因 |
| --- | ---: | --- |
| `reportUnknownMemberType` | 855 | `dict[str, Any]`に依存する設定/GitHubレスポンスを `.get()` 連鎖で扱っている |
| `reportUnknownVariableType` | 176 | `yaml.safe_load` や `tomllib.load` の戻り値を未注釈のまま保持 |
| `reportUnknownParameterType` | 59 | pytest モック関数（`fail_replace` など）に型ヒントが無い |
| `reportMissingImports` | 36 | `typer`/`rich` など dev 環境外モジュールの型取得に失敗 |
| `reportUnknownArgumentType` | 35 | Integrator/ユーティリティに `dict` や `MagicMock` をそのまま渡している |
| `reportArgumentType` | 16 | GitHubクライアントのモックが `Request` プロトコルに適合していない |
| `reportOptionalMemberAccess` | 13 | APIレスポンスを Optional のまま属性アクセス |
| `reportCallIssue` | 12 | `safe_github_call` のフォールバック戻り値が `bool | dict` など多態になっている |

#### ボトルネック観察
- CLI/統合テスト群（`secuority/cli/main.py` 233件、`tests/integration/test_end_to_end.py` 175件、`secuority/utils/user_interface.py` 168件、`tests/integration/test_cli_commands.py` 114件）: `rich`/Typer から返す辞書や `ConsoleRenderable` を `dict[str, Any]` のまま積み上げた結果、`reportUnknownMemberType`/`reportUnknownVariableType` が雪だるま状態。CLI応答を `CommandAnalysisResult` 的な TypedDict で固定し、ユーザーインターフェース層も `Protocol` 経由でインタラクションを限定する必要がある。
- Config適用スタック（`secuority/core/analyzer.py` 45件、`secuority/core/security_tools.py` 26件、`secuority/core/template_manager.py` 11件、`secuority/core/applier.py` 8件）: `ConfigurationMerger` や `_check_security_tools` が `dict[str, Any]` を返し、`DiffGenerator` 経由で `ConfigChange` に注入されるため Unknown 系が集中。Config/Change Payload 用の `TypedDict` 群と `Protocol` で `FileOperations`/`UserApprovalInterface` の契約を定義する。
- GitHubスタック（`secuority/core/github_integration.py` 37件、`tests/unit/core/test_github_client.py` 8件）: `safe_github_call` の戻り値が `dict | list | bool` の混在、`MagicMock` が `HTTPResponse` を再現せず `reportArgumentType`/`reportCallIssue` が多数。`GitHubApiStatus`, `WorkflowSummary`, `DependabotConfig` の TypedDict と `SupportsURLLibRequest` プロトコルを用意し、テスト側は `typing.cast` と専用フィクスチャで吸収する。
- 言語アナライザ群（`languages/rust.py` 25件、`python.py` 22件、`nodejs.py` 21件、`cpp.py` 19件、`csharp.py` 15件、`go.py` 12件）: `ToolStatusMap` エイリアスを導入して `detect_tools`/`parse_dependencies` のシグネチャを揃えた結果、`reportIncompatibleMethodOverride` は0件になったが、返却値の `dict[str, bool]` をそのまま `.get()` している箇所が Unknown のまま。`ToolStatusMap`/`ToolRecommendation` を `Protocol` 化し、呼び出し側に `TypedDict` を伝播させる。
- テストフィクスチャ（`tests/unit/core/test_precommit_integrator.py` 36件ほか）: 擬似的な辞書フィクスチャ・モック関数の未注釈と `_logger_instance` 直接操作により `reportUnknownParameterType`/`reportAttributeAccessIssue` が残っている。TypedDict フィクスチャと `get_logger()` 経由のアクセスに切り替える。

### Bandit（セキュリティ）
`uv run pre-commit run bandit --all-files` で Medium 1件（`xml.etree.ElementTree.parse` 利用、`secuority/core/languages/csharp.py:294`）と Low 12件（`B110 try/except/pass`、複数言語アナライザ）を検出。
→ 既に `# noqa` コメントはあるが、`defusedxml` 採用や例外ログ化・粒度の細かい例外種別が推奨。

## 段階的アプローチ

### フェーズ1: 低リスク是正（1〜2日）
- **対象**: PLC0415, PTH123, ARG002, PLW2901 のような表層lint違反。
- **タスク**:
  - 依存解決が不要なインポートをモジュール先頭へ移動（`tests/integration/test_security_features.py`, `secuority/core/workflow_integrator.py` 等）。
  - `open()` を `Path.read_text()` 等に移行（`secuority/core/template_manager.py:613`）。
  - 未使用引数を削除 or `*_unused` へリネーム + `# noqa` 最小化。
- **完了条件**: `uv run ruff check --select PLC0415,S110,ARG002,PLW2901,PTH123 --exit-zero` で0件。

### フェーズ2: 構造リファクタリング（3〜5日）
- **対象**: PLR0912/PLR0915/PLR0911 高複雑度のコアモジュール（`secuority/cli/main.py:47`, `secuority/core/precommit_integrator.py:336`, `secuority/models/project.py:42` 等）。
- **タスク**:
  - CLIコマンドを Typer サブコマンドや小関数へ分割。
  - `precommit_integrator` のブランチを戦略パターン化（各フック処理を dataclass に分離）。
  - 大量 return を含む関数をベースクラス/ヘルパー化。
- **完了条件**: `uv run ruff check --select PLR0912,PLR0915,PLR0911 --exit-zero` で0件。主要関数が 50行/12分岐の社内基準内。

### フェーズ3: 型定義と契約明確化（5〜7日）
- **対象**: `secuority/core/applier.py`, `secuority/core/analyzer.py`, `secuority/utils/diff.py`, `tests/integration/test_security_features.py` 等 Basedpyright 上位10ファイル。
- **タスク**:
  - Config/Payload用の `TypedDict` / `Protocol` / dataclass を導入し dict/list 連鎖を明文化。
  - テストフィクスチャの型指定（`tests/integration/...`）と helper を共通化。
  - `reportUnknownMemberType` の主因である `.get()` 連鎖を専用オブジェクトに移行。
- **完了条件**: `uv run basedpyright` が error 0。型補助のためのユーティリティ（`secuority/types.py` 等）を追加。

### フェーズ4: セキュリティ強化（2日）
- **対象**: Bandit指摘とRuff S110重複箇所。
- **タスク**:
  - `xml.etree.ElementTree` を `defusedxml.ElementTree` に置換し、入力ファイルの信頼境界を明記。
  - 例外握りつぶしポイントで `rich` logger / `contextlib.suppress` への置換、catch対象を限定。
- **完了条件**: `uv run pre-commit run bandit --all-files` が成功。S110 0件。

## 成功指標と追跡
1. `uv run pre-commit run --all-files` がノーエラーで完走。
2. `htmlcov/index.html` で既存カバレッジ（現在値はCIログ参照）を維持。
3. `docs/CHANGELOG.md` に各フェーズの要約と影響範囲を追記。

フェーズ完了ごとにこの文書へ状況を追記し、残タスクとブロッカーを明記する。

## 進捗ログ
- 2025-12-04: フェーズ1（Lint）完了。`uv run ruff check --select PLC0415,S110,ARG002,PLW2901,PTH123` が0件になり、Lint系の全指摘を解消。
- 2025-12-04: フェーズ2-1として`secuority/cli/main.py`の`check`コマンドをヘルパー化し、PLR0912/0915の主要要因を分離。引き続き`apply`/`init`など残る複雑度箇所の分解を予定。
- 2025-12-04: フェーズ2-2で`apply`/`template`/`init`コマンドをヘルパー分割し、`uv run ruff check --select PLR0911,PLR0912,PLR0915 secuority/cli/main.py` がクリーンに。今後は`core/analyzer.py`等の複雑関数へ着手予定。
- 2025-12-04: フェーズ2-3で`core/analyzer.py` (`_detect_dependency_manager`/`_check_security_tools`ほか) と `core/applier.py` (`apply_changes_interactively`/依存移行) をヘルパー化、さらに `languages/cpp.py` `languages/python.py` の判定ロジックを簡素化。`uv run ruff check --select PLR0911,PLR0912,PLR0915` 全体がクリーンに。
- 2025-12-04: Basedpyright最新結果（80ファイル/494 error）を取得し、上位ボトルネックと型整備ロードマップ（Configスタック/GitHub統合/言語アナライザ/テスト群）を文書化。
- 2025-12-05: フェーズ3初動として `LanguageAnalyzer` に `ToolStatusMap` を導入し、各言語実装の `detect_tools`/`parse_dependencies` シグネチャを統一。`UV_CACHE_DIR=.uv-cache uv run basedpyright --outputjson` の再実行（46ファイル/1,238 error）で `reportIncompatibleMethodOverride` が 17→0 件、言語ファイルの累計も 6 ファイルで計 -17 件改善。
- 2025-12-05: `LanguageAnalyzer.analyze()` の戻り値を `LanguageAnalysisResult` TypedDict で固定し、`LanguageRegistry.analyze_project()` も `dict[str, LanguageAnalysisResult]` を返すよう整備。最新の `uv run basedpyright --outputjson`（46ファイル/1,237 error）を記録し、型情報を CLI/Analyzer へ伝播する準備を完了。
- 2025-12-05: フェーズ3主要型エラーの修正完了。`ProjectState.language_analysis`属性を追加（`dict[str, LanguageAnalysisResult]`型）、`analyze_github_repository()`の戻り値型を`GitHubAnalysisResult`に変更、`_workflow_has_*_checks()`の引数型を`GitHubWorkflowSummary`に変更、YAML/TOML読み込み結果に型注釈（`Any`）を追加。型エラー数は1,237→306件（約75%削減）に改善。`secuority/core/analyzer.py`のエラー数は47→30件に減少。主要なインターフェース不一致エラー（`reportIncompatibleMethodOverride`、`reportArgumentType`）を解消。
- 2025-12-05: `core/languages/{nodejs,python,rust}.py` に依存リスト正規化ヘルパーと TypedDict ベースのパース処理を導入し、`parse_dependencies` の Unknown 型を削減。さらに `core/precommit_integrator.py` は YAML 読み込み/書き出しを `_require_yaml_module`、`_coerce_config`、`_sanitize_repo_list` で統一し、hook マージ／重複検出も型安全なヘルパーで置き換え。`uv run basedpyright` の残件は 149 件まで減少、pre-commit 関連テストは既存挙動を維持したまま `uv run pytest` が通過（571 passed）。

## 型チェック棚卸し（basedpyright）
- **Config適用スタック**（`secuority/core/applier.py`, `secuority/core/analyzer.py`, `secuority/core/security_tools.py`, `secuority/core/template_manager.py`, `secuority/utils/diff.py`）: `ConfigurationMerger` と `Analyzer` が YAML/TOML 読み込み結果を `dict[str, Any]` のまま保持し、`ConfigChange`/`ApplyResult` を経由して `DiffGenerator` へ伝播している。`ApplyResult.changes` などの戻り値も未注釈で、`reportUnknownMemberType`/`reportUnknownVariableType` を誘発。Config payload, dependency 分析結果、workflow 推奨値を `TypedDict` 化し、`DiffRenderable` のような `Protocol` で `change_type.value` などの属性を縛る。
- **GitHub統合**（`secuority/core/github_integration.py`, `secuority/core/github_client.py`, `tests/unit/core/test_github_client.py`）: `safe_github_call` のフォールバック値が `dict | list | bool` の混在を返し、下流が `.get()`/`[]` を直接叩く構造。テストでは匿名の `MagicMock` を `urlopen` に差し込み `reportArgumentType` と `reportUnknownParameterType` が噴出。API レスポンス用 `TypedDict`（`GitHubApiStatus`, `PushProtectionCheck`, `WorkflowFile` 等）と URL リクエスト用 `Protocol` を定義し、pytest フィクスチャは `cast` と `simple_namespace` で型を満たす。
- **言語アナライザ群**（`secuority/core/languages/{python,nodejs,cpp,rust,csharp,go}.py`）: `ToolStatusMap` エイリアスと `LanguageAnalysisResult` TypedDict を base に追加し、`detect_tools`/`parse_dependencies` の共通シグネチャ化により `reportIncompatibleMethodOverride` は 17→0 件に減少。とはいえ `core/analyzer.py` など受け手は依然として `dict[str, Any]` 扱いのままで Unknown が残るため、`LanguageAnalysisResult` を引数／戻り値に伝播させ `.get()` チェーンを段階的に解体する。
- **テスト／ユーティリティ**（`tests/unit/core/test_precommit_integrator.py`, `tests/unit/utils/test_file_ops.py`, `tests/unit/utils/test_logger.py`）: `dict[str, Any]` のフィクスチャやローカル関数（`fail_replace`）が未注釈、`logger_module._logger_instance` の直接操作も `reportAttributeAccessIssue` を誘発。共通 TypedDict を `tests/fixtures/types.py` に置いて import する＋非公開属性操作は `contextlib.ExitStack` で monkeypatch する方針に切り替える。

## 型チェック次ステップ
1. **Config適用スタックの型整備**: `TypedDict` (`AnalyzerFinding`, `DependencySummary`, `TemplateMergePlan` 等) を `secuority/types/configuration.py` に切り出し、`ConfigurationMerger`/`Analyzer`/`SecurityToolsIntegrator`/`DiffGenerator`/`WorkflowIntegrator` へ逐次適用する。`ApplyResult` と `ConfigChange` に `Protocol` を噛ませ `change.change_type.value` や `change.conflicts` アクセス時の Unknown を解消。
2. **GitHub API モデルの導入**: `GitHubClient`・`GitHubIntegration` の返却値を `GitHubApiStatus`, `RepositorySecuritySettings`, `WorkflowFile`, `DependabotState` などの TypedDict で表現し、`safe_github_call` の `fallback_value` も同型に限定する。テストは共通フィクスチャを `tests/fixtures/github.py` に持たせ、`MagicMock` の `return_value`/`side_effect` に `cast` を挟む。
3. **LanguageAnalyzer型の伝播**: `LanguageAnalysisResult` TypedDict を `core/analyzer.py`・CLI・テンプレート層で直接受け取り、`dict[str, Any]` への変換や `.get()` 連鎖をやめる。必要に応じて `LanguageAnalysisResult` → dataclass 変換ユーティリティを導入し、`ToolStatusMap` も `Mapping[str, bool]` ベースへ引き上げる。
4. **テスト／ユーティリティの型付け**: `tests/unit/core/test_precommit_integrator.py` 向けに TypedDict ベースのフィクスチャを追加し、`tests/unit/utils/test_file_ops.py` のローカル関数へ引数/戻り値型を明示。`tests/unit/utils/test_logger.py` は module 直アクセスを避け `monkeypatch.setattr(logger_module, \"_logger_instance\", None)` と `cast[SecuorityLogger, Any]` でアクセスする。
