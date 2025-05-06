# import asyncio
# import re
# from ncatbot.plugin import BasePlugin, CompatibleEnrollment
# from ncatbot.core.message import GroupMessage
# from utils.priority_handler import register_handler
# from utils.config_manager import get_config, load_config
# from ncatbot.utils.logger import get_log
# import yaml
# import os

# _log = get_log()

# bot = CompatibleEnrollment

# class GroupManager(BasePlugin):
#     name = "GroupManager"
#     version = "1.0.0"
#     is_enabled = True  # 插件默认开启
#     __plugin_class__ = True  # 标识这是一个插件类

#     async def on_load(self):
#         print(f"{self.name} 插件已加载")
#         print(f"插件版本: {self.version}")

#     @register_handler(priority=1)  # 原本为priority=1
#     @bot.group_event()
#     async def handle_group_message(self, event: GroupMessage):
#         if not GroupManager.is_enabled:
#             await self.api.post_group_msg(event.group_id, text="机器人已关闭")
#             return True

#         raw_message = event.raw_message.strip()

#         if raw_message == "/关机":
#             if await self.is_master(event.user_id):
#                 GroupManager.is_enabled = False
#                 await self.api.post_group_msg(event.group_id, text="所有插件已关闭")
#                 return True  # 阻止后续插件处理
#             else:
#                 await self.api.post_group_msg(event.group_id, text="你没有权限执行此操作")
#                 return False

#         elif raw_message == "/开机":
#             if await self.is_master(event.user_id):
#                 GroupManager.is_enabled = True
#                 await self.api.post_group_msg(event.group_id, text="所有插件已开启")
#                 return False  # 允许后续插件处理
#             else:
#                 await self.api.post_group_msg(event.group_id, text="你没有权限执行此操作")
#                 return False

#         elif raw_message.startswith("/添加主人"):
#             if await self.is_master(event.user_id):
#                 match = re.search(r"\[CQ:at,qq=(\d+)]", raw_message)
#                 if match:
#                     new_master_id = int(match.group(1))
#                     await self.add_master(new_master_id)
#                     await self.api.post_group_msg(event.group_id, text=f"已添加 {new_master_id} 为主人")
#                 else:
#                     await self.api.post_group_msg(event.group_id, text="请 @ 需要添加为主人的人")
#                 return True
#             else:
#                 await self.api.post_group_msg(event.group_id, text="你没有权限执行此操作")
#             return False
#         return False

#     async def is_master(self, user_id: int) -> bool:
#         """检查用户是否为主人"""
#         master_list = get_config("master", [])
#         return user_id in master_list

#     async def add_master(self, user_id: int):
#         """添加主人到配置文件"""
#         config_path = os.path.join(os.getcwd(), "config.yaml")
#         config = get_config()
#         if "master" not in config:
#             config["master"] = []
#         if user_id not in config["master"]:
#             config["master"].append(user_id)
#             # 使用 aiofiles 异步写入 YAML 文件
#             try:
#                 with open(config_path, 'w', encoding='utf-8') as f:
#                     yaml.dump(config, f)
#                 _log.info(f"已添加 {user_id} 为主人")
#             except Exception as e:
#                 _log.error(f"写入配置文件失败: {e}")
#         else:
#             _log.info(f"{user_id} 已经是主人")

#     @staticmethod
#     def is_plugin_enabled():
#         return GroupManager.is_enabled
