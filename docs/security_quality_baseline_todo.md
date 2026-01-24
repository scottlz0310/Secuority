# セキュリティ/コード品質基盤 TODO

この文書は「多言語のセキュリティ/品質標準を中央集権で提供する」という方針を、後から実装できるように TODO として整理したメモです。

## 目的
- 主要言語（Python/C#/C++/TypeScript/Rust/Go）を網羅する標準テンプレートを提供する
- 各言語の最適ツールを採用しつつ、ポリシー/出力/ゲート基準は共通化する
- ライセンスや運用制約でツールが差し替わっても破綻しない設計にする

## 前提
- ツールの多様化は許容する（テンプレートで最適化する）
- 依存関係更新は外部の renovate-config で管理済み
- LGPL-2.1 などのライセンス制約は中央ポリシーとして扱う

## TODO: 共通ポリシー
- [ ] ライセンス許可/拒否ルールを定義する（例: MIT/Apache/BSD/ISCのみ許可）
- [ ] 脆弱性のゲート基準（severity, fail threshold）を言語横断で統一する
- [ ] 出力形式（SARIF/JSON/Markdown）を統一し、PRコメント/Artifactの標準を決める
- [ ] CIの最低必須ジョブ（SAST/SCA/Secrets/Tests）を決める

## TODO: 共通ツール（言語横断）
- [ ] Secrets: gitleaks（全テンプレート必須）
- [ ] Dependency Review: GitHub dependency-review-action（全テンプレート必須）
- [ ] CodeQL: 対応言語は常時有効（Python/TS/Go/C#/C++/Rust）
- [ ] SBOM: syft 等で生成し、artifactとして保存
- [ ] ライセンス監査: OSS Review Toolkit or osv-scanner 等を検討

## TODO: 言語別ツール候補（初期案）
### Python
- [ ] Lint/Format: Ruff
- [ ] Type check: basedpyright
- [x] SAST: Bandit + CodeQL（Semgrepは廃止済み）
- [x] SCA: pip-audit + Safety（比較検証のため併用）
- [x] 横断スキャン: Trivy（FS/secrets/config）

### TypeScript / Node.js
- [ ] Lint/Format: ESLint + Prettier or Biome
- [ ] Type check: tsc
- [ ] SAST: CodeQL + ESLint security rules
- [ ] SCA: npm audit / osv-scanner

### C#
- [ ] Lint/Analyzer: dotnet analyzers + Roslyn
- [ ] SAST: CodeQL
- [ ] SCA: dotnet list package --vulnerable or OSV

### C++
- [ ] Lint: clang-tidy + cppcheck
- [ ] SAST: CodeQL
- [ ] SCA: vcpkg/Conan向けの依存監査を検討

### Rust
- [ ] Lint: clippy
- [ ] SAST: CodeQL
- [ ] SCA: cargo-audit + cargo-deny

### Go
- [ ] Lint: staticcheck + golangci-lint
- [ ] SAST: CodeQL + gosec
- [ ] SCA: govulncheck

## TODO: テンプレート設計
- [ ] 言語テンプレートは `base` / `strict` を基本に分岐
- [ ] ランタイム/用途別（app/lib/cli/server）プロファイルの導入
- [ ] セキュリティツールは「オプション化 + 互換ルール」で切替可能にする
- [ ] CIは「LTS + 最新」を基本とし、言語固有の最適マトリクスを定義する

## TODO: 実装ロードマップ（案）
- [ ] Phase 0: ポリシー定義（ライセンス/ゲート/出力）
- [ ] Phase 1: 共通ワークフローのベース化（SAST/SCA/Secrets）
- [ ] Phase 2: 言語別テンプレートのツール最適化
- [ ] Phase 3: ルール/設定の集約（単一設定ソース）
- [ ] Phase 4: テスト拡充（テンプレートの期待値固定）

## Semgrep 運用方針（決定済み）
- [x] Semgrepはリポジトリから完全に削除（LGPL-2.1ライセンス問題、間接依存による運用コスト増加のため）
- [x] 静的解析はCodeQL + Banditに移行
- [x] 依存脆弱性スキャンはpip-audit + Safetyで対応
- [x] 横断スキャンはTrivyで対応

## 未決事項
- [ ] 「許容ライセンス一覧」の最終合意（LGPL/MPLの扱い）
- [x] SCAを Safety / pip-audit / osv-scanner のどれに統一するか → pip-audit + Safetyを併用（比較検証期間後に判断）
- [x] CodeQL と言語固有SASTの役割分担 → CodeQLが主軸、Banditは軽量な即時検知用として継続
