import os
import json
import hashlib
import aiohttp
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from PIL import Image
import io

_log = logging.getLogger(__name__)

class EmojiManager:
    """表情管理器"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.emoji_dir = os.path.join(data_dir, "emojis")
        self.emoji_data_file = os.path.join(data_dir, "emoji_data.json")
        self.emoji_data = {}
        
        # 创建目录
        os.makedirs(self.emoji_dir, exist_ok=True)
    
    async def load_emoji_data(self):
        """加载表情数据"""
        try:
            if os.path.exists(self.emoji_data_file):
                with open(self.emoji_data_file, 'r', encoding='utf-8') as f:
                    self.emoji_data = json.load(f)
            else:
                self.emoji_data = {}
                await self.save_emoji_data()
        except Exception as e:
            _log.error(f"加载表情数据失败: {e}")
            self.emoji_data = {}
    
    async def save_emoji_data(self):
        """保存表情数据"""
        try:
            with open(self.emoji_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.emoji_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log.error(f"保存表情数据失败: {e}")
    
    async def add_emoji_from_url(self, image_url: str, user_id: int, description: str = None) -> Optional[str]:
        """从URL添加表情"""
        try:
            # 生成唯一ID
            emoji_id = hashlib.md5(f"{image_url}_{datetime.now().isoformat()}".encode()).hexdigest()[:12]
            
            # 下载图片
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        
                        # 验证图片格式
                        try:
                            img = Image.open(io.BytesIO(image_data))
                            img.verify()
                        except Exception:
                            _log.warning(f"无效的图片格式: {image_url}")
                            return None
                        
                        # 确定文件扩展名
                        file_extension = self._get_file_extension(image_url, image_data)
                        file_path = os.path.join(self.emoji_dir, f"{emoji_id}.{file_extension}")
                    
                        # 保存图片文件
                        with open(file_path, 'wb') as f:
                            f.write(image_data)
                        
                        # 解析AI分析结果
                        parsed_category, parsed_description = self._parse_ai_description(description or "表情图片")

                        # 保存表情信息
                        self.emoji_data[emoji_id] = {
                            "file_path": file_path,
                            "original_url": image_url,
                            "added_by": user_id,
                            "added_time": datetime.now().isoformat(),
                            "description": parsed_description,
                            "category": parsed_category,
                            "usage_count": 0,
                            "file_size": len(image_data),
                            "dimensions": self._get_image_dimensions(image_data)
                        }
                        
                        await self.save_emoji_data()
                        _log.info(f"添加表情成功: {emoji_id}")
                        return emoji_id
                        
        except Exception as e:
            _log.error(f"添加表情失败: {e}")
        
        return None
    
    def _get_file_extension(self, url: str, image_data: bytes) -> str:
        """获取文件扩展名"""
        # 首先尝试从URL获取
        url_ext = url.split('.')[-1].lower()
        if url_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
            return url_ext
        
        # 从图片数据判断格式
        try:
            img = Image.open(io.BytesIO(image_data))
            format_map = {
                'JPEG': 'jpg',
                'PNG': 'png',
                'GIF': 'gif',
                'WEBP': 'webp'
            }
            return format_map.get(img.format, 'jpg')
        except Exception:
            return 'jpg'
    
    def _get_image_dimensions(self, image_data: bytes) -> Dict[str, int]:
        """获取图片尺寸"""
        try:
            img = Image.open(io.BytesIO(image_data))
            return {"width": img.width, "height": img.height}
        except Exception:
            return {"width": 0, "height": 0}
    
    def _auto_categorize(self, description: str) -> str:
        """自动分类表情"""
        description_lower = description.lower()
        
        # 情感分类关键词
        categories = {
            "开心": ["开心", "高兴", "笑", "愉快", "快乐", "兴奋", "😊", "😄", "😆", "哈哈"],
            "难过": ["难过", "伤心", "哭", "悲伤", "沮丧", "😢", "😭", "😞"],
            "愤怒": ["愤怒", "生气", "恼火", "😠", "😡", "🤬"],
            "惊讶": ["惊讶", "震惊", "吃惊", "意外", "😲", "😱", "🤯"],
            "疑惑": ["疑惑", "困惑", "不解", "疑问", "🤔", "😕", "😵"],
            "调皮": ["调皮", "顽皮", "搞怪", "恶作剧", "😜", "😝", "🤪"],
            "无语": ["无语", "无奈", "尴尬", "汗", "😅", "😓", "🙄"],
            "赞同": ["赞同", "同意", "点赞", "好的", "👍", "👌", "✅"],
            "可爱": ["可爱", "萌", "卡通", "动物", "🥰", "😍", "🐱"],
            "思考": ["思考", "想", "考虑", "🤔", "💭"],
            "睡觉": ["睡", "困", "累", "😴", "💤"],
            "吃东西": ["吃", "食物", "美食", "🍕", "🍔", "🍰"]
        }
        
        for category, keywords in categories.items():
            if any(keyword in description_lower for keyword in keywords):
                return category
        
        return "其他"

    def _parse_ai_description(self, ai_description: str) -> tuple:
        """解析AI分析结果，提取分类和描述"""
        try:
            # 检查是否是AI分析的格式：分类:描述
            if ':' in ai_description:
                parts = ai_description.split(':', 1)
                category = parts[0].strip()
                description = parts[1].strip()

                # 验证分类是否有效
                valid_categories = [
                    "开心", "难过", "愤怒", "惊讶", "疑惑", "无语",
                    "赞同", "可爱", "调皮", "思考", "睡觉", "吃东西", "其他"
                ]

                if category in valid_categories:
                    return category, description

            # 检查是否是旧格式：[分类] 描述
            if '[' in ai_description and ']' in ai_description:
                start = ai_description.find('[') + 1
                end = ai_description.find(']')
                if start > 0 and end > start:
                    category = ai_description[start:end].strip()
                    description = ai_description[end+1:].strip()

                    # 验证分类
                    valid_categories = [
                        "开心", "难过", "愤怒", "惊讶", "疑惑", "无语",
                        "赞同", "可爱", "调皮", "思考", "睡觉", "吃东西", "其他"
                    ]

                    if category in valid_categories:
                        return category, description

            # 如果无法解析，使用自动分类
            category = self._auto_categorize(ai_description)
            return category, ai_description

        except Exception as e:
            _log.warning(f"解析AI描述失败: {e}")
            return "其他", ai_description or "表情图片"

    def get_emoji_by_category(self, category: str) -> List[str]:
        """根据分类获取表情ID列表"""
        return [
            emoji_id for emoji_id, emoji_info in self.emoji_data.items()
            if emoji_info.get('category') == category
        ]
    
    def get_emoji_by_keywords(self, keywords: List[str]) -> List[str]:
        """根据关键词搜索表情"""
        matching_emojis = []
        
        for emoji_id, emoji_info in self.emoji_data.items():
            description = emoji_info.get('description', '').lower()
            if any(keyword.lower() in description for keyword in keywords):
                matching_emojis.append(emoji_id)
        
        return matching_emojis
    
    def get_emoji_info(self, emoji_id: str) -> Optional[Dict]:
        """获取表情信息"""
        return self.emoji_data.get(emoji_id)
    
    def get_emoji_file_path(self, emoji_id: str) -> Optional[str]:
        """获取表情文件路径"""
        emoji_info = self.emoji_data.get(emoji_id)
        if emoji_info and os.path.exists(emoji_info['file_path']):
            return emoji_info['file_path']
        return None
    
    def update_usage_count(self, emoji_id: str):
        """更新表情使用次数"""
        if emoji_id in self.emoji_data:
            self.emoji_data[emoji_id]['usage_count'] = self.emoji_data[emoji_id].get('usage_count', 0) + 1
    
    def get_popular_emojis(self, limit: int = 10) -> List[str]:
        """获取热门表情"""
        sorted_emojis = sorted(
            self.emoji_data.items(),
            key=lambda x: x[1].get('usage_count', 0),
            reverse=True
        )
        return [emoji_id for emoji_id, _ in sorted_emojis[:limit]]
    
    def get_random_emoji(self, category: str = None) -> Optional[str]:
        """随机获取表情"""
        import random
        
        if category:
            emoji_list = self.get_emoji_by_category(category)
        else:
            emoji_list = list(self.emoji_data.keys())
        
        if emoji_list:
            return random.choice(emoji_list)
        return None
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取表情库统计信息"""
        total_count = len(self.emoji_data)
        
        # 分类统计
        categories = {}
        total_usage = 0
        
        for emoji_info in self.emoji_data.values():
            category = emoji_info.get('category', '其他')
            categories[category] = categories.get(category, 0) + 1
            total_usage += emoji_info.get('usage_count', 0)
        
        # 文件大小统计
        total_size = sum(emoji_info.get('file_size', 0) for emoji_info in self.emoji_data.values())
        
        return {
            "total_count": total_count,
            "categories": categories,
            "total_usage": total_usage,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "average_usage": round(total_usage / total_count, 2) if total_count > 0 else 0
        }
    
    async def cleanup_unused_files(self):
        """清理未使用的文件"""
        try:
            # 获取所有表情文件路径
            used_files = set()
            for emoji_info in self.emoji_data.values():
                if 'file_path' in emoji_info:
                    used_files.add(os.path.basename(emoji_info['file_path']))
            
            # 扫描表情目录
            if os.path.exists(self.emoji_dir):
                for filename in os.listdir(self.emoji_dir):
                    if filename not in used_files:
                        file_path = os.path.join(self.emoji_dir, filename)
                        try:
                            os.remove(file_path)
                            _log.info(f"清理未使用文件: {filename}")
                        except Exception as e:
                            _log.warning(f"清理文件失败 {filename}: {e}")
                            
        except Exception as e:
            _log.error(f"清理文件失败: {e}")
    
    async def remove_emoji(self, emoji_id: str) -> bool:
        """删除表情"""
        try:
            if emoji_id in self.emoji_data:
                emoji_info = self.emoji_data[emoji_id]
                
                # 删除文件
                if 'file_path' in emoji_info and os.path.exists(emoji_info['file_path']):
                    os.remove(emoji_info['file_path'])
                
                # 删除数据
                del self.emoji_data[emoji_id]
                await self.save_emoji_data()
                
                _log.info(f"删除表情成功: {emoji_id}")
                return True
                
        except Exception as e:
            _log.error(f"删除表情失败: {e}")
        
        return False
