import os
import json
import random
import asyncio
import logging
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, At, Text, Image
from utils.onebot_v11_handler import extract_images
from utils.cq_to_onebot import remove_cq_codes

# 导入自定义模块
from .emoji_manager import EmojiManager
from .ai_integration import AIIntegration
from .config_manager import ConfigManager

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment  # 兼容回调函数注册器

class FakeChat(BasePlugin):
    name = "FakeChat"  # 插件名称
    version = "1.0.0"  # 插件版本

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        self.data_dir = "data/fakechat"
        self.emoji_dir = "data/fakechat/emojis"
        self.config_file = "data/fakechat/config.json"
        self.group_data_file = "data/fakechat/group_data.json"
        self.emoji_data_file = "data/fakechat/emoji_data.json"
        
        # 默认配置
        self.default_config = {
            "enabled_groups": [],  # 启用的群组
            "reply_probability": 0.1,  # 回复概率 (0.0-1.0)
            "emoji_probability": 0.3,  # 发送表情的概率
            "max_reply_length": 200,  # 最大回复长度
            "cooldown_seconds": 30,  # 冷却时间
            "fake_users": {},  # 伪装用户配置
            "trigger_keywords": ["好的", "是的", "哈哈", "笑死", "确实"],  # 触发关键词
            "blacklist_keywords": ["管理", "踢人", "禁言"]  # 黑名单关键词
        }
        
        # 运行时数据
        self.fake_config = {}
        self.group_data = {}
        self.last_reply_time = {}  # 群组最后回复时间

        # 模块实例
        self.config_manager = ConfigManager(self.data_dir)
        self.emoji_manager = EmojiManager(self.data_dir)
        self.ai_integration = AIIntegration()

    async def on_load(self):
        """插件加载时的初始化逻辑"""
        try:
            # 创建数据目录
            os.makedirs(self.data_dir, exist_ok=True)
            os.makedirs(self.emoji_dir, exist_ok=True)
            
            # 初始化模块
            await self.config_manager.load_config()
            await self.config_manager.load_group_data()
            await self.emoji_manager.load_emoji_data()
            ai_init_success = await self.ai_integration.initialize(self.api)

            # 更新配置引用
            self.fake_config = self.config_manager.config
            
            _log.info(f"FakeChat v{self.version} 插件已加载")
            _log.info(f"已启用群组: {len(self.fake_config.get('enabled_groups', []))}")

            # 获取表情库统计
            emoji_stats = self.emoji_manager.get_statistics()
            _log.info(f"表情库数量: {emoji_stats['total_count']}")
            _log.info(f"AI集成状态: {'成功' if ai_init_success else '失败'}")
            
        except Exception as e:
            _log.error(f"FakeChat插件加载失败: {e}")



    def _is_group_enabled(self, group_id: int) -> bool:
        """检查群组是否启用了伪装功能"""
        return group_id in self.fake_config.get('enabled_groups', [])

    def _is_in_cooldown(self, group_id: int) -> bool:
        """检查是否在冷却时间内"""
        if group_id not in self.last_reply_time:
            return False
        
        cooldown = self.fake_config.get('cooldown_seconds', 30)
        last_time = self.last_reply_time[group_id]
        return (datetime.now() - last_time).total_seconds() < cooldown

    def _should_reply(self, message: str) -> bool:
        """判断是否应该回复"""
        # 检查黑名单关键词
        blacklist = self.fake_config.get('blacklist_keywords', [])
        if any(keyword in message for keyword in blacklist):
            return False

        # 检查触发关键词
        trigger_keywords = self.fake_config.get('trigger_keywords', [])
        has_trigger = any(keyword in message for keyword in trigger_keywords)

        # 基础概率 + 触发关键词加成
        base_prob = self.fake_config.get('reply_probability', 0.1)
        if has_trigger:
            base_prob *= 2  # 触发关键词时概率翻倍
        
        return random.random() < base_prob

    async def _get_fake_user_info(self, group_id: int) -> Dict[str, Any]:
        """获取伪装用户信息"""
        return self.config_manager.get_fake_user_config(group_id)

    @bot.group_event()
    async def on_group_message(self, msg: GroupMessage):
        """处理群消息事件"""
        try:
            group_id = msg.group_id
            raw_message = msg.raw_message.strip()
            
            # 检查是否为管理命令
            if await self._handle_admin_commands(msg):
                return
            
            # 检查是否为添加表情命令
            if await self._handle_emoji_commands(msg):
                return
            
            # 检查群组是否启用
            if not self._is_group_enabled(group_id):
                return
            
            # 检查冷却时间
            if self._is_in_cooldown(group_id):
                return
            
            # 过滤掉机器人自己的消息
            if msg.user_id == msg.self_id:
                return
            
            # 判断是否应该回复
            clean_message = remove_cq_codes(raw_message)
            if not self._should_reply(clean_message):
                return
            
            # 生成伪装回复
            await self._generate_fake_reply(msg)
            
        except Exception as e:
            _log.error(f"处理群消息失败: {e}")

    async def _handle_admin_commands(self, msg: GroupMessage) -> bool:
        """处理管理员命令"""
        raw_message = msg.raw_message.strip()
        group_id = msg.group_id

        # 只对管理命令进行权限检查
        if not raw_message.startswith("/伪装"):
            return False

        # 检查管理员权限
        try:
            from utils.config_manager import get_config
            master_list = get_config("master", [])
            if msg.user_id not in master_list:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 权限不足，只有管理员可以使用伪装功能",
                    reply=msg.message_id
                )
                return True  # 返回True表示已处理，阻止继续执行
        except Exception as e:
            _log.warning(f"权限检查失败: {e}")
            # 如果权限检查失败，允许所有用户使用（降级处理）
            pass
        
        if raw_message.startswith("/伪装"):
            parts = raw_message.split()
            if len(parts) < 2:
                await self.api.post_group_msg(
                    group_id,
                    text="🎭 伪装群友聊天插件\n\n📝 管理命令：\n• /伪装 启用 - 启用当前群组\n• /伪装 禁用 - 禁用当前群组\n• /伪装 状态 - 查看当前状态\n• /伪装 概率 <0.0-1.0> - 设置回复概率\n• /伪装 帮助 - 显示帮助信息\n\n🖼️ 表情命令：\n• /添加表情 [图片] - 添加表情到表情库\n• /分析图片 [图片] - AI分析图片并添加到表情库\n• /表情列表 - 查看表情库统计",
                    reply=msg.message_id
                )
                return True
            
            command = parts[1]
            
            if command == "启用":
                if not self.config_manager.is_group_enabled(group_id):
                    await self.config_manager.enable_group(group_id)
                    self.fake_config = self.config_manager.config  # 更新配置引用
                    await self.api.post_group_msg(group_id, text="✅ 伪装功能已启用", reply=msg.message_id)
                else:
                    await self.api.post_group_msg(group_id, text="⚠️ 伪装功能已经启用", reply=msg.message_id)

            elif command == "禁用":
                if self.config_manager.is_group_enabled(group_id):
                    await self.config_manager.disable_group(group_id)
                    self.fake_config = self.config_manager.config  # 更新配置引用
                    await self.api.post_group_msg(group_id, text="❌ 伪装功能已禁用", reply=msg.message_id)
                else:
                    await self.api.post_group_msg(group_id, text="⚠️ 伪装功能已经禁用", reply=msg.message_id)
                    
            elif command == "状态":
                enabled = self.config_manager.is_group_enabled(group_id)
                status = "启用" if enabled else "禁用"
                prob = self.fake_config.get('reply_probability', 0.1)
                emoji_stats = self.emoji_manager.get_statistics()
                daily_count = self.config_manager.get_daily_reply_count(group_id)

                status_text = f"🎭 伪装功能状态：{status}\n📊 回复概率：{prob:.1%}\n🖼️ 表情库：{emoji_stats['total_count']}个\n⏰ 冷却时间：{self.fake_config.get('cooldown_seconds', 30)}秒\n📈 今日回复：{daily_count}次"
                await self.api.post_group_msg(group_id, text=status_text, reply=msg.message_id)
                
            elif command == "概率" and len(parts) >= 3:
                try:
                    prob = float(parts[2])
                    if 0.0 <= prob <= 1.0:
                        await self.config_manager.set_config('reply_probability', prob)
                        self.fake_config = self.config_manager.config  # 更新配置引用
                        await self.api.post_group_msg(group_id, text=f"✅ 回复概率已设置为 {prob:.1%}", reply=msg.message_id)
                    else:
                        await self.api.post_group_msg(group_id, text="❌ 概率值必须在 0.0-1.0 之间", reply=msg.message_id)
                except ValueError:
                    await self.api.post_group_msg(group_id, text="❌ 无效的概率值", reply=msg.message_id)
                    
            return True

        return False

    async def _handle_emoji_commands(self, msg: GroupMessage) -> bool:
        """处理表情相关命令"""
        raw_message = msg.raw_message.strip()
        group_id = msg.group_id

        if raw_message.startswith("/添加表情"):
            # 提取图片
            image_urls = extract_images(msg)

            if not image_urls:
                await self.api.post_group_msg(
                    group_id,
                    text="📷 请发送包含图片的消息来添加表情\n💡 例如：/添加表情 [图片]",
                    reply=msg.message_id
                )
                return True

            # 保存表情
            saved_count = 0
            for image_url in image_urls:
                # 使用AI分析图片描述
                description = await self.ai_integration.analyze_image_for_emoji(image_url)
                emoji_id = await self.emoji_manager.add_emoji_from_url(image_url, msg.user_id, description)
                if emoji_id:
                    saved_count += 1

            if saved_count > 0:
                await self.api.post_group_msg(
                    group_id,
                    text=f"✅ 成功添加 {saved_count} 个表情到表情库！\n🎯 AI会智能选择合适的表情进行回复",
                    reply=msg.message_id
                )
            else:
                await self.api.post_group_msg(
                    group_id,
                    text="❌ 表情保存失败，请稍后重试",
                    reply=msg.message_id
                )
            return True

        elif raw_message == "/表情列表":
            emoji_stats = self.emoji_manager.get_statistics()
            if emoji_stats['total_count'] == 0:
                await self.api.post_group_msg(
                    group_id,
                    text="📭 表情库为空\n💡 使用 /添加表情 [图片] 来添加表情",
                    reply=msg.message_id
                )
            else:
                category_text = "\n".join([f"• {cat}: {count}个" for cat, count in emoji_stats['categories'].items()])

                await self.api.post_group_msg(
                    group_id,
                    text=f"🖼️ 表情库统计\n📊 总数：{emoji_stats['total_count']}个\n💾 总大小：{emoji_stats['total_size_mb']}MB\n📈 总使用：{emoji_stats['total_usage']}次\n\n📂 分类统计：\n{category_text}",
                    reply=msg.message_id
                )
            return True

        return False

    async def _generate_fake_reply(self, msg: GroupMessage):
        """生成伪装回复"""
        try:
            group_id = msg.group_id
            clean_message = remove_cq_codes(msg.raw_message)

            # 获取伪装用户信息
            fake_user = await self._get_fake_user_info(group_id)

            # 决定回复类型：纯文本、纯表情、文本+表情
            reply_type = self._decide_reply_type()

            reply_content = []

            if reply_type in ["text", "text_emoji"]:
                # 使用AI集成生成回复，传入API以获取聊天记录
                ai_response = await self.ai_integration.generate_response(group_id, clean_message, fake_user, self.api)
                if ai_response:
                    reply_content.append({"type": "text", "data": {"text": ai_response}})

            if reply_type in ["emoji", "text_emoji"]:
                # 选择合适的表情
                emoji_path = await self._select_appropriate_emoji(clean_message)
                if emoji_path:
                    # 确保路径格式正确，兼容不同OneBot实现
                    if os.path.isabs(emoji_path):
                        # 如果已经是绝对路径，直接使用
                        file_path = emoji_path
                    else:
                        # 如果是相对路径，转换为绝对路径
                        file_path = os.path.abspath(emoji_path)

                    # 标准化路径分隔符（Windows兼容性）
                    file_path = file_path.replace('\\', '/')

                    reply_content.append({"type": "image", "data": {"file": file_path}})

            # 发送回复
            if reply_content:
                await self._send_fake_message(group_id, reply_content, fake_user)

                # 更新最后回复时间和统计
                self.last_reply_time[group_id] = datetime.now()
                await self.config_manager.increment_reply_count(group_id)

                _log.info(f"发送伪装回复: 群{group_id}, 类型{reply_type}")

        except Exception as e:
            _log.error(f"生成伪装回复失败: {e}")

    def _decide_reply_type(self) -> str:
        """决定回复类型"""
        emoji_prob = self.fake_config.get('emoji_probability', 0.3)

        rand = random.random()
        if rand < emoji_prob * 0.3:  # 30%概率纯表情
            return "emoji"
        elif rand < emoji_prob:  # 剩余概率文本+表情
            return "text_emoji"
        else:  # 其余纯文本
            return "text"



    async def _select_appropriate_emoji(self, message: str) -> Optional[str]:
        """选择合适的表情"""
        try:
            # 分析消息情感，选择对应分类的表情
            message_lower = message.lower()

            # 情感关键词映射
            emotion_mapping = {
                "开心": ["哈", "笑", "好", "棒", "赞", "爽", "开心"],
                "难过": ["难过", "伤心", "哭", "悲", "惨"],
                "愤怒": ["气", "怒", "烦", "讨厌", "恶心"],
                "惊讶": ["哇", "天", "震惊", "不敢相信"],
                "疑惑": ["?", "？", "什么", "为什么", "怎么"],
                "无语": ["无语", "醉了", "服了", "汗"],
                "赞同": ["对", "是", "确实", "同意", "支持"]
            }

            # 找到匹配的情感分类
            target_category = "其他"
            for category, keywords in emotion_mapping.items():
                if any(keyword in message_lower for keyword in keywords):
                    target_category = category
                    break

            # 使用表情管理器选择表情
            emoji_id = self.emoji_manager.get_random_emoji(target_category)
            if not emoji_id:
                # 如果没有匹配的分类，先尝试从"其他"分类选择
                emoji_id = self.emoji_manager.get_random_emoji("其他")
            if not emoji_id:
                # 如果"其他"分类也没有，随机选择任意表情
                emoji_id = self.emoji_manager.get_random_emoji()

            if emoji_id:
                # 更新使用次数
                self.emoji_manager.update_usage_count(emoji_id)
                await self.emoji_manager.save_emoji_data()

                return self.emoji_manager.get_emoji_file_path(emoji_id)

        except Exception as e:
            _log.error(f"选择表情失败: {e}")

        return None

    async def _send_fake_message(self, group_id: int, content: List[Dict], fake_user: Dict):
        """发送伪装消息"""
        try:
            # 简化消息发送逻辑，直接发送普通消息
            text_parts = []
            image_files = []

            # 分离文本和图片内容
            for item in content:
                if item["type"] == "text":
                    text_parts.append(item["data"]["text"])
                elif item["type"] == "image":
                    image_files.append(item["data"]["file"])

            # 发送文本消息
            if text_parts:
                text_content = " ".join(text_parts)
                try:
                    await self.api.post_group_msg(group_id=group_id, text=text_content)
                except Exception as text_error:
                    _log.warning(f"发送文本消息失败: {text_error}")

            # 发送图片消息
            for image_file in image_files:
                try:
                    # 尝试不同的图片发送方式，兼容不同OneBot实现
                    success = False

                    # 尝试多种图片发送方式
                    methods = [
                        lambda: self.api.post_group_msg(group_id=group_id, image=image_file),
                        lambda: self.api.post_group_msg(group_id=group_id, image=f"file://{image_file}"),
                        lambda: self._send_image_as_base64(group_id, image_file)
                    ]

                    for method in methods:
                        try:
                            await method()
                            success = True
                            break
                        except Exception:
                            continue

                    if not success:
                        _log.warning(f"图片发送失败: {image_file}")

                    if success:
                        _log.info(f"表情发送成功: {os.path.basename(image_file)}")

                except Exception as img_error:
                    _log.warning(f"发送图片失败: {img_error}")

        except Exception as e:
            _log.error(f"发送伪装消息失败: {e}")

    async def _send_image_as_base64(self, group_id: int, image_file: str):
        """使用base64编码发送图片"""
        import base64
        with open(image_file, 'rb') as f:
            image_data = f.read()
            base64_data = base64.b64encode(image_data).decode()
            await self.api.post_group_msg(group_id=group_id, image=f"base64://{base64_data}")

# 注册插件
plugin = FakeChat()
