了解です。では、\*\*“Incomplete URL substring sanitization” を二度と起こさないための方針（設計原則とチェックリスト）\*\*をまとめます。修正は後で進められるよう、**テスト／本番コード／CodeQL設定**の3レイヤで指針を用意しました。

***

## 1) 設計原則（本番コード・テスト共通）

1.  **URLは必ずパースしてから検証**
    文字列の `includes` / `endswith` で許可可否を決めない。**`URL` / `urllib.parse` 等で `hostname`（必要なら `port` / `scheme`）を取り出して判定**する。
    *根拠:* CodeQL公式は「URLを文字列部分一致で扱うと、パスやクエリ、サブドメインに許可ドメインを埋め込んで回避される。ホストで厳格に検証せよ」と明示。 [\[sugawarake...epoint.com\]](https://sugawarakensetsu-my.sharepoint.com/personal/hiroyasu_sugawarakensetsu_onmicrosoft_com/Documents/Microsoft%20Copilot%20Chat%20%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB/test_security_md_generation.py), [\[github.com\]](https://github.com/github/codeql/issues/7937)

2.  **許可リスト（allowlist）で“完全一致”**
    許可するFQDN（例：`example.com`、`www.example.com`）を**列挙し、完全一致のみ**許可。サブドメインをまとめて許可するなら「`.`＋基底ドメイン」（例：`hostname.endswith(".example.com")`）の**正しくパースした値**で判定。
    *根拠:* OWASPはオープンリダイレクト対策に **whitelist方式** を推奨。部分一致は誤判定の温床。 [\[nlsq.readthedocs.io\]](https://nlsq.readthedocs.io/en/stable/developer/ci_cd/codeql_quick_reference.html), [\[github.com\]](https://github.com/wsollers/codeql_suppression_comments/blob/main/AlertSuppression.ql)

3.  **プロトコルはホワイトリスト化（`http` / `https` のみ）**
    `javascript:` / `data:` / `ftp:` などは拒否。**`@`、`//`、エンコードされたスラッシュ**等の曖昧表記には正規化で対処する。
    *根拠:* URL検証バイパスの代表的手法が各種特殊表記。正規化＋ホワイトリストが有効。 [\[zenn.dev\]](https://zenn.dev/hankei6km/scraps/68a821c76f72e6)

4.  **可能なら相対URL運用**
    外部ドメインへの遷移が不要なら**相対パスのみ**受け付ける設計にし、外部遷移は**サーバ側で固定**する。
    *根拠:* OWASPの安全なリダイレクト設計（固定URL／ユーザー入力に依存しない）。 [\[nlsq.readthedocs.io\]](https://nlsq.readthedocs.io/en/stable/developer/ci_cd/codeql_quick_reference.html)

5.  **ログと拒否理由の明示**
    拒否時はステータスと簡潔な理由（unsupported scheme / host not allowed など）を返し、**監査ログに残す**。
    *根拠:* 仕様上の“安全な失敗（fail-safe）”はセキュリティ運用の基本。 [\[nlsq.readthedocs.io\]](https://nlsq.readthedocs.io/en/stable/developer/ci_cd/codeql_quick_reference.html)

***

## 2) テストの指針（今回のケースに直結）

*   **文字列の部分一致アサートは禁止**
    `assert "example.com" in content` のような**包含判定**は不適切。**URL抽出 → パース → `hostname` の一致**に置き換える。
    *根拠:* CodeQLはテストでも不安全なパターンを検出する。公式が示す安全パターンは**パース＋ホスト一致**。 [\[sugawarake...epoint.com\]](https://sugawarakensetsu-my.sharepoint.com/personal/hiroyasu_sugawarakensetsu_onmicrosoft_com/Documents/Microsoft%20Copilot%20Chat%20%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB/test_security_md_generation.py), [\[github.com\]](https://github.com/github/codeql/issues/7937)

*   **URL抽出ヘルパーを共通化**
    Markdown／HTMLから `http(s)://` を正規表現で抽出 → `urlparse` → `hostname` セットで検証。テスト全体で再利用し、**安全な検証ロジックを統一**。

*   **許可ホストの明示**
    テスト期待値も `{"example.com", "github.com"}` のような**許可集合**で一致検証（完全一致）。
    *根拠:* allowlist方式をテストにも反映しておくと、将来の実装変更でも安全性が保たれる。 [\[github.com\]](https://github.com/wsollers/codeql_suppression_comments/blob/main/AlertSuppression.ql)

***

## 3) CodeQL側の運用（除外・調整）

> 修正は後で行うとのことなので、**CIノイズ低減の即効策**も合わせて提示します。

*   **`paths-ignore` でテスト除外（推奨するが、言語差に注意）**
    `.github/codeql/codeql-config.yml` に `paths` / `paths-ignore` を記述し、Actionの `init` で `config-file` を指定。例：
    ```yaml
    # .github/codeql/codeql-config.yml
    name: "secuority CodeQL"
    paths:
      - src
    paths-ignore:
      - tests
      - "**/__tests__/**"
      - "**/*.test.py"
    ```
    ```yaml
    # .github/workflows/codeql.yml
    - uses: github/codeql-action/init@v3
      with:
        languages: ${{ matrix.language }}
        config-file: ./.github/codeql/codeql-config.yml
    ```
    *注意:* 解析対象の絞り込みは**言語やビルドモードにより効果差**があります（インタプリタ言語は効きやすい）。 [\[github.com\]](https://github.com/linode/linode-cli/issues/735), [\[stackoverflow.com\]](https://stackoverflow.com/questions/75944180/sanitizing-a-dynamic-url-with-angulars-domsanitizer-without-the-bypasssecurityt)

*   **クエリ単位の除外（`query-filters`）**
    一時的に該当クエリを外す例：
    ```yaml
    # .github/codeql/codeql-config.yml
    name: "secuority CodeQL"
    query-filters:
      - exclude:
          id: py/incomplete-url-substring-sanitization
      - exclude:
          id: js/incomplete-url-substring-sanitization
    ```
    *根拠:* GitHub公式が**クエリフィルター**での除外をサポート。 [\[github.com\]](https://github.com/OWASP/wstg/blob/master/document/4-Web_Application_Security_Testing/11-Client-side_Testing/04-Testing_for_Client-side_URL_Redirect.md)

*   **（参考）インライン抑制は標準未サポート**
    いわゆる `# noqa` 的な**コード内コメントでの抑制は標準では不可**。CLIで\*\*`@kind alert-suppression`\*\*のカスタムクエリを併用する方法や、**UIでのDismiss**、**SARIFフィルタ**が選択肢。 [\[stackoverflow.com\]](https://stackoverflow.com/questions/3756924/sanitizing-untrusted-url-strings-that-will-be-passed-to-location-replace), [\[stackoverflow.com\]](https://stackoverflow.com/questions/71485991/incomplete-string-escaping-or-encoding), [\[swisskyrep....github.io\]](https://swisskyrepo.github.io/PayloadsAllTheThings/Open%20Redirect/)

***

## 4) 実装チェックリスト（配布用の短縮版）

*   [ ] URLを必ずパース（`URL` / `urlparse`）
*   [ ] `scheme ∈ {http, https}` 以外は拒否
*   [ ] `hostname` を**許可リストで完全一致**（必要なら `endswith(".example.com")`）
*   [ ] `@` / `//` / エンコード混在は**正規化後に判定**
*   [ ] 相対URLのみ受け付ける設計を検討
*   [ ] 拒否時は**理由を明示＋ログ**
*   [ ] **テストも同じ検証ロジック**（部分一致禁止）
*   [ ] CodeQL設定で**不要領域の除外**／クエリフィルター併用

***

## 5) 参考リンク（一次情報）

*   CodeQL Query Help: **Incomplete URL substring sanitization**（JS版の解説・安全例） [\[sugawarake...epoint.com\]](https://sugawarakensetsu-my.sharepoint.com/personal/hiroyasu_sugawarakensetsu_onmicrosoft_com/Documents/Microsoft%20Copilot%20Chat%20%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB/test_security_md_generation.py)
*   CodeQL Query Help: **Python版**（`urlparse`＋許可リストの安全例） [\[github.com\]](https://github.com/github/codeql/issues/7937)
*   OWASP Cheat Sheet: **Unvalidated Redirects and Forwards**（安全なリダイレクト設計） [\[nlsq.readthedocs.io\]](https://nlsq.readthedocs.io/en/stable/developer/ci_cd/codeql_quick_reference.html)
*   OWASP ASVS 5.1.5: **URLリダイレクトは許可リストのみ** [\[github.com\]](https://github.com/wsollers/codeql_suppression_comments/blob/main/AlertSuppression.ql)
*   PortSwigger: **URL validation bypass cheat sheet**（検証回避ペイロード集） [\[zenn.dev\]](https://zenn.dev/hankei6km/scraps/68a821c76f72e6)
*   CodeQL設定のカスタマイズ（`paths` / `paths-ignore` / `config-file`） [\[github.com\]](https://github.com/linode/linode-cli/issues/735), [\[stackoverflow.com\]](https://stackoverflow.com/questions/75944180/sanitizing-a-dynamic-url-with-angulars-domsanitizer-without-the-bypasssecurityt)
*   クエリフィルターでの除外（`query-filters`） [\[github.com\]](https://github.com/OWASP/wstg/blob/master/document/4-Web_Application_Security_Testing/11-Client-side_Testing/04-Testing_for_Client-side_URL_Redirect.md)

***

必要なら、後で修正に取り掛かる際に**パッチ雛形**（今回お示ししたテスト用ヘルパー＋いくつかの置換）をまとめてお渡しします。
他にも、`secuority` の**横断ルール**として「URL検証ユーティリティ」を1つ用意して、Python/Node.jsで**同じインターフェース**にしておくと、将来C#/C++側にも移植しやすいですよ。どう進めるか、次に着手する箇所をご指定ください。
