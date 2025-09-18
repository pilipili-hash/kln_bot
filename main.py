from ncatbot.core import BotClient
from ncatbot.core.message import GroupMessage, PrivateMessage

from ncatbot.utils.config import config
from utils.config_manager import load_config
bot = BotClient()
load_config()

config.set_ws_uri("ws://localhost:3001") 



if __name__ == "__main__":
    bot.run(enable_webui_interaction=False)
   
   