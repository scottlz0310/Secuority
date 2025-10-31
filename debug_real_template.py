#!/usr/bin/env python3
"""実際のテンプレートファイルでのデバッグ"""

from pathlib import Path
from secuority.core.applier import ConfigurationApplier
from secuority.core.template_manager import TemplateManager

def test_real_template():
    """実際のテンプレートファイルでテスト"""
    applier = ConfigurationApplier()
    template_manager = TemplateManager()
    
    print("=== 実際のテンプレートファイルテスト ===")
    
    # テンプレートを読み込み
    try:
        templates = template_manager.load_templates()
        pyproject_template = templates.get("pyproject.toml.template")
        
        if not pyproject_template:
            print("❌ pyproject.toml.templateが見つかりません")
            return
            
        print("テンプレート読み込み成功")
        print("テンプレート内容（最初の500文字）:")
        print(pyproject_template[:500])
        print("\n" + "="*50 + "\n")
        
        # テンプレート処理
        processed = applier._process_template_variables(
            pyproject_template, 
            Path("pyproject.toml")
        )
        
        print("テンプレート処理後（最初の500文字）:")
        print(processed[:500])
        print("\n" + "="*50 + "\n")
        
        # TOML構文チェック
        try:
            import toml
            parsed = toml.loads(processed)
            print("✅ 処理後TOML構文チェック: 成功")
            print("プロジェクト名:", parsed.get('project', {}).get('name'))
        except Exception as e:
            print("❌ 処理後TOML構文チェック: 失敗")
            print("エラー:", e)
            
            # エラー箇所を特定
            lines = processed.split('\n')
            for i, line in enumerate(lines[:20], 1):
                print(f"{i:2d}: {line}")
        
    except Exception as e:
        print("❌ テンプレート読み込み失敗:")
        print("エラー:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_template()