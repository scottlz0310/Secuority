#!/usr/bin/env python3
"""テンプレート処理機能のデバッグスクリプト"""

from pathlib import Path
from secuority.core.applier import ConfigurationApplier

def test_template_processing():
    """テンプレート変数処理をテスト"""
    applier = ConfigurationApplier()
    
    # テンプレート内容（簡単な例）
    template_content = '''[project]
name = "{{ project_name }}"
version = "{{ project_version | default('0.1.0') }}"
description = "{{ project_description | default('') }}"
authors = [
    {name = "{{ author_name | default('') }}", email = "{{ author_email | default('') }}"}
]'''
    
    # テスト用のファイルパス
    test_file = Path("pyproject.toml")
    
    print("=== テンプレート処理テスト ===")
    print("入力テンプレート:")
    print(template_content)
    print("\n" + "="*50 + "\n")
    
    # テンプレート処理を実行
    processed = applier._process_template_variables(template_content, test_file)
    
    print("処理後の内容:")
    print(processed)
    print("\n" + "="*50 + "\n")
    
    # TOML構文チェック
    try:
        import toml
        parsed = toml.loads(processed)
        print("✅ TOML構文チェック: 成功")
        print("パース結果:", parsed)
    except Exception as e:
        print("❌ TOML構文チェック: 失敗")
        print("エラー:", e)

if __name__ == "__main__":
    test_template_processing()