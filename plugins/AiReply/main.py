import os
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from AiReply.message_db import OpenAIContextManager  # 导入上下文管理器
from PluginManager.plugin_manager import master_required  # 导入管理员检查装饰器

bot = CompatibleEnrollment  # 兼容回调函数注册器


class AiReply(BasePlugin):
    name = "AiReply"  # 插件名称
    version = "0.0.1"  # 插件版本

    @bot.group_event()
    @master_required(commands=["/修改设定", "/清空上下文"])# 检查是否为管理员
    async def on_group_event(self, msg: GroupMessage):
        """
        处理群消息事件
        """
        group_id = msg.group_id
        raw_message = msg.raw_message
        try:
            # 检查是否为修改设定命令
            if raw_message.strip().startswith("/修改设定"):
                new_setting = raw_message.strip()[len("/修改设定"):].strip()
                if new_setting:
                    await self.context_manager.save_setting(group_id, new_setting)
                    await self.api.post_group_msg(group_id, text=f"设定已更新", reply=msg.message_id)
                return  # 处理完设定修改后直接返回

            # 检查是否为清空上下文命令
            if raw_message.strip().startswith("/清空上下文"):
                await self.context_manager.clear_context(group_id)
                await self.api.post_group_msg(group_id, text="上下文已清空", reply=msg.message_id)
                return  # 处理完清空上下文后直接返回

            # 检查是否被 @ 或以“机器人”开头
            is_at = f"[CQ:at,qq={msg.self_id}]" in raw_message
            is_start_with_robot = raw_message.startswith("机器人")
            is_start_with_bot_name = raw_message.startswith(self.bot_name)
            if is_at or is_start_with_robot or is_start_with_bot_name:
                # 提取用户输入的内容
                reply_text = raw_message.replace(f"[CQ:at,qq={msg.self_id}]", "").replace("机器人", "").replace(self.bot_name, "").strip()
                if not reply_text:
                    return  # 如果没有内容，不处理

                # 检查是否以“联网”开头
                use_search_model = reply_text.startswith("联网")
                if use_search_model:
                    reply_text = reply_text[len("联网"):].strip()

                # 调用 OpenAIContextManager 获取回复
                response = await self.context_manager.get_openai_reply(group_id, reply_text, use_search_model)
                if response:
                    await self.api.post_group_msg(group_id, text=response, reply=msg.message_id)
        except Exception as e:
            print(f"[ERROR] 处理消息时出错: {e}")

    async def on_load(self):
        """
        插件加载时的初始化逻辑
        """
        self.context_manager = OpenAIContextManager()  # 初始化上下文管理器
        await self.context_manager._initialize_database()  # 确保表已创建
        self.bot_name = self.context_manager.bot_name
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")