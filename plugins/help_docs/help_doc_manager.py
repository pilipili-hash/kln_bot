"""
帮助文档管理工具
用于管理和维护插件帮助文档
"""

import json
import os
from typing import Dict, List, Optional
from .plugin_help_docs import PLUGIN_HELP_DOCS, add_plugin_help, update_plugin_help

class HelpDocManager:
    """帮助文档管理器"""
    
    def __init__(self):
        self.docs_file = os.path.join(os.path.dirname(__file__), "plugin_help_docs.json")
    
    def export_to_json(self) -> bool:
        """导出帮助文档到JSON文件"""
        try:
            with open(self.docs_file, 'w', encoding='utf-8') as f:
                json.dump(PLUGIN_HELP_DOCS, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"导出帮助文档失败: {e}")
            return False
    
    def import_from_json(self) -> bool:
        """从JSON文件导入帮助文档"""
        try:
            if os.path.exists(self.docs_file):
                with open(self.docs_file, 'r', encoding='utf-8') as f:
                    docs = json.load(f)
                    PLUGIN_HELP_DOCS.update(docs)
                return True
            return False
        except Exception as e:
            print(f"导入帮助文档失败: {e}")
            return False
    
    def add_plugin_doc(self, plugin_name: str, display_name: str, version: str, 
                      description: str, category: str, help_content: str) -> bool:
        """添加插件帮助文档"""
        try:
            doc_data = {
                "display_name": display_name,
                "version": version,
                "description": description,
                "category": category,
                "help_content": help_content
            }
            add_plugin_help(plugin_name, doc_data)
            return True
        except Exception as e:
            print(f"添加插件帮助文档失败: {e}")
            return False
    
    def update_plugin_doc(self, plugin_name: str, **kwargs) -> bool:
        """更新插件帮助文档"""
        try:
            update_plugin_help(plugin_name, kwargs)
            return True
        except Exception as e:
            print(f"更新插件帮助文档失败: {e}")
            return False
    
    def get_plugin_list(self) -> List[str]:
        """获取所有插件名称列表"""
        return list(PLUGIN_HELP_DOCS.keys())
    
    def get_categories(self) -> List[str]:
        """获取所有插件类别"""
        categories = set()
        for doc in PLUGIN_HELP_DOCS.values():
            categories.add(doc.get('category', '其他功能'))
        return list(categories)
    
    def get_plugins_by_category(self, category: str) -> List[Dict]:
        """按类别获取插件"""
        plugins = []
        for name, doc in PLUGIN_HELP_DOCS.items():
            if doc.get('category', '其他功能') == category:
                plugins.append({
                    'name': name,
                    'display_name': doc.get('display_name', name),
                    'description': doc.get('description', ''),
                    'version': doc.get('version', '未知')
                })
        return plugins
    
    def validate_help_content(self, help_content: str) -> Dict[str, bool]:
        """验证帮助内容格式"""
        validation = {
            'has_commands': False,
            'has_usage': False,
            'has_examples': False,
            'has_notes': False
        }
        
        if '📝 管理命令' in help_content or '📋 命令列表' in help_content:
            validation['has_commands'] = True
        
        if '🎮 使用方式' in help_content:
            validation['has_usage'] = True
            
        if '💡 使用示例' in help_content:
            validation['has_examples'] = True
            
        if '⚠️ 注意事项' in help_content:
            validation['has_notes'] = True
            
        return validation
    
    def generate_template(self, plugin_name: str) -> str:
        """生成帮助文档模板"""
        template = f"""📝 管理命令：
• /命令1 <参数> - 命令1描述
• /命令2 - 命令2描述

🎮 使用方式：
1. 使用方法1
2. 使用方法2
3. 使用方法3

💡 使用示例：
/命令1 示例参数
/命令2

⚠️ 注意事项：
• 注意事项1
• 注意事项2
• 注意事项3"""
        return template

# 全局管理器实例
help_doc_manager = HelpDocManager()

def get_help_doc_manager() -> HelpDocManager:
    """获取帮助文档管理器实例"""
    return help_doc_manager
