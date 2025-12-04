# コード品質改善プラン（2025-12-04）

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
`uv run basedpyright --outputjson` から抽出した上位10ファイルとルール件数:

| 件数 | ファイル |
| ---: | --- |
| 117 | `tests/integration/test_security_features.py` |
| 69  | `secuority/core/applier.py` |
| 60  | `secuority/core/analyzer.py` |
| 39  | `secuority/core/precommit_integrator.py` |
| 33  | `tests/unit/core/test_github_client.py` |
| 32  | `secuority/core/github_integration.py` |
| 23  | `secuority/utils/diff.py` |
| 23  | `tests/unit/core/test_precommit_integrator.py` |
| 22  | `secuority/core/security_tools.py` |
| 21  | `secuority/core/languages/nodejs.py` |

主なルール件数: `reportUnknownMemberType` 303件、`reportUnknownVariableType` 148件、`reportUnknownArgumentType` 74件。  
→ 動的 dict/list を返す内部API、`PluginConfig` 等の型定義不足、テストが `dict` リテラルで未注釈などがボトルネック。

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
- 2025-12-04: プラン初版作成。フェーズ1未着手（PLC0415/S110/ARG002/PLW2901/PTH123の是正準備中）。
- 2025-12-04: フェーズ1-1としてコアモジュール（workflow_integrator/security_tools/template_manager/applier/言語アナライザ）の遅延import整理とPath API化を実施。`uv run ruff check --select PLC0415,S110,ARG002,PLW2901,PTH123` で残42件（主に言語アナライザのS110/ARG002とtests配下）まで削減。
- 2025-12-04: フェーズ1-2でtests配下のPLC0415を解消し、各言語アナライザの`ARG002`/`PLW2901`/`S110`と`models/project.py`の指摘を修正。`uv run ruff check --select PLC0415,S110,ARG002,PLW2901,PTH123` がクリーンに通過（0件）したため、フェーズ1のLint面は完了。
