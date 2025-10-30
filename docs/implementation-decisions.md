# Implementation Decisions

このドキュメントでは README が扱う実装方針のうち、詳細な判断基準や補足仕様をまとめる。

## 1. 依存関係移行のガードレール

- pyproject.toml への移行は、既存のビルド・デプロイで requirements.txt が参照されていないことを検出した場合にのみ自動提案する。
- requirements.txt 由来の依存関係はテンポラリにバックアップし、ユーザー承認後に削除可否を選択できるようにする。
- Poetry/PDM/Setuptools-SCM など他ツールに基づく設定を検出した場合は、自動移行をスキップし警告を出す。

## 2. GitHub 連携と認証

- GitHub Push Protection/Dependabot の状態確認は `GITHUB_TOKEN` 環境変数 (読み取りスコープ) が利用可能な場合にのみ実施する。
- トークンが見つからない場合はローカル情報のみで評価し、未実施の旨をレポートに残す。
- API 呼び出しが失敗した際は CLI を失敗させず、警告として扱う。

## 3. テンプレート配置と上書き

- デフォルトのテンプレートディレクトリは OS に応じて以下を利用する: Windows は `%APPDATA%\secuority\templates`、POSIX は `$XDG_CONFIG_HOME/secuority/templates` (未設定時は `~/.config/secuority/templates`)。
- `SECUORITY_TEMPLATES_DIR` 環境変数でテンプレートディレクトリを上書き可能にする。
- 初期化コマンドは存在しないテンプレートファイルのみを書き出し、既存ファイルはバックアップの上で上書き確認を行う。

## 4. セキュリティツール統合

- Bandit は `tool.bandit` セクションを pyproject.toml に生成し、プロファイルファイルがある場合は外部参照を行う。
- Safety は `tool.secuority.safety` セクションで CLI 実行時の推奨設定を管理し、CI ワークフローでは `safety check --full-report` を実行する。
- いずれのツールも既存設定がある場合はマージ戦略を適用し、衝突時はユーザーに選択を促す。

## 5. apply フローの差分提示

- `secuority apply` は各ファイルごとに unified diff を表示し、ユーザーはファイル単位で適用可否を選択できる。
- 拒否された差分はレポートに残し、次回実行時まで保持する。
- 自動マージは 3-way merge (既存ファイル/テンプレート/適用後) を使用し、コンフリクト発生時は手動解決を要求する。

## 6. 機密漏洩対策ワークフロー

- pre-commit は既存の `.pre-commit-config.yaml` がある場合に `repos` の重複を避けるマージを行い、未導入の場合はテンプレートを追加する。
- CI ワークフローは GitHub Actions 用の YAML テンプレートを提供し、既存ワークフローとの重複検出を試みる (ファイル名・ジョブ名ベース)。
- Push Protection の有効/無効判定は GitHub API から取得し、ローカルでは設定手順のみ提示する。

## 7. CLI コマンドの振る舞い

- `secuority init`: テンプレートディレクトリと config.yaml を初期化する。既存ファイルはバックアップ (`*.bak`) を作成する。
- `secuority template update`: リモートソース (GitHub Releases など) からテンプレートを更新し、バージョン履歴を記録する。
- `secuority template list`: 利用可能なテンプレートの名前とバージョンを表示する。

## 8. ロードマップ整合性

- setup.py からの移行提案は v0.1 の検出範囲に含め、v0.3 以降で自動修正オプションを提供する。
- v0.4 で GitHub Actions/Dependabot を扱う場合、前述の認証要件をクリアしていることを条件とする。

必要に応じて本ドキュメントを README から参照し、詳細を更新する。
