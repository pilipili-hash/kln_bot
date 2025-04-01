from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from QA.database_handler import QADatabaseHandler
from QA.image_generator import generate_qa_image
import re
from PluginManager.plugin_manager import master_required
from utils.group_forward_msg import send_group_forward_msg_cq
import os

bot = CompatibleEnrollment

class QA(BasePlugin):
    name = "QA"
    version = "1.0.0"

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        self.db_handler = QADatabaseHandler()

    @bot.group_event()
    @master_required(commands=["精确问", "模糊问", "删除词条"])
    async def handle_group_message(self, event: GroupMessage):
        group_id = event.group_id
        raw_message = event.raw_message.strip()

        # 检查表是否存在，不存在则创建
        if not await self.db_handler.table_exists(group_id):
            await self.db_handler.create_table(group_id)

        # 处理 "精确问 答" 格式的消息
        match_exact = re.match(r"^精确问\s*(.+?)\s*答\s*(.+)$", raw_message)
        if match_exact:
            question = match_exact.group(1).strip()
            answer = match_exact.group(2).strip()
            if await self.db_handler.save_qa(group_id, question, answer, match_type='exact'):
                await self.api.post_group_msg(group_id, text="精确问答已保存。")
            else:
                await self.api.post_group_msg(group_id, text="保存精确问答失败。")
            return

        # 处理 "模糊问 答" 格式的消息
        match_fuzzy = re.match(r"^模糊问\s*(.+?)\s*答\s*(.+)$", raw_message)
        if match_fuzzy:
            question = match_fuzzy.group(1).strip()
            answer = match_fuzzy.group(2).strip()
            if await self.db_handler.save_qa(group_id, question, answer, match_type='fuzzy'):
                await self.api.post_group_msg(group_id, text="模糊问答已保存。")
            else:
                await self.api.post_group_msg(group_id, text="保存模糊问答失败。")
            return

        # 处理 "查询词条" 命令
        if raw_message == "查询词条":
            qa_list = await self.db_handler.get_all_qa(group_id)
            if qa_list:
                image_path = await generate_qa_image(qa_list)
                await self.api.post_group_msg(group_id, image=image_path)
                os.remove(image_path)  # 发送后删除临时图片
            else:
                await self.api.post_group_msg(group_id, text="当前群没有词条。")
            return

        # 处理 "删除词条" 命令
        match_delete = re.match(r"^删除词条\s*(\d+)$", raw_message)
        if match_delete:
            index = int(match_delete.group(1))
            if await self.db_handler.delete_qa(group_id, index):
                await self.api.post_group_msg(group_id, text=f"成功删除第 {index} 条词条。")
            else:
                await self.api.post_group_msg(group_id, text=f"删除失败：序号 {index} 无效或不存在。")
            return

        # 查找精确匹配的答案
        answer = await self.db_handler.get_answer(group_id, raw_message)
        if answer:
            await send_group_forward_msg_cq(group_id, answer)
            return

        # 查找模糊匹配的答案
        answer = await self.db_handler.get_answer_fuzzy(group_id, raw_message)
        if answer:
            await send_group_forward_msg_cq(group_id, answer)
            return

        # 如果没有找到答案
        # await self.api.post_group_msg(group_id, text="未找到相关答案。")
