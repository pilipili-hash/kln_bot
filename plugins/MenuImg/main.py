
from .database_utils import load_menu_data, extract_members, generate_temp_image, send_image,update_menu_from_file
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from utils.group_forward_msg import send_group_forward_msg_ws


bot = CompatibleEnrollment  # 兼容回调函数注册器

    
class MenuImg(BasePlugin):
    name = "MenuImg"  # 插件名称
    version = "0.0.2"  # 插件版本
    # dependencies={"Pillow":">=9.0.0"}
    
    @bot.group_event()
    async def on_group_event(self, msg: GroupMessage):
        if msg.raw_message == "菜单":
            menu_data = await load_menu_data(msg.group_id)  # 添加 await 调用异步函数
            if not menu_data:
                await self.api.post_group_msg(msg.group_id, text="菜单数据不存在或数据格式错误")
                return

            members = extract_members(menu_data)  # 提取成员信息
            image_path = generate_temp_image(members)  # 生成临时图片

            if image_path:
                await send_image(self.api, msg.group_id, image_path)  # 发送图片

        elif msg.raw_message == "更新菜单":
            success = await update_menu_from_file(msg.group_id)  # 添加 await 调用异步函数
            if success:
                await self.api.post_group_msg(msg.group_id, text="菜单已成功更新并合并")
            else:
                await self.api.post_group_msg(msg.group_id, text="菜单更新失败，请检查 menu.json 文件")



    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

