# secuority バージョンアップ計画

## 目的

secuority を言語横断の品質・セキュリティ基盤へ進化させ、Python、Node.js、C++、C# を含むモノレポ構成にも対応する。

## 背景

従来は Python 一辺倒で uv を必須とする設計だったが、最近はフロントエンド (Electron)、バックエンド (Python)、さらに C++ や C# を含む複雑な構成が増加。品質・セキュリティルールを横断的に適用する必要がある。

## 課題

・pre-commit.ci は Python 中心で Node/C++/C# の対応が不十分
・モノレポで旧実装と新実装が混在し、ルール適用が難しい
・ツール選定が古く、モダン化が必要 (ESLint → Biome、MyPy → basedpyright 等)
・Renovate.jsonの設定も言語横断で最適化が必要

## 対応方針

・言語横断の共通ルール (秘密情報検出、コミット品質) を全リポジトリに適用
・言語別ルールをモジュール化し、プロジェクト構成に応じて選択的に適用
・pre-commit + CI のハイブリッド運用 (軽量チェックは pre-commit、重い検査は CI)

## モダン化対象ツール一覧

## アーキテクチャ概要

・共通ルール: pre-commit-hooks, gitleaks, detect-secrets
・言語別モジュール: Python(uv, ruff, basedpyright), Node(Biome), C++(clang-format), C#(dotnet format)
・CI: GitHub Actions で重い検査を並列実行 (Python, Node, C++, C#)

## テンプレート更新方針

・pre-commit テンプレートをモジュール化 (共通 + 言語別)
・CI テンプレートをマトリクス構成で提供
・secuority CLI に --modern オプションを追加し、最新ツールを自動適用

## CI統合方針

・pre-commit.ci は Python 中心の軽量チェックに利用
・Node/C++/C# は GitHub Actions で補完
・uv は公式インストーラーで CI に導入

## 今後のロードマップ

1. モダン化版テンプレートの試験導入
2. secuority CLI の改修 (テンプレート生成器の拡張)
3. 全リポジトリへの横展開 (PR 自動生成)
4. 継続的改善 (新ツール対応、CI最適化)


旧ツール | 新ツール

--- | ---

ESLint | Biome

MyPy | basedpyright

npm audit | osv-scanner

Safety | Safety (継続)

clang-format/clang-tidy | 継続

dotnet format | 継続