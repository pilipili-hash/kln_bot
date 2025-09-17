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
        清空指定群号的上下文内容（只清空context字段，保留setting）
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                # 只更新context字段为空，不删除整个记录
                await conn.execute("UPDATE ai_txt SET context = '' WHERE group_id = ?", (group_id,))
                await conn.commit()
                _log.info(f"已清空群号 {group_id} 的上下文")
                return True
        except Exception as e:
            _log.error(f"清空上下文时出错: {e}")
            return False
    async def save_context(self, group_id, context):
        """
        保存或更新指定群号的上下文内容
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                # 检查群组是否已存在
                async with conn.execute("SELECT COUNT(*) FROM ai_txt WHERE group_id = ?", (group_id,)) as cursor:
                    exists = (await cursor.fetchone())[0] > 0
                
                if exists:
                    # 更新现有记录的上下文
                    await conn.execute("UPDATE ai_txt SET context = ? WHERE group_id = ?", (context, group_id))
                else:
                    # 创建新记录
                    await conn.execute("INSERT INTO ai_txt (group_id, context, setting) VALUES (?, ?, '你是一个智能助手。')", (group_id, context))
                
                await conn.commit()
                return True
        except Exception as e:
            _log.error(f"保存上下文时出错: {e}")
            return False

    async def save_setting(self, group_id, setting):
        """
        保存或更新指定群号的设定
        """
        try:
            async with aiosqlite.connect(self.db_path) as conn:
                # 检查群组是否已存在
                async with conn.execute("SELECT COUNT(*) FROM ai_txt WHERE group_id = ?", (group_id,)) as cursor:
                    exists = (await cursor.fetchone())[0] > 0

                if exists:
                    # 更新现有记录的设定
                    await conn.execute("UPDATE ai_txt SET setting = ? WHERE group_id = ?", (setting, group_id))
                else:
                    # 创建新记录
                    await conn.execute("INSERT INTO ai_txt (group_id, setting, context) VALUES (?, ?, '')", (group_id, setting))

                await conn.commit()
                _log.info(f"已更新群号 {group_id} 的设定为: {setting}")

                # 设定更新后，清空该群组的上下文，确保新设定立即生效
                await self.clear_context(group_id)
                _log.info(f"已清空群号 {group_id} 的上下文以应用新设定")

                return True
        except Exception as e:
            _log.error(f"保存设定时出错: {e}")
            return False

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

    async def get_openai_reply(self, group_id, prompt, use_search_model=False, image_urls=None):
        """
        调用 OpenAI 接口获取回复，并更新上下文
        支持图片分析功能

        Args:
            group_id: 群组ID
            prompt: 用户输入的文本
            use_search_model: 是否使用搜索模型
            image_urls: 图片URL列表，用于图片分析
        """
        if not self.api_key:
            _log.error("API 密钥未初始化，无法调用 OpenAI 接口！")
            return "抱歉，API 密钥未正确配置，无法处理您的请求。"

        # 获取当前设定
        setting = await self.get_setting(group_id)

        # 构建对话历史
        messages = [{"role": "system", "content": setting}]

        # 获取并解析上下文，而不是简单地将其作为单个消息
        context = await self.get_context(group_id)
        if context:
            try:
                # 将保存的上下文分割成对话轮次
                context_parts = context.split('\n')
                i = 0
                while i < len(context_parts):
                    if i+1 < len(context_parts) and context_parts[i].startswith("User: ") and context_parts[i+1].startswith("Assistant: "):
                        user_msg = context_parts[i][6:]  # 去掉 "User: " 前缀
                        asst_msg = context_parts[i+1][11:]  # 去掉 "Assistant: " 前缀
                        messages.append({"role": "user", "content": user_msg})
                        messages.append({"role": "assistant", "content": asst_msg})
                        i += 2
                    else:
                        i += 1
            except Exception as e:
                _log.error(f"解析上下文时出错: {e}")
                # 出错时清空上下文重新开始
                await self.clear_context(group_id)
                messages = [{"role": "system", "content": setting}]

        # 调试：打印当前使用的设定
        _log.info(f"群组 {group_id} 当前设定: {setting}")
        _log.info(f"消息历史长度: {len(messages)}")
        for i, msg in enumerate(messages):
            if msg["role"] == "system":
                _log.info(f"系统消息 {i}: {msg['content'][:100]}...")
            else:
                _log.info(f"消息 {i} ({msg['role']}): {str(msg['content'])[:100] if isinstance(msg['content'], str) else 'multimodal'}...")

        # 构建用户消息内容
        if image_urls:
            # 有图片时，检查是否为base64格式，如果是则跳过图片分析
            valid_image_urls = []
            for image_url in image_urls:
                if image_url.startswith('http'):
                    valid_image_urls.append(image_url)
                    _log.info(f"添加图片到消息: {image_url}")
                else:
                    _log.warning(f"跳过非HTTP图片: {image_url[:50]}...")

            if valid_image_urls:
                # 使用Gemini的多模态格式
                user_message_content = []

                # 添加文本内容
                text_content = prompt if prompt else "请分析这张图片，描述你看到的内容。"
                user_message_content.append({
                    "type": "text",
                    "text": text_content
                })

                # 添加图片内容
                for image_url in valid_image_urls:
                    user_message_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": image_url
                        }
                    })

                messages.append({"role": "user", "content": user_message_content})
            else:
                # 没有有效的HTTP图片，降级为纯文本
                fallback_text = f"{prompt} [注：图片格式不支持，无法分析]" if prompt else "抱歉，图片格式不支持分析。"
                messages.append({"role": "user", "content": fallback_text})
                _log.warning("所有图片都不是HTTP格式，降级为纯文本处理")
        else:
            # 没有图片，使用简单的文本格式
            messages.append({"role": "user", "content": prompt})

        # 根据是否使用搜索模型选择模型名称
        model_name = "gemini-2.0-flash:search" if use_search_model else "gemini-2.0-flash-exp"

        url = "https://gemn.ariaxz.tk/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 构建请求载荷
        payload = {
            "model": model_name,
            "messages": messages,
            "max_tokens": 4000,  # 添加最大token限制
            "temperature": 0.7   # 添加温度参数
        }

        # 调试：打印请求信息
        _log.info(f"API请求模型: {model_name}")
        _log.info(f"消息数量: {len(messages)}")
        for i, msg in enumerate(messages[-2:]):  # 只打印最后2条消息
            if isinstance(msg.get('content'), list):
                content_types = [item.get('type', 'unknown') for item in msg['content']]
                _log.info(f"消息 {i} ({msg['role']}): 多模态内容 {content_types}")
            else:
                content_preview = str(msg.get('content', ''))[:100]
                _log.info(f"消息 {i} ({msg['role']}): {content_preview}...")

        async with aiohttp.ClientSession() as session:
            try:
                _log.info(f"发送API请求到: {url}")
                async with session.post(url, headers=headers, json=payload, proxy=self.proxy) as resp:
                    response_text = await resp.text()
                    _log.info(f"API响应状态码: {resp.status}")

                    if resp.status == 200:
                        try:
                            data = await resp.json()
                            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                            if not reply:
                                _log.warning("API返回空回复")
                                return "抱歉，AI没有返回有效回复。"

                            # 构建上下文记录
                            context_prompt = prompt if prompt else "[图片分析]"
                            if image_urls:
                                valid_count = len([url for url in image_urls if url.startswith('http')])
                                context_prompt += f" [包含{valid_count}张图片]"

                            # 更新上下文，保持正确的格式
                            new_context = context + (f"\nUser: {context_prompt}\nAssistant: {reply}" if context else f"User: {context_prompt}\nAssistant: {reply}")

                            # 如果上下文太长，可以考虑截取最近的几轮对话
                            if len(new_context) > 4000:  # 设置一个合理的长度限制
                                parts = new_context.split('\nUser: ')
                                if len(parts) > 3:  # 保留最近的几轮对话
                                    new_context = 'User: ' + '\nUser: '.join(parts[-3:])

                            await self.save_context(group_id, new_context)
                            _log.info(f"AI回复成功，长度: {len(reply)}")
                            return reply

                        except Exception as json_error:
                            _log.error(f"解析API响应JSON失败: {json_error}")
                            _log.error(f"原始响应: {response_text[:500]}...")
                            return "抱歉，解析AI回复时出现错误。"

                    elif resp.status == 400:
                        _log.error(f"API请求参数错误 (400): {response_text}")
                        # 尝试解析错误信息
                        try:
                            error_data = await resp.json()
                            error_msg = error_data.get("error", {}).get("message", "未知错误")
                            _log.error(f"详细错误信息: {error_msg}")

                            # 如果是图片相关错误，提供更友好的提示
                            if "image" in error_msg.lower() or "multimodal" in error_msg.lower():
                                return "抱歉，图片分析功能暂时不可用，请稍后再试或发送纯文本消息。"
                            else:
                                return f"抱歉，请求格式有误：{error_msg}"
                        except:
                            return "抱歉，请求参数有误，请检查输入内容。"

                    else:
                        _log.error(f"API请求失败，状态码: {resp.status}, 响应: {response_text[:500]}...")
                        return f"抱歉，服务暂时不可用（错误码：{resp.status}）。"

            except Exception as e:
                _log.error(f"请求API时发生异常: {e}")
                import traceback
                _log.error(f"异常详情: {traceback.format_exc()}")
                return "抱歉，网络连接出现问题，请稍后再试。"