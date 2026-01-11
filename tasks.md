# 次回作業ガイド

このファイルは次回以降の作業で迷わないための指針メモです。

## 目的
- 多言語（Python/C#/C++/TypeScript/Rust/Go）のセキュリティ/品質基盤を中央集権で標準化する
- ツールの多様化は許容し、テンプレートごとに最適化する

## 次回の優先タスク
- [ ] 許容/拒否ライセンスの最終合意（LGPL/MPLの扱い）
- [ ] 共通ポリシー定義（ゲート基準・出力形式・必須ジョブ）
- [ ] 言語別ツールの最終選定（SAST/SCA/Lint/Type）
- [ ] テンプレート設計の確定（base/strict + 用途別プロファイル）
- [ ] CI共通フローの設計（SAST/SCA/Secrets/Tests）

## 参照ドキュメント
- `docs/security_quality_baseline_todo.md`: セキュリティ/品質基盤のTODOと実装方針の整理
- `docs/template_language_optimization.md`: 言語別テンプレートの課題と最適化方針

## 実装前の確認事項
- [ ] Semgrep運用方針（デフォルト無効/オプション化/バージョン固定）
- [ ] SCA統一ツール（Safety/pip-audit/osv-scanner）
- [ ] CodeQLと言語固有SASTの役割分担
