from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.utils.config import config
from .pokeData import *
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_msg_cq # 添加依赖
import os
bot = CompatibleEnrollment

class PokeReply(BasePlugin):
    name = "PokeReply"  # 插件名称
    version = "1.0.0"   # 插件版本

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        await init_db()  # 初始化数据库

    @bot.group_event()
    async def on_message(self, event: GroupMessage):
        """处理用户发送的消息"""
        message = event.raw_message
        group_id = event.group_id
        user_id = event.user_id

        if message.startswith("/添加cyc"):
            content = message[len("/添加cyc"):].strip()
            print(content)
            if content:
                await add_poke_reply(group_id, content)
                await send_group_msg_cq(
                    group_id,
                    "添加成功"
                )
            else:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text="请提供要添加的内容，例如：/添加cyc 你好！"
                )

        elif message.startswith("/查询cyc"):
            replies = await get_all_poke_replies(group_id)
            if replies:
                image_path = await generate_replies_image(replies)
                await self.api.post_group_msg(
                    group_id=group_id,
                    image=image_path
                )
                os.remove(image_path)  # 发送后删除临时图片
            else:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text="当前群暂无戳一戳回复内容！"
                )
        elif message.startswith("/删除cyc"):
            try:
                # 提取序号
                index = int(message[len("/删除cyc"):].strip())
                success = await delete_poke_reply(group_id, index)
                if success:
                    await send_group_msg_cq(
                        group_id,
                        f"成功删除第 {index} 条戳一戳内容。"
                    )
                else:
                    await self.api.post_group_msg(
                        group_id=group_id,
                        text=f"删除失败：序号 {index} 无效或不存在。"
                    )
            except ValueError:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text="输入格式错误，请输入 '/删除cyc<序号>' 以删除对应内容。"
                )        
    @bot.notice_event()
    async def on_group_poke(self, event):
        """处理戳一戳事件"""
        bot_qq = config.bt_uin

        # 检测是否为戳一戳事件，并且目标是机器人
        if event.get("sub_type") == "poke" and int(event.get("target_id")) == int(bot_qq):
            group_id = event.get("group_id")
            if group_id:
                reply = await get_random_poke_reply(group_id)
                if reply:
                    await send_group_msg_cq(
                        group_id,
                        reply
                    )
                else:
                    await self.api.post_group_msg(
                        group_id=group_id,
                        text="暂无戳一戳回复内容，请使用 /添加cyc 添加！"
                    )

