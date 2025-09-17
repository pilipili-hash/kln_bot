import asyncio
import time
import re
import os
import html
from typing import Dict, List, Optional, Any
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from QA.database_handler import QADatabaseHandler
from QA.image_generator import generate_qa_image
from PluginManager.plugin_manager import master_required
from utils.group_forward_msg import send_group_msg_cq

bot = CompatibleEnrollment

class QA(BasePlugin):
    name = "QA"
    version = "2.0.0"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db_handler = None
        # 缓存系统
        self.cache = {}
        self.cache_ttl = 300  # 5分钟缓存
        # 请求限制
        self.last_request_time = {}
        self.request_interval = 1  # 1秒间隔
        # 统计信息
        self.stats = {
            "total_queries": 0,
            "exact_matches": 0,
            "fuzzy_matches": 0,
            "no_matches": 0
        }

    async def on_load(self):
        print(f"{self.name} 插件已加载，版本: {self.version}")
        self.db_handler = QADatabaseHandler()

    def _get_cache_key(self, group_id: int, query: str) -> str:
        """生成缓存键"""
        return f"qa_cache:{group_id}:{query}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache:
            return False
        timestamp, _ = self.cache[cache_key]
        return time.time() - timestamp < self.cache_ttl

    def _get_cached_result(self, cache_key: str) -> Optional[str]:
        """获取缓存结果"""
        if self._is_cache_valid(cache_key):
            _, result = self.cache[cache_key]
            return result
        return None

    def _set_cache(self, cache_key: str, result: str):
        """设置缓存"""
        self.cache[cache_key] = (time.time(), result)

    def _check_request_limit(self, user_id: int) -> bool:
        """检查请求频率限制"""
        current_time = time.time()
        if user_id in self.last_request_time:
            if current_time - self.last_request_time[user_id] < self.request_interval:
                return False
        self.last_request_time[user_id] = current_time
        return True

    def _parse_qa_command(self, message: str) -> Optional[Dict[str, Any]]:
        """
        解析QA命令

        Args:
            message: 原始消息

        Returns:
            Dict: 解析后的参数，或None
        """
        message = message.strip()

        # 精确问答格式: 精确问 问题 答 答案
        exact_match = re.match(r"^精确问\s*(.+?)\s*答\s*(.+)$", message)
        if exact_match:
            return {
                "action": "add_exact",
                "question": exact_match.group(1).strip(),
                "answer": exact_match.group(2).strip()
            }

        # 模糊问答格式: 模糊问 问题 答 答案
        fuzzy_match = re.match(r"^模糊问\s*(.+?)\s*答\s*(.+)$", message)
        if fuzzy_match:
            return {
                "action": "add_fuzzy",
                "question": fuzzy_match.group(1).strip(),
                "answer": fuzzy_match.group(2).strip()
            }

        # 删除词条格式: 删除词条 序号
        delete_match = re.match(r"^删除词条\s*(\d+)$", message)
        if delete_match:
            return {
                "action": "delete",
                "index": int(delete_match.group(1))
            }

        # 查询词条
        if message == "查询词条":
            return {"action": "list"}

        # 词条统计
        if message == "词条统计":
            return {"action": "stats"}

        # 清空词条 (管理员功能)
        if message == "清空词条":
            return {"action": "clear"}

        # 帮助命令
        if message in ["QA帮助", "问答帮助", "/qa帮助", "/QA帮助"]:
            return {"action": "help"}

        # 搜索词条格式: 搜索词条 关键词
        search_match = re.match(r"^搜索词条\s*(.+)$", message)
        if search_match:
            return {
                "action": "search",
                "keyword": search_match.group(1).strip()
            }

        return None

    async def _show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """📚 QA问答系统帮助

🔧 管理员命令：
• 精确问 <问题> 答 <答案> - 添加精确匹配问答
• 模糊问 <问题> 答 <答案> - 添加模糊匹配问答
• 删除词条 <序号> - 删除指定序号的词条
• 清空词条 - 清空本群所有词条

📋 查询命令：
• 查询词条 - 查看本群所有词条
• 搜索词条 <关键词> - 搜索包含关键词的词条
• 词条统计 - 查看词条统计信息
• QA帮助 - 显示此帮助信息

💡 使用示例：
精确问 你好 答 你好呀！
模糊问 天气 答 今天天气不错呢
删除词条 3
搜索词条 天气

📊 功能特点：
• 🎯 精确匹配：完全匹配问题才回答
• 🔍 模糊匹配：包含关键词就可能回答
• 💾 智能缓存：提高响应速度
• 📈 使用统计：记录使用情况
• 🖼️ 图片展示：美观的词条列表

⚠️ 注意事项：
• 管理员命令需要管理员权限
• 问答内容支持CQ码格式
• 缓存时间为5分钟"""

        await self.api.post_group_msg(group_id, text=help_text)

    @bot.group_event()
    @master_required(commands=["精确问", "模糊问", "删除词条", "清空词条"])
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息"""
        group_id = event.group_id
        user_id = event.user_id
        raw_message = html.unescape(event.raw_message.strip())

        # 检查请求频率限制
        if not self._check_request_limit(user_id):
            return

        # 确保数据库表存在
        if not await self.db_handler.table_exists(group_id):
            await self.db_handler.create_table(group_id)

        # 解析命令
        command = self._parse_qa_command(raw_message)
        if command:
            await self._handle_command(group_id, user_id, command)
            return

        # 尝试查找答案
        await self._search_answer(group_id, user_id, raw_message)

    async def _handle_command(self, group_id: int, user_id: int, command: Dict[str, Any]):
        """处理QA命令"""
        action = command["action"]

        try:
            if action == "add_exact":
                await self._add_qa(group_id, command["question"], command["answer"], "exact")
            elif action == "add_fuzzy":
                await self._add_qa(group_id, command["question"], command["answer"], "fuzzy")
            elif action == "delete":
                await self._delete_qa(group_id, command["index"])
            elif action == "list":
                await self._list_qa(group_id)
            elif action == "stats":
                await self._show_stats(group_id)
            elif action == "clear":
                await self._clear_qa(group_id)
            elif action == "help":
                await self._show_help(group_id)
            elif action == "search":
                await self._search_qa(group_id, command["keyword"])
        except Exception as e:
            print(f"处理QA命令失败: {e}")
            await self.api.post_group_msg(group_id, text="命令执行失败，请稍后重试。")

    async def _add_qa(self, group_id: int, question: str, answer: str, match_type: str):
        """添加问答"""
        if await self.db_handler.save_qa(group_id, question, answer, match_type):
            match_type_text = "精确" if match_type == "exact" else "模糊"
            await self.api.post_group_msg(group_id, text=f"✅ {match_type_text}问答已保存\n问：{question}\n答：{answer}")
            # 清除相关缓存
            self._clear_group_cache(group_id)
        else:
            await self.api.post_group_msg(group_id, text="❌ 保存问答失败，请稍后重试。")

    async def _delete_qa(self, group_id: int, index: int):
        """删除问答"""
        if await self.db_handler.delete_qa(group_id, index):
            await self.api.post_group_msg(group_id, text=f"✅ 成功删除第 {index} 条词条")
            # 清除相关缓存
            self._clear_group_cache(group_id)
        else:
            await self.api.post_group_msg(group_id, text=f"❌ 删除失败：序号 {index} 无效或不存在")

    async def _list_qa(self, group_id: int):
        """列出所有问答"""
        qa_list = await self.db_handler.get_all_qa_with_type(group_id)
        if qa_list:
            try:
                image_path = await generate_qa_image(qa_list)
                if image_path and os.path.exists(image_path):
                    await self.api.post_group_msg(group_id, image=image_path)
                    os.remove(image_path)  # 发送后删除临时图片
                else:
                    # 降级到文本显示
                    await self._list_qa_text(group_id, qa_list)
            except Exception as e:
                print(f"生成QA图片失败: {e}")
                await self._list_qa_text(group_id, qa_list)
        else:
            await self.api.post_group_msg(group_id, text="📝 当前群没有词条")

    async def _list_qa_text(self, group_id: int, qa_list: List[Dict[str, str]]):
        """以文本形式列出问答"""
        text_lines = ["📚 本群问答词条：\n"]
        for i, qa in enumerate(qa_list[:20], 1):  # 限制显示前20条
            match_type = qa.get("match_type", "exact")
            type_icon = "🎯" if match_type == "exact" else "🔍"
            text_lines.append(f"{i}. {type_icon} Q: {qa['question']}")
            text_lines.append(f"   A: {qa['answer']}\n")

        if len(qa_list) > 20:
            text_lines.append(f"... 还有 {len(qa_list) - 20} 条词条")

        await self.api.post_group_msg(group_id, text="\n".join(text_lines))

    def _clear_group_cache(self, group_id: int):
        """清除指定群的缓存"""
        keys_to_remove = [key for key in self.cache.keys() if key.startswith(f"qa_cache:{group_id}:")]
        for key in keys_to_remove:
            del self.cache[key]

    async def _show_stats(self, group_id: int):
        """显示统计信息"""
        qa_count = await self.db_handler.get_qa_count(group_id)
        exact_count = await self.db_handler.get_qa_count_by_type(group_id, "exact")
        fuzzy_count = await self.db_handler.get_qa_count_by_type(group_id, "fuzzy")

        stats_text = f"""📊 QA系统统计信息

📚 词条统计：
• 总词条数：{qa_count}
• 精确匹配：{exact_count}
• 模糊匹配：{fuzzy_count}

🎯 使用统计：
• 总查询次数：{self.stats['total_queries']}
• 精确匹配次数：{self.stats['exact_matches']}
• 模糊匹配次数：{self.stats['fuzzy_matches']}
• 未匹配次数：{self.stats['no_matches']}

💾 缓存状态：
• 缓存条目数：{len(self.cache)}
• 缓存TTL：{self.cache_ttl}秒"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def _clear_qa(self, group_id: int):
        """清空所有问答"""
        if await self.db_handler.clear_all_qa(group_id):
            await self.api.post_group_msg(group_id, text="✅ 已清空本群所有词条")
            self._clear_group_cache(group_id)
        else:
            await self.api.post_group_msg(group_id, text="❌ 清空词条失败")

    async def _search_qa(self, group_id: int, keyword: str):
        """搜索问答"""
        qa_list = await self.db_handler.search_qa(group_id, keyword)
        if qa_list:
            text_lines = [f"🔍 搜索「{keyword}」的结果：\n"]
            for i, qa in enumerate(qa_list[:10], 1):  # 限制显示前10条
                match_type = qa.get("match_type", "exact")
                type_icon = "🎯" if match_type == "exact" else "🔍"
                text_lines.append(f"{i}. {type_icon} Q: {qa['question']}")
                text_lines.append(f"   A: {qa['answer']}\n")

            if len(qa_list) > 10:
                text_lines.append(f"... 还有 {len(qa_list) - 10} 条结果")

            await self.api.post_group_msg(group_id, text="\n".join(text_lines))
        else:
            await self.api.post_group_msg(group_id, text=f"🔍 未找到包含「{keyword}」的词条")

    async def _search_answer(self, group_id: int, user_id: int, message: str):
        """搜索答案"""
        # 更新统计
        self.stats["total_queries"] += 1

        # 检查缓存
        cache_key = self._get_cache_key(group_id, message)
        cached_answer = self._get_cached_result(cache_key)
        if cached_answer:
            await send_group_msg_cq(group_id, cached_answer)
            return

        # 查找精确匹配的答案
        answer = await self.db_handler.get_answer(group_id, message)
        if answer:
            self.stats["exact_matches"] += 1
            self._set_cache(cache_key, answer)
            await send_group_msg_cq(group_id, answer)
            return

        # 查找模糊匹配的答案
        answer = await self.db_handler.get_answer_fuzzy(group_id, message)
        if answer:
            self.stats["fuzzy_matches"] += 1
            self._set_cache(cache_key, answer)
            await send_group_msg_cq(group_id, answer)
            return

        # 没有找到答案
        self.stats["no_matches"] += 1

    async def __onload__(self):
        """插件加载时调用"""
        await self.on_load()
