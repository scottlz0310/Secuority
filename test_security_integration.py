#!/usr/bin/env python3
"""セキュリティツール統合のテスト"""

from pathlib import Path

from rich.console import Console

from secuority.core.security_tools import SecurityToolsIntegrator

console = Console()


def test_security_integration():
    """セキュリティツール統合をテスト"""
    integrator = SecurityToolsIntegrator()

    console.print("=== セキュリティツール統合テスト ===")

    # 既存のpyproject.tomlを読み込み
    project_path = Path.cwd()

    try:
        changes = integrator.integrate_security_tools(project_path, ["bandit"])

        console.print(f"変更数: {len(changes)}")

        for i, change in enumerate(changes, 1):
            console.print(f"\n変更 {i}:")
            console.print(f"  ファイル: {change.file_path}")
            console.print(f"  タイプ: {change.change_type}")
            console.print(f"  説明: {change.description}")

            if hasattr(change, "new_content") and change.new_content:
                console.print("  新しい内容（最初の500文字）:")
                console.print(change.new_content[:500])

                # TOML構文チェック
                try:
                    import toml

                    _ = toml.loads(change.new_content)
                    console.print("  ✅ TOML構文チェック: 成功")
                except Exception as e:
                    console.print("  ❌ TOML構文チェック: 失敗")
                    console.print(f"  エラー: {e}")

                    # エラー箇所を表示
                    lines = change.new_content.split("\n")
                    for j, line in enumerate(lines[:20], 1):
                        console.print(f"  {j:2d}: {line}")

    except Exception as e:
        console.print(f"❌ セキュリティツール統合失敗: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_security_integration()
