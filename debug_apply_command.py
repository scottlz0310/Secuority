#!/usr/bin/env python3
"""applyコマンドの詳細デバッグ"""

from pathlib import Path
from secuority.core.applier import ConfigurationApplier
from secuority.core.template_manager import TemplateManager
from secuority.core.analyzer import ProjectAnalyzer
from secuority.core.engine import CoreEngine
from secuority.core.github_client import GitHubClient

def debug_apply_command():
    """applyコマンドの処理を段階的にデバッグ"""
    print("=== Apply コマンド詳細デバッグ ===")
    
    # コアエンジンを作成
    analyzer = ProjectAnalyzer()
    template_manager = TemplateManager()
    applier = ConfigurationApplier()
    github_client = GitHubClient()
    
    core_engine = CoreEngine(
        analyzer=analyzer,
        template_manager=template_manager,
        applier=applier,
        github_client=github_client if github_client.is_authenticated() else None,
    )
    
    project_path = Path.cwd()
    
    # 1. プロジェクト分析
    print("1. プロジェクト分析中...")
    project_state = core_engine.analyze_project(project_path)
    print(f"   pyproject.toml存在: {project_state.has_pyproject_toml}")
    
    # 2. テンプレート読み込み
    print("2. テンプレート読み込み中...")
    try:
        templates = core_engine.template_manager.load_templates()
        print(f"   テンプレート数: {len(templates)}")
        print(f"   pyproject.toml.template存在: {'pyproject.toml.template' in templates}")
    except Exception as e:
        print(f"   ❌ テンプレート読み込み失敗: {e}")
        return
    
    # 3. 変更生成（pyproject.tomlのみ）
    print("3. pyproject.toml変更生成中...")
    if project_state.has_pyproject_toml and "pyproject.toml.template" in templates:
        try:
            change = core_engine.applier.merge_file_configurations(
                project_path / "pyproject.toml",
                templates["pyproject.toml.template"]
            )
            
            print(f"   変更タイプ: {change.change_type}")
            print(f"   説明: {change.description}")
            print(f"   競合数: {len(change.conflicts) if hasattr(change, 'conflicts') else 0}")
            
            # 競合の詳細を表示
            if hasattr(change, 'conflicts') and change.conflicts:
                print("   競合の詳細:")
                for i, conflict in enumerate(change.conflicts, 1):
                    print(f"     {i}. {conflict.description}")
                    print(f"        既存値: {conflict.existing_value}")
                    print(f"        テンプレート値: {conflict.template_value}")
            
            # 新しい内容をチェック
            if hasattr(change, 'new_content'):
                print("   新しい内容（最初の300文字）:")
                print(change.new_content[:300])
                
                # TOML構文チェック
                try:
                    import toml
                    parsed = toml.loads(change.new_content)
                    print("   ✅ 生成された内容のTOML構文: 成功")
                except Exception as e:
                    print("   ❌ 生成された内容のTOML構文: 失敗")
                    print(f"   エラー: {e}")
                    
                    # エラー箇所を表示
                    lines = change.new_content.split('\n')
                    for i, line in enumerate(lines[:20], 1):
                        print(f"   {i:2d}: {line}")
            
        except Exception as e:
            print(f"   ❌ 変更生成失敗: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("   スキップ（条件不一致）")

if __name__ == "__main__":
    debug_apply_command()