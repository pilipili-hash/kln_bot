from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from .niuniu_utils import (
    init_database,
    register_player,
    apply_glue,
    jj_battle,
    use_item,
    query_player
)

class PassionateCowPlugin(BasePlugin):
    name = "PassionateCowPlugin"
    version = "1.0.0"

    async def on_load(self):
        """插件加载时初始化数据库"""
        await init_database("data.db")
        print(f"{self.name} 插件已加载")

    @CompatibleEnrollment.group_event()
    async def on_group_message(self, msg: GroupMessage):
        """处理群聊消息"""
        if msg.raw_message.startswith("注册牛子"):
            await register_player("data.db", msg, self)
        elif msg.raw_message.startswith("打胶"):
            await apply_glue("data.db", msg, self)
        elif msg.raw_message.startswith("jj"):
            await jj_battle("data.db", msg, self)
        elif msg.raw_message.startswith("使用道具"):
            await use_item("data.db", msg, self)
        elif msg.raw_message.startswith("我的牛子"):
            await query_player("data.db", msg, self)