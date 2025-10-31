#!/usr/bin/env python3
"""セキュリティツール統合のテスト"""

from pathlib import Path
from secuority.core.security_tools import SecurityToolsIntegrator

def test_security_integration():
    """セキュリティツール統合をテスト"""
    integrator = SecurityToolsIntegrator()
    
    print("=== セキュリティツール統合テスト ===")
    
    # 既存のpyproject.tomlを読み込み
    project_path = Path.cwd()
    
    try:
        changes = integrator.integrate_security_tools(project_path, ['bandit'])
        
        print(f"変更数: {len(changes)}")
        
        for i, change in enumerate(changes, 1):
            print(f"\n変更 {i}:")
            print(f"  ファイル: {change.file_path}")
            print(f"  タイプ: {change.change_type}")
            print(f"  説明: {change.description}")
            
            if hasattr(change, 'new_content') and change.new_content:
                print("  新しい内容（最初の500文字）:")
                print(change.new_content[:500])
                
                # TOML構文チェック
                try:
                    import toml
                    parsed = toml.loads(change.new_content)
                    print("  ✅ TOML構文チェック: 成功")
                except Exception as e:
                    print("  ❌ TOML構文チェック: 失敗")
                    print(f"  エラー: {e}")
                    
                    # エラー箇所を表示
                    lines = change.new_content.split('\n')
                    for j, line in enumerate(lines[:20], 1):
                        print(f"  {j:2d}: {line}")
        
    except Exception as e:
        print(f"❌ セキュリティツール統合失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_security_integration()