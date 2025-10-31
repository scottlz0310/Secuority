#!/usr/bin/env python3
"""TOMLマージ処理のデバッグスクリプト"""

from pathlib import Path
from secuority.core.applier import ConfigurationApplier

def test_toml_merge():
    """TOMLマージ処理をテスト"""
    applier = ConfigurationApplier()
    
    # 既存のpyproject.tomlの内容（簡略版）
    existing_content = '''[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "secuority"
version = "0.1.0"
description = "Automate and standardize Python project security and quality configurations"
'''
    
    # テンプレートの内容（処理済み）
    template_content = '''[project]
name = "secuority"
version = "0.1.0"
description = "Automate and standardize Python project security and quality configurations"
authors = [
    {name = "Secuority Team", email = "team@secuority.dev"}
]

[tool.ruff]
line-length = 120
target-version = "py313"
'''
    
    print("=== TOMLマージ処理テスト ===")
    print("既存内容:")
    print(existing_content)
    print("\n" + "="*30 + "\n")
    print("テンプレート内容:")
    print(template_content)
    print("\n" + "="*50 + "\n")
    
    # マージ処理を実行
    try:
        merged_content, conflicts = applier._merge_toml_file(
            existing_content, 
            template_content, 
            Path("pyproject.toml")
        )
        
        print("マージ後の内容:")
        print(merged_content)
        print("\n" + "="*30 + "\n")
        print("競合:", conflicts)
        
        # TOML構文チェック
        try:
            import toml
            parsed = toml.loads(merged_content)
            print("✅ マージ後TOML構文チェック: 成功")
        except Exception as e:
            print("❌ マージ後TOML構文チェック: 失敗")
            print("エラー:", e)
            
    except Exception as e:
        print("❌ マージ処理失敗:")
        print("エラー:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_toml_merge()