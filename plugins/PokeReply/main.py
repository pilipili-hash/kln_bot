from typing import Optional
import os

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.utils.config import config
from ncatbot.core.message import GroupMessage
from .pokeData import (
    init_db, add_poke_reply, get_random_poke_reply,
    get_all_poke_replies, delete_poke_reply, generate_replies_image
)

bot = CompatibleEnrollment

class PokeReply(BasePlugin):
    """戳一戳回复插件 - 管理群组戳一戳自动回复内容"""

    name = "PokeReply"
    version = "1.0.0"

    async def on_load(self):
        """插件加载时初始化"""
        await init_db()
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    @bot.group_event()
    async def on_message(self, event: GroupMessage):
        """处理群消息事件"""
        message = event.raw_message.strip()
        group_id = event.group_id

        # 戳一戳帮助命令
        if message == "/cyc帮助" or message == "/戳一戳帮助":
            await self._send_help(group_id)
            return

        # 添加戳一戳回复
        if message.startswith("/添加cyc"):
            await self._handle_add_reply(group_id, message)
            return

        # 查询戳一戳回复列表
        if message.startswith("/查询cyc"):
            await self._handle_query_replies(group_id)
            return

        # 删除戳一戳回复
        if message.startswith("/删除cyc"):
            await self._handle_delete_reply(group_id, message)
            return

    async def _send_help(self, group_id: int):
        """发送帮助信息"""
        help_text = """🎯 戳一戳回复插件使用说明

📝 管理命令：
• /添加cyc <内容> - 添加戳一戳回复内容
• /查询cyc - 查看当前群组所有戳一戳回复
• /删除cyc <序号> - 删除指定序号的回复内容
• /cyc帮助 - 显示此帮助信息

🎮 使用方式：
1. 戳一戳机器人，随机回复已添加的内容
2. 支持文字和图片回复
3. 每个群组独立管理回复内容

💡 使用示例：
/添加cyc 你好呀！
/添加cyc [CQ:image,file=xxx.jpg]
/查询cyc
/删除cyc 1

⚠️ 注意事项：
• 回复内容支持CQ码格式
• 删除时请使用查询显示的序号
• 每个群组的回复内容相互独立"""

        await self.api.post_group_msg(group_id=group_id, text=help_text)

    async def _handle_add_reply(self, group_id: int, message: str):
        """处理添加回复命令"""
        content = message[len("/添加cyc"):].strip()

        if not content:
            await self.api.post_group_msg(
                group_id=group_id,
                text="❌ 请提供要添加的内容！\n使用方法：/添加cyc <回复内容>"
            )
            return

        try:
            await add_poke_reply(group_id, content)
            await self.api.post_group_msg(
                group_id=group_id,
                text="✅ 戳一戳回复添加成功！"
            )
        except Exception as e:
            await self.api.post_group_msg(
                group_id=group_id,
                text=f"❌ 添加失败：{str(e)}"
            )

    async def _handle_query_replies(self, group_id: int):
        """处理查询回复列表命令"""
        try:
            replies = await get_all_poke_replies(group_id)
            if not replies:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text="📝 当前群组暂无戳一戳回复内容！\n使用 /添加cyc <内容> 来添加回复。"
                )
                return

            image_path = await generate_replies_image(replies)
            await self.api.post_group_msg(
                group_id=group_id,
                image=image_path
            )
            # 发送后删除临时图片
            if os.path.exists(image_path):
                os.remove(image_path)

        except Exception as e:
            await self.api.post_group_msg(
                group_id=group_id,
                text=f"❌ 查询失败：{str(e)}"
            )

    async def _handle_delete_reply(self, group_id: int, message: str):
        """处理删除回复命令"""
        try:
            index_str = message[len("/删除cyc"):].strip()
            if not index_str:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text="❌ 请提供要删除的序号！\n使用方法：/删除cyc <序号>"
                )
                return

            index = int(index_str)
            if index < 1:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text="❌ 序号必须大于0！"
                )
                return

            success = await delete_poke_reply(group_id, index)
            if success:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text=f"✅ 成功删除第 {index} 条戳一戳回复！"
                )
            else:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text=f"❌ 删除失败：序号 {index} 不存在或无效。"
                )

        except ValueError:
            await self.api.post_group_msg(
                group_id=group_id,
                text="❌ 序号格式错误！请输入数字，例如：/删除cyc 1"
            )
        except Exception as e:
            await self.api.post_group_msg(
                group_id=group_id,
                text=f"❌ 删除失败：{str(e)}"
            )   
            
    @bot.notice_event()
    async def on_group_poke(self, event):
        """处理戳一戳事件"""
        try:
            # 检查是否为戳一戳事件
            if event.get("sub_type") != "poke":
                return

            bot_qq = config.bt_uin
            target_id = event.get("target_id")
            group_id = event.get("group_id")

            # 检查是否戳的是机器人
            if not target_id or int(target_id) != int(bot_qq):
                return

            if not group_id:
                return

            # 获取随机回复
            reply = await get_random_poke_reply(group_id)
            if reply:
                # 使用标准API发送消息
                await self.api.post_group_msg(
                    group_id=group_id,
                    text=reply
                )
            else:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text="🎯 暂无戳一戳回复内容！\n使用 /添加cyc <内容> 来添加回复，或发送 /cyc帮助 查看使用说明。"
                )

        except Exception:
            # 静默处理错误，避免影响其他功能
            pass

