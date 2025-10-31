# 要件文書

## 概要

SecuorityはPythonプロジェクトのコード品質とセキュリティ設定を自動化・標準化するCLIツールです。このシステムは、プロジェクト間での設定の分散、requirements.txt依存などの古い慣習、同じ設定を繰り返し手動で追加する非効率性の問題を解決します。このツールは、現代的なpyproject.toml中心の設定への移行、セキュリティベストプラクティスの自動適用、設定漏れの検出と修正提案を目的としています。

## 用語集

- **Secuority_CLI**: Pythonプロジェクト設定を分析・修正するコマンドラインインターフェースツール
- **Project_Directory**: 分析・修正対象となるPythonプロジェクトディレクトリ
- **Template_System**: 標準設定を保存する設定テンプレート管理システム
- **Configuration_Files**: pyproject.toml、requirements.txt、.gitignore、CIワークフローファイルなどのファイル
- **Security_Tools**: セキュリティ分析用のBandit、Safety、gitleaksなどのツール
- **Dependency_Groups**: 現代的なPython依存関係指定形式（PEP 735）
- **GitHub_API**: リポジトリセキュリティ設定確認用のGitHub REST API

## Requirements

### 要件 1

**ユーザーストーリー:** Pythonデベロッパーとして、プロジェクトの現在の設定状態を分析したい。そうすることで、何を現代化し、セキュアにする必要があるかを理解できる。

#### 受け入れ基準

1. ユーザーが`secuority check`を実行したとき、Secuority_CLIは既存のConfiguration_FilesについてProject_Directoryを分析しなければならない
2. Secuority_CLIはrequirements.txt、pyproject.toml、setup.py、.gitignoreファイルの存在を検出しなければならない
3. Secuority_CLIは既存の設定をTemplate_System標準と比較しなければならない
4. Secuority_CLIは設定の不備と推奨事項を示すレポートを生成しなければならない
5. `--verbose`フラグが提供された場合、Secuority_CLIは詳細な分析情報を表示しなければならない

### 要件 2

**ユーザーストーリー:** Pythonデベロッパーとして、requirements.txtからpyproject.tomlに移行したい。そうすることで、現代的な依存関係管理の慣習を使用できる。

#### 受け入れ基準

1. requirements.txtが存在し、pyproject.tomlに依存関係が含まれていない場合、Secuority_CLIはpyproject.tomlへの移行を提案しなければならない
2. Secuority_CLIは移行前にrequirements.txtのバックアップを作成しなければならない
3. Secuority_CLIはパッケージ仕様をpyproject.toml形式に変換しなければならない
4. Poetry、PDM、またはSetuptools-SCM設定が検出された場合、Secuority_CLIは自動移行をスキップし、警告を表示しなければならない
5. Secuority_CLIはextras仕様を検出し、dependency-groups形式への移行を提案しなければならない

### 要件 3

**ユーザーストーリー:** Pythonデベロッパーとして、リンティングとコード品質ツールを標準化したい。そうすることで、プロジェクトが一貫した品質基準に従うことができる。

#### 受け入れ基準

1. Secuority_CLIはRuffとMypyの設定をpyproject.tomlに統合しなければならない
2. 既存のツール設定が見つかった場合、Secuority_CLIはそれらを標準テンプレートとマージしなければならない
3. 設定の競合が発生した場合、Secuority_CLIはユーザーに解決を促さなければならない
4. Secuority_CLIはすべてのツール設定がpyproject.tomlに統合されることを保証しなければならない
5. Secuority_CLIはマージされた設定が構文的に正しいことを検証しなければならない

### 要件 4

**ユーザーストーリー:** Pythonデベロッパーとして、.gitignoreファイルがPythonのベストプラクティスに従うことを保証したい。そうすることで、機密ファイルや不要なファイルを誤ってコミットしないようにできる。

#### 受け入れ基準

1. Secuority_CLIは既存の.gitignoreをPython標準テンプレートと比較しなければならない
2. Secuority_CLIは.envファイル、__pycache__、その他のPython固有パターンの欠落エントリを検出しなければならない
3. Secuority_CLIは既存のエントリを削除することなく、.gitignoreへの追加を提案しなければならない
4. Secuority_CLIはセキュリティのために.envファイルが明示的に無視されることを保証しなければならない
5. Secuority_CLIは.gitignoreが存在しない場合、それを作成しなければならない

### 要件 5

**ユーザーストーリー:** Pythonデベロッパーとして、セキュリティツールをプロジェクトに統合したい。そうすることで、脆弱性とセキュリティ問題を自動的に検出できる。

#### 受け入れ基準

1. Secuority_CLIはpyproject.tomlの`tool.bandit`セクションにBandit設定を追加しなければならない
2. Secuority_CLIは`tool.secuority.safety`セクションでSafety設定を構成しなければならない
3. 既存のセキュリティツール設定が存在する場合、Secuority_CLIはマージ戦略を使用してそれらをマージしなければならない
4. Secuority_CLIは機密漏洩を防ぐためにgitleaks用のpre-commitフックを設定しなければならない
5. Secuority_CLIはセキュリティチェックを実行するCIワークフローを設定しなければならない

### 要件 6

**ユーザーストーリー:** Pythonデベロッパーとして、偶発的な機密コミットを防ぎたい。そうすることで、開発、CI、リポジトリレベル全体でセキュリティベストプラクティスを維持できる。

#### 受け入れ基準

1. Secuority_CLIはローカル機密検出のためにgitleaksを使用したpre-commitフックを設定しなければならない
2. Secuority_CLIはCIレベルの機密検証のためにGitHub Actionsワークフローを作成しなければならない
3. GITHUB_PERSONAL_ACCESS_TOKENが利用可能な場合、Secuority_CLIはGitHub Push Protectionステータスを確認しなければならない
4. GitHub API呼び出しが失敗した場合、Secuority_CLIは実行を継続し、失敗を警告として報告しなければならない
5. Secuority_CLIはAPIアクセスが利用できない場合、GitHub Push Protectionの設定手順を提供しなければならない

### 要件 7

**ユーザーストーリー:** Pythonデベロッパーとして、設定変更を安全に適用したい。そうすることで、プロジェクトに変更が加えられる前に、変更を確認し承認できる。

#### 受け入れ基準

1. ユーザーが`secuority apply`を実行したとき、Secuority_CLIは提案された各ファイル変更のunified diffを表示しなければならない
2. Secuority_CLIはユーザーがファイル単位で変更を承認または拒否できるようにしなければならない
3. `--dry-run`フラグが提供された場合、Secuority_CLIは変更を適用せずに提案された変更を表示しなければならない
4. Secuority_CLIは変更を適用する前に既存ファイルのバックアップを作成しなければならない
5. マージ競合が発生した場合、Secuority_CLIは手動解決を要求しなければならない

### 要件 8

**ユーザーストーリー:** Pythonデベロッパーとして、設定テンプレートを管理したい。そうすることで、標準を最新に保ち、必要に応じてカスタマイズできる。

#### 受け入れ基準

1. Secuority_CLIはOS適切な設定ディレクトリにテンプレートを保存しなければならない
2. SECUORITY_TEMPLATES_DIR環境変数が設定されている場合、Secuority_CLIはテンプレート用にそのディレクトリを使用しなければならない
3. ユーザーが`secuority template update`を実行したとき、Secuority_CLIはリモートソースから更新されたテンプレートを取得しなければならない
4. Secuority_CLIはテンプレート更新のバージョン履歴を維持しなければならない
5. ユーザーが`secuority init`を実行したとき、Secuority_CLIはテンプレートディレクトリとconfig.yamlを初期化しなければならない

### 要件 9

**ユーザーストーリー:** Pythonデベロッパーとして、CI/CDと依存関係管理の設定を検証したい。そうすることで、自動化されたセキュリティと品質チェックが適切に配置されていることを保証できる。

#### 受け入れ基準

1. Secuority_CLIは品質とセキュリティチェック用の既存のGitHub Actionsワークフローを検出しなければならない
2. Secuority_CLIはDependabot設定を推奨設定と比較しなければならない
3. GitHub APIアクセスが利用可能な場合、Secuority_CLIはリポジトリセキュリティ設定を検証しなければならない
4. Secuority_CLIは欠落しているCI/CDワークフロー設定を提案しなければならない
5. Secuority_CLIは自動化された依存関係更新設定を検出し、報告しなければならない
