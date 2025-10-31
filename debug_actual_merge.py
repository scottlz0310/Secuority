#!/usr/bin/env python3
"""実際のpyproject.tomlとのマージテスト"""

from pathlib import Path
from secuority.core.applier import ConfigurationApplier
from secuority.core.template_manager import TemplateManager

def test_actual_merge():
    """実際のpyproject.tomlとのマージをテスト"""
    applier = ConfigurationApplier()
    template_manager = TemplateManager()
    
    print("=== 実際のマージ処理テスト ===")
    
    # 現在のpyproject.tomlを読み込み
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("❌ pyproject.tomlが見つかりません")
        return
        
    with open(pyproject_path, 'r', encoding='utf-8') as f:
        existing_content = f.read()
    
    print("既存pyproject.toml読み込み成功")
    print("既存内容（最初の300文字）:")
    print(existing_content[:300])
    print("\n" + "="*50 + "\n")
    
    # テンプレートを読み込み・処理
    try:
        templates = template_manager.load_templates()
        template_content = templates.get("pyproject.toml.template")
        
        if not template_content:
            print("❌ テンプレートが見つかりません")
            return
            
        # テンプレート処理
        processed_template = applier._process_template_variables(
            template_content, 
            pyproject_path
        )
        
        print("テンプレート処理完了")
        print("処理済みテンプレート（最初の300文字）:")
        print(processed_template[:300])
        print("\n" + "="*50 + "\n")
        
        # マージ処理
        try:
            merged_content, conflicts = applier._merge_toml_file(
                existing_content,
                processed_template,
                pyproject_path
            )
            
            print("マージ処理完了")
            print("マージ後内容（最初の500文字）:")
            print(merged_content[:500])
            print("\n" + "="*30 + "\n")
            
            # TOML構文チェック
            try:
                import toml
                parsed = toml.loads(merged_content)
                print("✅ マージ後TOML構文チェック: 成功")
            except Exception as e:
                print("❌ マージ後TOML構文チェック: 失敗")
                print("エラー:", e)
                
                # エラー箇所を特定
                lines = merged_content.split('\n')
                for i, line in enumerate(lines[:30], 1):
                    print(f"{i:2d}: {line}")
                    
        except Exception as e:
            print("❌ マージ処理失敗:")
            print("エラー:", e)
            import traceback
            traceback.print_exc()
        
    except Exception as e:
        print("❌ テンプレート処理失敗:")
        print("エラー:", e)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_actual_merge()