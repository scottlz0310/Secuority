# 言語別テンプレート調査と修正方針

## 目的
言語別テンプレートが実際の開発慣行とズレている点を洗い出し、最適化方針を明文化する。
Renovate テンプレートは外部リポジトリ（`../renovate-config/`）へ移管済みのため、本書では扱わない。

## 調査範囲
- `secuority/templates/python`
- `secuority/templates/nodejs`
- `secuority/templates/rust`
- `secuority/templates/go`
- `secuority/templates/cpp`
- `secuority/templates/csharp`
- 各言語の GitHub Actions ワークフロー

## 現状の課題と修正方針（言語別）

### Python
課題:
- `pyproject.toml.template` の classifiers に重複があり、`requires-python`/`tool.ruff`/`basedpyright` のバージョン指定と整合しない。
- `project.optional-dependencies` と `tool.uv.dev-dependencies` が二重管理になっている。
- `tool.secuority.safety` は標準的な設定キーではなく、実運用と一致しない。
- pre-commit に `detect-secrets` を含むが `.secrets.baseline` がテンプレートに存在しない。

方針:
- `requires-python` を単一の基準にし、classifiers と `tool.ruff`/`basedpyright` を自動同期する。
- 依存管理は PEP 735 の dependency groups を優先し、`project.optional-dependencies` との二重化を解消する。
- Safety の設定は標準キーへ移行（`tool.safety`）またはテンプレートから除去して採用時にのみ追加する。
- `detect-secrets` を維持する場合は `.secrets.baseline` 生成方針をテンプレートに含める。

### Node.js / TypeScript
課題:
- `tsconfig.json.template` が `moduleResolution: bundler` 固定で、Node.js サーバ用途に最適化されていない。
- `biome.json.template` が TypeScript 前提の厳密なルール設計になっていない。
- CI が npm 前提で、pnpm/yarn を自動選択できない。
- Node バージョンが `package.json` の `engines`/`.nvmrc` を参照していない。

方針:
- `node` / `bundler` / `library` の用途別テンプレートに分割し、`moduleResolution` と `module` を切り替える。
- Biome は `javascript`/`typescript` を分離し、`recommended` の上書きポリシーを明示する。
- ロックファイル（`package-lock.json`/`pnpm-lock.yaml`/`yarn.lock`）を検出して CI のパッケージマネージャを切り替える。
- Node バージョンは `engines` または `.nvmrc` を優先し、未指定なら LTS のみを利用する。

### Rust
課題:
- `Cargo.toml.template` の edition が 2021 固定で、最新エディションと乖離しやすい。
- `cargo-audit`/`cargo-deny`/`cargo-tarpaulin` を毎回インストールするため CI が重い。
- MSRV や `rust-toolchain.toml` への追従がない。

方針:
- edition は最新版（例: 2024）を標準とし、`rust-version` を明記する。
- セキュリティツールはキャッシュ・アクション利用を前提にし、必要なジョブだけに限定する。
- `rust-toolchain.toml` があればそれを優先し、なければ stable のみを使用する。

### Go
課題:
- Go バージョンのマトリクスが固定で、`go.mod` の `go`/`toolchain` に連動しない。
- `golangci-lint` の `version: latest` と `gosec@master` は再現性に欠ける。
- `golangci.yml` が厳しすぎるプロジェクトでノイズになりやすい。

方針:
- `go.mod` の `go`/`toolchain` を読み取り、最新 + LTS のみを検証対象にする。
- `golangci-lint` と `gosec` はバージョン固定を必須化する。
- `golangci.yml` を `base` / `strict` の2段階で提供する。

### C++
課題:
- `CMakeLists.txt.template` が単一構成（実行ファイル固定）で、ライブラリ/テスト構成に最適化されていない。
- `.clang-tidy` の命名規則が一般的な C++ コーディング規約と合わない場合がある。
- CI がコンパイラごとの警告差分を吸収できない。

方針:
- `exe` / `lib` / `header-only` のテンプレート分岐を設ける。
- `.clang-tidy` は複数プロファイル（Google/LLVM/プロジェクト独自）で選択可能にする。
- CI では Clang/GCC/MSVC を分離し、警告扱いの違いをドキュメント化する。

### C#
課題:
- `Directory.Build.props` が `LangVersion=latest` 固定で、ターゲット SDK と不整合になる可能性がある。
- analyzers のバージョンが固定で、更新戦略が不明瞭。
- CI が .NET 9.0.x 固定で、`global.json` 未考慮。

方針:
- `global.json` があればその SDK を最優先し、なければ LTS（8.x）を標準にする。
- analyzers は `Directory.Packages.props` で集中管理する方針に移行する。
- `dotnet format` は任意ステップとして分離し、未導入プロジェクトではスキップ可能にする。

## 横断的な改善方針
- テンプレートは「用途別プロファイル」と「言語別プロファイル」の二軸で管理する。
- 既存ファイル検出（`go.mod`, `package.json`, `Cargo.toml`, `global.json`, `CMakeLists.txt` など）で最適テンプレートを自動選択する。
- CI は「LTS + 最新」の最小構成を標準にし、無駄なマトリクスを削減する。
- 依存関係更新の自動化は外部リポジトリ（`renovate-config`）へ委譲する。

## テンプレート・バリアント命名統一（設計）
目的: 同じ言語でも「用途」と「厳格度」を切り替えられるようにし、命名規則を固定する。

### バリアントID
- `base`: 最小構成。デフォルトで採用される基準。
- `strict`: 静的解析・セキュリティを強化した構成。
- `app`: 実行アプリ向け（CLI/Web/Service）。ビルド・実行を前提にした設定。
- `lib`: ライブラリ/SDK向け。公開APIと互換性を重視。

### 合成ルール
- `app-strict`, `lib-strict` を許可し、「用途 + 厳格度」を一意に表す。
- 片方のみ指定された場合は以下にフォールバック:
  - `app` → `base`
  - `lib` → `base`
  - `strict` → `base`

### ディレクトリ構造
```
secuority/templates/
  common/
    base/
    strict/
  <language>/
    base/
    strict/
    app/
    lib/
    app-strict/
    lib-strict/
```

### 既存テンプレートの位置づけ
- 現行のテンプレートは **すべて `base` 相当** とみなし、順次 `base/` 配下へ移行する。
- `strict` は `base` を上書きする差分のみを持つ方針とする。

### 選択優先順位（仕様）
1. `app-strict` / `lib-strict`（合成）
2. `app` / `lib`
3. `strict`
4. `base`

## 次のアクション
1. 言語ごとのテンプレート・バリアント設計（`base`/`strict`/`app`/`lib` の命名統一）。
2. TemplateManager に「用途別テンプレート選択」ロジックを追加。
3. テンプレート更新時のテスト追加（言語別の期待差分固定）。
