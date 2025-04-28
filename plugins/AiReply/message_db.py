import os
import aiosqlite
import aiohttp
import yaml
from ncatbot.utils.logger import get_log

_log = get_log()

class OpenAIContextManager:
    def __init__(self, db_path="data.db"):
        """
        初始化数据库连接和配置加载
        """
        self.db_path = db_path
        self.api_key, self.proxy, self.bot_name = self.load_config()  # 加载 bot_name

    async def _initialize_database(self):
        """
        初始化数据库，创建 ai_txt 表
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS ai_txt (
                        group_id TEXT PRIMARY KEY NOT NULL,
                        context TEXT NOT NULL,
                        setting TEXT DEFAULT '你是一个智能助手。'
                    )
                """)
                await conn.commit()
        except Exception as e:
            _log.error(f"初始化数据库时出错: {e}")

    def load_config(self):
        """
        从根目录的 config.yaml 文件中加载 gemini_apikey、代理地址和 bot_name
        """
        config_path = os.path.join(os.getcwd(), "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                api_key = config.get("gemini_apikey", "")
                proxy = config.get("proxy", None)
                bot_name = config.get("bot_name", "可琳雫")  # 默认值为“机器人”
                return api_key, proxy, bot_name
        except FileNotFoundError:
            _log.error("配置文件 config.yaml 未找到！")
        except Exception as e:
            _log.error(f"加载配置文件时出错: {e}")
        return "", None, "机器人"

    async def get_context(self, group_id):
        """
        获取指定群号的上下文内容
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                async with conn.execute("SELECT context FROM ai_txt WHERE group_id = ?", (group_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else ""
        except Exception as e:
            _log.error(f"获取上下文时出错: {e}")
            return ""
    async def clear_context(self, group_id):
        """
        清空指定群号的上下文内容
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("DELETE FROM ai_txt WHERE group_id = ?", (group_id,))
                await conn.commit()
                _log.info(f"已清空群号 {group_id} 的上下文")
        except Exception as e:
            _log.error(f"清空上下文时出错: {e}")
    async def save_context(self, group_id, context):
        """
        保存或更新指定群号的上下文内容
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO ai_txt (group_id, context) VALUES (?, ?)
                    ON CONFLICT(group_id) DO UPDATE SET context = excluded.context
                """, (group_id, context))
                await conn.commit()
        except Exception as e:
            _log.error(f"保存上下文时出错: {e}")

    async def save_setting(self, group_id, setting):
        """
        保存或更新指定群号的设定
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO ai_txt (group_id, setting, context) VALUES (?, ?, '')
                    ON CONFLICT(group_id) DO UPDATE SET setting = excluded.setting
                """, (group_id, setting))
                await conn.commit()
                _log.info(f"已更新群号 {group_id} 的设定为: {setting}")
        except Exception as e:
            _log.error(f"保存设定时出错: {e}")

    async def get_setting(self, group_id):
        """
        获取指定群号的设定
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                async with conn.execute("SELECT setting FROM ai_txt WHERE group_id = ?", (group_id,)) as cursor:
                    result = await cursor.fetchone()
                    return result[0] if result else "你是一个智能助手。"
        except Exception as e:
            _log.error(f"获取设定时出错: {e}")
            return "你是一个智能助手。"

    async def get_openai_reply(self, group_id, prompt, use_search_model=False):
        """
        调用 OpenAI 接口获取回复，并更新上下文
        """
        if not self.api_key:
            _log.error("API 密钥未初始化，无法调用 OpenAI 接口！")
            return "抱歉，API 密钥未正确配置，无法处理您的请求。"

        # 获取当前上下文和设定
        context = await self.get_context(group_id)
        setting = await self.get_setting(group_id)
        messages = [{"role": "system", "content": setting}]
        if context:
            messages.append({"role": "assistant", "content": context})
        messages.append({"role": "user", "content": prompt})

        # 根据是否使用搜索模型选择模型名称
        model_name = "gemini-2.0-flash:search" if use_search_model else "gemini-2.0-flash-exp"

        url = "https://gemini.syy-freeusa.workers.dev/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": model_name,
            "messages": messages,
            # "temperature": 0.7
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=payload, proxy=self.proxy) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        # 更新上下文
                        new_context = f"{context}\nUser: {prompt}\nAssistant: {reply}"
                        await self.save_context(group_id, new_context)
                        return reply
                    else:
                        _log.error(f"请求失败，状态码: {resp.status}, 响应内容: {await resp.text()}")
                        return "抱歉，无法处理您的请求。"
            except Exception as e:
                _log.error(f"请求 OpenAI 接口时出错: {e}")
                return "抱歉，处理请求时发生错误。"