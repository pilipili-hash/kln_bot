from ncatbot.core import BotClient
from ncatbot.core.message import GroupMessage, PrivateMessage
from ncatbot.utils.config import config
from utils.config_manager import load_config
# from ncatbot.utils.logger import get_log

# _log = get_log()

config.set_bot_uin("")  # 设置 bot qq 号 (必填)
config.set_ws_uri("ws://localhost:3001")  # 设置 napcat websocket server 地址
# config.set_token("napcat") # 设置 token (napcat 服务器的 token)
config.set_root("")
bot = BotClient()
load_config()  # 加载全局配置



if __name__ == "__main__":
    
    bot.run()

    
   