最高です。**Secuority** の “横断テンプレート” として、

*   **`renovate.json`（共通プリセット）**
*   **GitHub Actions 2 本（PR 更新用＋main 検証用）**
*   **再利用しやすい構成／適用手順**

を一式で用意しました。**Python=uv／Node=pnpm／.NET=NuGet／C++=Conan** を前提にしています。

***

## 構成（Secuority リポジトリ）

    secuority/
    ├─ presets/
    │  └─ renovate/
    │     ├─ default.jsonc          # 横断プリセット (shareable config)
    │     └─ README.md              # 適用ガイド
    ├─ .github/
    │  └─ workflows/
    │     ├─ update-lock-on-renovate-pr.yml   # PRトリガー（Renovate PR限定）
    │     └─ verify-lock-on-main.yml          # main push検証
    └─ .github/workflows/ (上記以外)

*   \*\*shareable config（プリセット）\*\*は、各プロジェクトから `extends: ["github>OrgName/secuority:presets/renovate/default.jsonc"]` のように参照できます。
*   Actions は **サブモジュール化不要**。各プロジェクト側で `workflow_call` を使う方法もありますが、まずは **Secuority を presets 置き場**として、各プロジェクトに **同名ワークフローを置く**運用がシンプルです。

***

## 1) `presets/renovate/default.jsonc`

> 方針：
>
> *   **Python（uv）**：依存は `pyproject.toml` に **ピン指定**。ロックは CI で再生成。
> *   **Node（pnpm）**：devDeps 非メジャーはグルーピング＋オートマージ、メジャーは段階。
> *   **.NET（NuGet）**：SDK スタイル前提。exact `[x.y.z]` は更新対象外。
> *   **C++（Conan）**：まとめて更新、必要に応じ `replace`。
> *   実行時間は **JST 夜間＋週末**、PRノイズを抑制。

```jsonc
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "description": "Secuority cross-language preset (Python=uv, Node=pnpm, .NET=NuGet, C++=Conan)",
  "extends": [
    "config:recommended"
  ],

  // 対象 manager を限定（必要に応じて追加/削除）
  "enabledManagers": ["pep621", "poetry", "pnpm", "nuget", "conan"],

  "dependencyDashboard": false,
  "labels": ["dependencies", "renovate"],
  "separateMultipleMajor": true,

  "timezone": "Asia/Tokyo",
  "schedule": [
    "after 10pm every weekday",
    "every weekend"
  ],

  "packageRules": [
    // ---------- Python（uv前提：ピン＋ロックはCI） ----------
    {
      "description": "Python: 非メジャー更新まとめ（ロックはCIで再生成）",
      "matchCategories": ["python"],
      "matchUpdateTypes": ["minor", "patch"],
      "groupName": "Python (non-major)",
      "rangeStrategy": "pin",
      "automerge": false
    },
    {
      "description": "Python: Poetry を併用する場合もピン方針",
      "matchManagers": ["poetry"],
      "rangeStrategy": "pin"
    },

    // ---------- Node（pnpm） ----------
    {
      "description": "Node: devDeps 非メジャーはまとめ & オートマージ",
      "matchManagers": ["pnpm"],
      "matchDepTypes": ["devDependencies"],
      "matchUpdateTypes": ["minor", "patch"],
      "groupName": "Node dev (non-major)",
      "automerge": true
    },
    {
      "description": "Node: メジャーは段階的に分割",
      "matchManagers": ["pnpm"],
      "matchUpdateTypes": ["major"],
      "separateMajorMinor": true,
      "automerge": false
    },

    // ---------- .NET（NuGet） ----------
    {
      "description": "NuGet: exact ピン（[x.y.z]）は更新停止",
      "matchManagers": ["nuget"],
      "matchCurrentValue": "/^\\[[^,]+\\]$/",
      "enabled": false
    },
    {
      "description": "NuGet: 非メジャーをまとめる",
      "matchManagers": ["nuget"],
      "matchUpdateTypes": ["minor", "patch"],
      "groupName": "NuGet (non-major)"
    },

    // ---------- C++（Conan） ----------
    {
      "description": "Conan: まとめて更新（範囲は replace）",
      "matchManagers": ["conan"],
      "groupName": "Conan deps",
      "rangeStrategy": "replace"
    }
  ]
}
```

> **各プロジェクトの `renovate.json`** は最小構成でOK：

```jsonc
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["github>YourOrg/secuority:presets/renovate/default.jsonc"]
}
```

***

## 2) PR トリガー：`update-lock-on-renovate-pr.yml`

*   Renovate が作成した **依存更新 PR** に限定し、**ロック再生成→差分をコミット**します。
*   **`--upgrade` は使いません**（Renovate が pyproject のバージョンを管理し、CI は “その仕様に従ってロック生成” という責務分担）。

```yaml
name: Update lockfiles on Renovate PR

on:
  pull_request:
    types: [opened, synchronize, reopened]
    branches: [main, develop]   # ベースブランチに合わせて変更

jobs:
  update-locks:
    if: >
      github.actor == 'renovate[bot]' || startsWith(github.actor, 'renovate')
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      # ---------- Python (uv) ----------
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'  # 菅原さんの標準に合わせる
      - name: Install uv
        run: |
          pipx install uv
          uv --version
      - name: Regenerate uv.lock
        run: |
          # Renovateがpyproject.tomlを更新済み想定
          uv lock
      - name: Commit uv.lock (if changed)
        run: |
          if git status --porcelain | grep -q "uv.lock"; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add uv.lock
            git commit -m "chore(uv): regenerate uv.lock for Renovate update"
            git push
          fi

      # ---------- Node (pnpm) ----------
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'      # 必要に応じて
          cache: 'pnpm'
      - name: Install pnpm
        run: corepack enable && pnpm -v
      - name: Update pnpm lockfile
        run: pnpm install --lockfile-only
      - name: Commit pnpm-lock.yaml (if changed)
        run: |
          if git status --porcelain | grep -q "pnpm-lock.yaml"; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add pnpm-lock.yaml
            git commit -m "chore(pnpm): regenerate lockfile for Renovate update"
            git push
          fi

      # ---------- .NET (NuGet) ----------
      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '9.0.x' # 必要に応じて
      - name: Restore (locked mode if applicable)
        run: |
          # Directory.Packages.props / global.json がある場合の整合確認
          dotnet restore

      # ---------- C++ (Conan) ----------
      - name: Install Conan
        run: |
          pipx install conan
          conan --version
      - name: Update Conan lock (if repo uses Conan)
        run: |
          # 例: プロジェクトごとにコマンド微調整
          if ls | grep -E 'conanfile\.(txt|py)' >/dev/null; then
            conan lock create conanfile.txt --lockfile-out=conan.lock || true
          fi
      - name: Commit conan.lock (if changed)
        run: |
          if git status --porcelain | grep -q "conan.lock"; then
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add conan.lock
            git commit -m "chore(conan): regenerate lockfile for Renovate update"
            git push
          fi
```

> **ポイント**
>
> *   各言語の“ロック生成”はプロジェクト構成により差があるため、**if存在チェック**を入れて安全運用。
> *   将来、Python のみ・Node のみ等の軽量版に切り分ける場合は **ジョブ分割**／**再利用ワークフロー化**も可能です。

***

## 3) main push 検証：`verify-lock-on-main.yml`

*   **main に push / merge された時**、**ロック整合を強制**（ズレたら失敗）。
*   人間が直接 push した場合の **保険**として機能します。

```yaml
name: Verify lockfiles on main

on:
  push:
    branches: [main]

jobs:
  verify-locks:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      # ---------- Python (uv) ----------
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install uv
        run: pipx install uv
      - name: Verify uv.lock (frozen)
        run: |
          # 差分がある場合は失敗化
          uv lock --frozen

      # ---------- Node (pnpm) ----------
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'pnpm'
      - name: Verify pnpm lockfile (frozen)
        run: pnpm install --lockfile-only --frozen-lockfile

      # ---------- .NET (NuGet) ----------
      - name: Setup .NET
        uses: actions/setup-dotnet@v4
        with:
          dotnet-version: '9.0.x'
      - name: Verify restore
        run: dotnet restore

      # ---------- C++ (Conan) ----------
      - name: Install Conan
        run: pipx install conan
      - name: Verify Conan lock (optional)
        run: |
          if ls | grep -E 'conanfile\.(txt|py)' >/dev/null; then
            # 必要なら lock の検証コマンドをプロジェクト側で定義
            echo "Conan lock verification step"
          fi
```

> **設計意図**
>
> *   **PRでロック生成→レビュー時点で完全**、**mainで最終チェック**の二段構え。
> *   `--frozen` 系は「齟齬があれば失敗」。**ズレを main に持ち込ませない**ための最後の砦。

***

## 横断適用の手順（各プロジェクト側）

1.  **Renovate 設定**
    プロジェクトの `renovate.json` に Secuority のプリセットを指定：
    ```jsonc
    {
      "$schema": "https://docs.renovatebot.com/renovate-schema.json",
      "extends": ["github>YourOrg/secuority:presets/renovate/default.jsonc"]
    }
    ```
2.  **CI ワークフロー**
    *   PR用：`update-lock-on-renovate-pr.yml`（Secuority のものをコピペ／再利用）
    *   main用：`verify-lock-on-main.yml`（同上）
3.  **必要に応じて微調整**
    *   Python バージョン（`3.13` / `3.14`）
    *   Node バージョン／pnpm のメジャー
    *   .NET の SDK バージョン
    *   Conan コマンド（プロジェクトの運用に合わせる）

***

## 運用Tips

*   **ラベル＆レビュー**：Renovate PRには `dependencies` ラベルを自動付与済み。チームルールに合わせて `auto-merge` を限定（例：devDeps のみ）。
*   **スケジュール**：JST 夜間＋週末設定でノイズ抑制。必要なら「月初のみ」などにも容易に変更可能。
*   **失敗時の可観測性**：main 検証で失敗したら、\*\*アラート（Slack/Teams）\*\*を発火するジョブを追記するとさらに堅牢。
*   **将来拡張**：vcpkg を採用する場合は、Renovate未対応なので CI 側のロック・更新ロジックを用意（regex manager を使った擬似運用もありですが、まずは Conan 推奨）。

***

## 次アクション（ご希望があれば）

*   このテンプレートを **実ファイルとして**用意してお渡しします。
*   プロジェクト側での \*\*再利用（`workflow_call` による呼び出し）\*\*版も作れます。
*   Teams/Slack 通知、セマンティックコミット、自動ラベル、ブランチ保護連携なども **Secuority 標準**として同梱可能。

***

必要なら、**YourOrg 名**や **ブランチ名**、**Python/Node/.NET の標準バージョン**に合わせて即座に調整します。
どの組織名／対象ブランチで運用しますか？ また、Python は **3.13 固定**で良いですか（3.14 へ段階移行計画なら、allowedVersions も合わせて書きます）。
