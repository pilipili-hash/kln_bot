import os
import json
import yaml
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

_log = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "config.json")
        self.group_data_file = os.path.join(data_dir, "group_data.json")
        self.character_file = "default.yml"  # 人设配置文件
        
        # 默认配置
        self.default_config = {
            "enabled_groups": [],  # 启用的群组
            "reply_probability": 0.1,  # 回复概率 (0.0-1.0)
            "emoji_probability": 0.3,  # 发送表情的概率
            "max_reply_length": 200,  # 最大回复长度
            "cooldown_seconds": 30,  # 冷却时间
            "fake_users": {},  # 伪装用户配置
            "trigger_keywords": ["好的", "是的", "哈哈", "笑死", "确实"],  # 触发关键词
            "blacklist_keywords": ["管理", "踢人", "禁言"],  # 黑名单关键词
            "advanced_settings": {
                "min_message_length": 2,  # 最小消息长度才触发
                "max_daily_replies": 50,  # 每日最大回复数
                "learning_mode": False,  # 学习模式（记录群友说话习惯）
                "auto_adjust_probability": False,  # 自动调整回复概率
                "personality_variation": True,  # 性格变化
                "time_based_activity": True  # 基于时间的活跃度
            }
        }
        
        # 默认群友配置模板
        self.default_fake_user = {
            "nickname": "群友小助手",
            "user_id": "fake_user",
            "personality": "友善、活泼、喜欢聊天的群友",
            "speaking_style": "轻松随意，偶尔使用网络用语和表情",
            "activity_hours": [9, 10, 11, 14, 15, 16, 19, 20, 21, 22],  # 活跃时间段
            "personality_traits": {
                "humor_level": 0.7,  # 幽默程度 0-1
                "enthusiasm": 0.6,   # 热情程度 0-1
                "formality": 0.3,    # 正式程度 0-1
                "emoji_usage": 0.5   # 表情使用频率 0-1
            }
        }

        self.config = {}
        self.group_data = {}
        self.character_config = {}  # 人设配置

        # 创建数据目录
        os.makedirs(data_dir, exist_ok=True)
    
    async def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和加载的配置
                    self.config = self._merge_config(self.default_config, loaded_config)
            else:
                self.config = self.default_config.copy()
                await self.save_config()

            # 加载人设配置
            await self.load_character_config()
        except Exception as e:
            _log.error(f"加载配置失败: {e}")
            self.config = self.default_config.copy()

    async def load_character_config(self):
        """加载人设配置文件"""
        try:
            if os.path.exists(self.character_file):
                with open(self.character_file, 'r', encoding='utf-8') as f:
                    self.character_config = yaml.safe_load(f)
                    _log.info("人设配置加载成功")
            else:
                _log.warning(f"人设配置文件不存在: {self.character_file}")
                self.character_config = {}
        except Exception as e:
            _log.error(f"加载人设配置失败: {e}")
            self.character_config = {}
    
    async def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log.error(f"保存配置失败: {e}")
    
    async def load_group_data(self):
        """加载群组数据"""
        try:
            if os.path.exists(self.group_data_file):
                with open(self.group_data_file, 'r', encoding='utf-8') as f:
                    self.group_data = json.load(f)
            else:
                self.group_data = {}
                await self.save_group_data()
        except Exception as e:
            _log.error(f"加载群组数据失败: {e}")
            self.group_data = {}
    
    async def save_group_data(self):
        """保存群组数据"""
        try:
            with open(self.group_data_file, 'w', encoding='utf-8') as f:
                json.dump(self.group_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            _log.error(f"保存群组数据失败: {e}")
    
    def _merge_config(self, default: Dict, loaded: Dict) -> Dict:
        """合并配置，保留默认值"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def get_config(self, key: str, default=None):
        """获取配置值"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    async def set_config(self, key: str, value):
        """设置配置值"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        await self.save_config()
    
    def is_group_enabled(self, group_id: int) -> bool:
        """检查群组是否启用"""
        return group_id in self.config.get('enabled_groups', [])
    
    async def enable_group(self, group_id: int):
        """启用群组"""
        enabled_groups = self.config.get('enabled_groups', [])
        if group_id not in enabled_groups:
            enabled_groups.append(group_id)
            self.config['enabled_groups'] = enabled_groups
            await self.save_config()
    
    async def disable_group(self, group_id: int):
        """禁用群组"""
        enabled_groups = self.config.get('enabled_groups', [])
        if group_id in enabled_groups:
            enabled_groups.remove(group_id)
            self.config['enabled_groups'] = enabled_groups
            await self.save_config()
    
    def get_fake_user_config(self, group_id: int) -> Dict[str, Any]:
        """获取伪装用户配置"""
        fake_users = self.config.get('fake_users', {})
        group_key = str(group_id)

        if group_key not in fake_users:
            # 从人设配置创建默认配置
            character_based_config = self._create_character_based_config()
            fake_users[group_key] = character_based_config
            fake_users[group_key]['user_id'] = f"fake_{group_id}_{hash(str(group_id)) % 100000}"
            self.config['fake_users'] = fake_users

        return fake_users[group_key]

    def _create_character_based_config(self) -> Dict[str, Any]:
        """基于人设配置创建伪装用户配置"""
        if not self.character_config:
            return self.default_fake_user.copy()

        # 从人设配置中提取信息
        config = {
            "nickname": self.character_config.get('name', '煕'),
            "user_id": "fake_user",
            "personality": self._extract_personality(),
            "speaking_style": self._extract_speaking_style(),
            "activity_hours": list(range(8, 23)),  # 默认活跃时间
            "personality_traits": {
                "humor_level": 0.8,  # 根据人设，幽默程度较高
                "enthusiasm": 0.7,   # 活泼性格
                "formality": 0.2,    # 非正式，轻松随意
                "emoji_usage": 0.6   # 适度使用表情
            },
            "character_system": self.character_config.get('system', ''),
            "character_input": self.character_config.get('input', ''),
            "character_status": self.character_config.get('status', ''),
            "mute_keywords": self.character_config.get('mute_keyword', [])
        }

        return config

    def _extract_personality(self) -> str:
        """从人设配置中提取性格描述"""
        system = self.character_config.get('system', '')

        # 提取性格相关信息
        personality_parts = []

        if '性格特点：活泼、幽默、略带抽象' in system:
            personality_parts.append("活泼、幽默、略带抽象")

        if '高中生' in system:
            personality_parts.append("年轻有活力的高中生")

        if '编程、音乐、游戏' in system:
            personality_parts.append("热爱编程、音乐和游戏")

        return "、".join(personality_parts) if personality_parts else "友善、活泼的群友"

    def _extract_speaking_style(self) -> str:
        """从人设配置中提取说话风格"""
        system = self.character_config.get('system', '')

        style_parts = []

        if '简短精炼' in system:
            style_parts.append("简短精炼")

        if '活泼幽默' in system:
            style_parts.append("活泼幽默")

        if '网络流行语和梗' in system:
            style_parts.append("善用网络流行语和梗")

        if '保持简洁' in system:
            style_parts.append("回复简洁")

        return "、".join(style_parts) if style_parts else "轻松随意，偶尔使用网络用语"
    
    async def update_fake_user_config(self, group_id: int, config: Dict[str, Any]):
        """更新伪装用户配置"""
        fake_users = self.config.get('fake_users', {})
        group_key = str(group_id)
        
        if group_key in fake_users:
            fake_users[group_key].update(config)
        else:
            fake_users[group_key] = config
        
        self.config['fake_users'] = fake_users
        await self.save_config()
    
    def get_group_stats(self, group_id: int) -> Dict[str, Any]:
        """获取群组统计数据"""
        group_key = str(group_id)
        if group_key not in self.group_data:
            self.group_data[group_key] = {
                "total_replies": 0,
                "daily_replies": {},
                "last_reply_time": None,
                "message_count": 0,
                "active_hours": {},
                "popular_keywords": {},
                "created_time": datetime.now().isoformat()
            }
        return self.group_data[group_key]
    
    async def update_group_stats(self, group_id: int, stats: Dict[str, Any]):
        """更新群组统计数据"""
        group_key = str(group_id)
        current_stats = self.get_group_stats(group_id)
        current_stats.update(stats)
        self.group_data[group_key] = current_stats
        await self.save_group_data()
    
    async def increment_reply_count(self, group_id: int):
        """增加回复计数"""
        stats = self.get_group_stats(group_id)
        stats['total_replies'] += 1
        
        # 更新每日计数
        today = datetime.now().strftime('%Y-%m-%d')
        daily_replies = stats.get('daily_replies', {})
        daily_replies[today] = daily_replies.get(today, 0) + 1
        stats['daily_replies'] = daily_replies
        
        # 更新最后回复时间
        stats['last_reply_time'] = datetime.now().isoformat()
        
        await self.update_group_stats(group_id, stats)
    
    def get_daily_reply_count(self, group_id: int) -> int:
        """获取今日回复次数"""
        stats = self.get_group_stats(group_id)
        today = datetime.now().strftime('%Y-%m-%d')
        return stats.get('daily_replies', {}).get(today, 0)
    
    def is_within_daily_limit(self, group_id: int) -> bool:
        """检查是否在每日限制内"""
        max_daily = self.get_config('advanced_settings.max_daily_replies', 50)
        current_count = self.get_daily_reply_count(group_id)
        return current_count < max_daily
    
    def is_active_hour(self, group_id: int) -> bool:
        """检查当前是否为活跃时间"""
        fake_user = self.get_fake_user_config(group_id)
        activity_hours = fake_user.get('activity_hours', list(range(24)))
        current_hour = datetime.now().hour
        return current_hour in activity_hours
    
    def get_personality_adjusted_probability(self, group_id: int, base_probability: float) -> float:
        """根据性格特征调整回复概率"""
        fake_user = self.get_fake_user_config(group_id)
        traits = fake_user.get('personality_traits', {})
        
        # 根据热情程度调整
        enthusiasm = traits.get('enthusiasm', 0.5)
        adjusted_prob = base_probability * (0.5 + enthusiasm)
        
        # 根据活跃时间调整
        if self.get_config('advanced_settings.time_based_activity', True):
            if not self.is_active_hour(group_id):
                adjusted_prob *= 0.3  # 非活跃时间降低概率
        
        return min(adjusted_prob, 1.0)
    
    def export_config(self) -> Dict[str, Any]:
        """导出配置"""
        return {
            "config": self.config,
            "group_data": self.group_data,
            "export_time": datetime.now().isoformat()
        }
    
    async def import_config(self, data: Dict[str, Any]):
        """导入配置"""
        try:
            if "config" in data:
                self.config = self._merge_config(self.default_config, data["config"])
                await self.save_config()
            
            if "group_data" in data:
                self.group_data.update(data["group_data"])
                await self.save_group_data()
            
            _log.info("配置导入成功")
        except Exception as e:
            _log.error(f"配置导入失败: {e}")
            raise
