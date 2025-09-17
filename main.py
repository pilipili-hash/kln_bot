from ncatbot.core import BotClient
from ncatbot.core.message import GroupMessage, PrivateMessage

from utils.config_manager import load_config
# _log = get_log()

# 创建机器人客户端
bot = BotClient()
load_config()  # 加载全局配置
# @bot.group_event()
# async def on_group_message(msg: GroupMessage):
#     _log.info(msg)
# #     if msg.raw_message == "测试":
# #         await msg.reply(text="NcatBot 测试成功喵~")


# # @bot.private_event()
# # async def on_private_message(msg: PrivateMessage):
# #     _log.info(msg)
# #     if msg.raw_message == "测试":
# #         await bot.api.post_private_msg(msg.user_id, text="NcatBot 测试成功喵~")


if __name__ == "__main__":
    bot.run(enable_webui_interaction=False)
   
   