from typing import Dict, List, Optional
from functools import wraps

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .message_db import OpenAIContextManager
from utils.cq_to_onebot import extract_at_users, remove_cq_codes
from utils.onebot_v11_handler import extract_images

# 导入管理员检查装饰器
try:
    from PluginManager.plugin_manager import master_required
except ImportError:
    def master_required(commands=None):
        """简单的装饰器替代版本"""
        def decorator(func):
            @wraps(func)
            async def wrapper(self, *args, **kwargs):
                return await func(self, *args, **kwargs)
            return wrapper
        return decorator

bot = CompatibleEnrollment  # 兼容回调函数注册器

class AiReply(BasePlugin):
    name = "AiReply"  # 插件名称
    version = "0.0.1"  # 插件版本

    @bot.group_event()
    async def on_group_event(self, msg: GroupMessage):
        """
        处理群消息事件
        """
        group_id = msg.group_id
        raw_message = msg.raw_message
        try:
            # 管理员命令列表
            admin_commands = ["/修改设定", "/清空上下文", "/查看设定", "/ai帮助"]

            # 检查是否为管理员命令
            is_admin_command = any(raw_message.strip().startswith(cmd) for cmd in admin_commands)

            if is_admin_command:
                # 检查管理员权限
                try:
                    from utils.config_manager import get_config
                    master_list = get_config("master", [])
                    if msg.user_id not in master_list:
                        await self.api.post_group_msg(group_id, text="您没有权限执行此操作", reply=msg.message_id)
                        return
                except Exception as e:
                    print(f"[ERROR] 权限检查失败: {e}")
                    return

            # 检查是否为修改设定命令
            if raw_message.strip().startswith("/修改设定"):
                new_setting = raw_message.strip()[len("/修改设定"):].strip()

                # 验证设定内容
                if not new_setting:
                    await self.api.post_group_msg(group_id, text="❌ 设定内容不能为空！\n请使用：/修改设定 <设定内容>", reply=msg.message_id)
                    return

                if len(new_setting) > 1000:  # 限制设定长度
                    await self.api.post_group_msg(group_id, text="❌ 设定内容过长！请限制在1000字符以内。", reply=msg.message_id)
                    return

                # 保存设定
                success = await self.context_manager.save_setting(group_id, new_setting)
                if success:
                    await self.api.post_group_msg(group_id, text=f"✅ 设定已更新成功！\n新设定：{new_setting[:50]}{'...' if len(new_setting) > 50 else ''}", reply=msg.message_id)
                else:
                    await self.api.post_group_msg(group_id, text="❌ 设定保存失败，请稍后重试。", reply=msg.message_id)
                return  # 处理完设定修改后直接返回

            # 检查是否为清空上下文命令
            if raw_message.strip().startswith("/清空上下文"):
                success = await self.context_manager.clear_context(group_id)
                if success:
                    await self.api.post_group_msg(group_id, text="✅ 上下文已清空", reply=msg.message_id)
                else:
                    await self.api.post_group_msg(group_id, text="❌ 清空上下文失败，请稍后重试。", reply=msg.message_id)
                return  # 处理完清空上下文后直接返回

            # 检查是否为查看设定命令
            if raw_message.strip() == "/查看设定":
                current_setting = await self.context_manager.get_setting(group_id)
                await self.api.post_group_msg(group_id, text=f"📋 当前群组设定：\n{current_setting}", reply=msg.message_id)
                return

            # 检查是否为帮助命令
            if raw_message.strip() == "/ai帮助":
                help_text = """🤖 AI回复插件使用说明：

📝 管理员命令：
• /修改设定 <内容> - 修改AI角色设定
• /查看设定 - 查看当前AI设定
• /清空上下文 - 清空对话历史
• /ai帮助 - 显示此帮助信息

💬 对话方式：
• @机器人 <消息> - 普通对话
• 机器人 <消息> - 普通对话
• @机器人 联网 <消息> - 联网搜索回答
• @机器人 <消息> + 图片 - 结合文字和图片进行对话

🖼️ 图片分析功能：
• /分析图片 [附带图片] - 专门的图片分析命令
• /分析图片 <问题> [附带图片] - 针对图片提出具体问题
• /分析图片 - 等待模式，发送命令后再发送图片
• @机器人 + 图片 - 可以同时发送文字和图片进行更详细的询问
• 支持多张图片同时分析
• /取消 - 取消等待中的图片分析

⚡ 使用示例：
/修改设定 你是一个可爱的猫娘，说话要加上"喵~"
@机器人 今天天气怎么样？
@机器人 联网 今天有什么新闻？
@机器人 这张图片里有什么？[附带图片]
/分析图片 [附带图片] - 专门分析图片
/分析图片 这是什么动物？[附带图片] - 针对图片提问
/分析图片 → [发送图片] - 等待模式分析"""
                await self.api.post_group_msg(group_id, text=help_text, reply=msg.message_id)
                return

            # 检查是否为图片分析命令
            if raw_message.strip().startswith("/分析图片"):
                # 从消息中提取图片
                image_urls = extract_images(msg)

                if image_urls:
                    # 获取命令后的文本（如果有）
                    command_text = raw_message.strip()[len("/分析图片"):].strip()
                    if not command_text:
                        command_text = "请详细分析这张图片的内容。"

                    # 调用AI分析图片
                    response = await self.context_manager.get_openai_reply(
                        group_id, command_text, False, image_urls
                    )
                    if response:
                        await self.api.post_group_msg(group_id, text=response, reply=msg.message_id)
                else:
                    # 没有图片，等待用户发送图片
                    command_text = raw_message.strip()[len("/分析图片"):].strip()
                    self.pending_image_analysis[group_id] = {
                        'user_id': msg.user_id,
                        'command_text': command_text if command_text else "请详细分析这张图片的内容。"
                    }
                    await self.api.post_group_msg(
                        group_id,
                        text="📷 请发送要分析的图片，或发送 /取消 取消分析。",
                        reply=msg.message_id
                    )
                return

            # 处理取消图片分析（优先处理取消命令）
            if raw_message.strip() == "/取消" and group_id in self.pending_image_analysis:
                if self.pending_image_analysis[group_id]['user_id'] == msg.user_id:
                    del self.pending_image_analysis[group_id]
                    await self.api.post_group_msg(group_id, text="✅ 已取消图片分析。", reply=msg.message_id)
                return

            # 处理等待中的图片分析请求
            if group_id in self.pending_image_analysis and self.pending_image_analysis[group_id]['user_id'] == msg.user_id:
                image_urls = extract_images(msg)

                if image_urls:
                    # 找到图片，执行分析
                    command_text = self.pending_image_analysis[group_id]['command_text']
                    del self.pending_image_analysis[group_id]

                    response = await self.context_manager.get_openai_reply(
                        group_id, command_text, False, image_urls
                    )
                    if response:
                        await self.api.post_group_msg(group_id, text=response, reply=msg.message_id)
                else:
                    # 仍然没有图片
                    await self.api.post_group_msg(
                        group_id,
                        text="❌ 请发送包含图片的消息，或发送 /取消 取消分析。",
                        reply=msg.message_id
                    )
                return

            # 检查是否被 @ 或包含机器人关键词
            at_users = extract_at_users(raw_message)
            is_at = str(msg.self_id) in at_users
            is_start_with_robot = raw_message.startswith("机器人")
            is_start_with_bot_name = raw_message.startswith(self.bot_name)
            # 检查是否包含机器人名字（如"小黑在吗"、"小黑你好"等）
            contains_bot_name = self.bot_name in raw_message

            # 提取消息中的图片
            image_urls = extract_images(msg)

            # 检查是否需要AI回复（被@、以机器人开头、或包含机器人名字）
            should_reply = is_at or is_start_with_robot or is_start_with_bot_name or contains_bot_name

            if should_reply:
                # 检查智能聊天功能是否启用
                if not await self._is_feature_enabled(group_id, "智能聊天"):
                    return  # 功能未启用，不处理
                # 提取用户输入的内容，移除CQ码和关键词
                reply_text = remove_cq_codes(raw_message).replace("机器人", "").replace(self.bot_name, "").strip()

                # 如果没有文本但有图片，设置默认提示
                if not reply_text and image_urls:
                    reply_text = ""  # 让AI自动分析图片
                elif not reply_text and not image_urls:
                    return  # 如果既没有文本也没有图片，不处理

                # 检查是否以"联网"开头
                use_search_model = reply_text.startswith("联网")
                if use_search_model:
                    reply_text = reply_text[len("联网"):].strip()

                # 调用 OpenAIContextManager 获取回复，传入图片URL
                response = await self.context_manager.get_openai_reply(
                    group_id, reply_text, use_search_model, image_urls
                )
                if response:
                    await self.api.post_group_msg(group_id, text=response, reply=msg.message_id)
        except Exception as e:
            # 静默处理错误，避免日志污染
            pass

    async def _is_feature_enabled(self, group_id: int, feature_name: str) -> bool:
        """检查功能是否启用"""
        try:
            from PluginManager.plugin_manager import is_feature_enabled
            return await is_feature_enabled(group_id, feature_name)
        except Exception:
            return True  # 出错时默认启用

    async def on_load(self):
        """插件加载时的初始化逻辑"""
        self.context_manager = OpenAIContextManager()
        await self.context_manager._initialize_database()
        self.bot_name = self.context_manager.bot_name
        self.pending_image_analysis = {}
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")