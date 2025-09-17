import logging
import random
import json
import time
import httpx
import yaml
import os
from typing import Dict, List, Optional, Any

_log = logging.getLogger(__name__)

class AIIntegration:
    """AI集成管理器"""

    def __init__(self):
        self.ai_reply_plugin = None
        self.context_manager = None

        # 加载配置
        self.api_key, self.proxy, self.bot_name = self.load_config()

        # 预设回复库
        self.preset_responses = {
            "greeting": ["你好", "嗨", "哈喽", "早上好", "下午好", "晚上好"],
            "agreement": ["确实", "有道理", "说得对", "我也觉得", "就是这样", "对对对"],
            "laughter": ["哈哈哈", "笑死我了", "太搞笑了", "确实好笑", "哈哈", "笑死"],
            "surprise": ["哇", "天哪", "不敢相信", "真的假的", "震惊", "厉害"],
            "confusion": ["啊？", "什么意思", "不太懂", "可能吧", "这样啊", "原来如此"],
            "casual": ["好的", "知道了", "收到", "明白", "了解", "这样啊"],
            "thinking": ["让我想想", "这个嘛", "怎么说呢", "可能是", "应该吧"],
            "encouragement": ["加油", "你可以的", "相信你", "没问题", "支持你"],
            "sympathy": ["辛苦了", "理解", "不容易", "加油吧", "会好的"],
            "excitement": ["太棒了", "厉害", "牛逼", "赞", "给力", "666"]
        }

        # 情感关键词映射
        self.emotion_keywords = {
            "greeting": ["你好", "hi", "hello", "早", "晚上好", "下午好"],
            "agreement": ["对", "是", "确实", "同意", "支持", "赞同"],
            "laughter": ["哈", "笑", "搞笑", "好笑", "有趣", "幽默"],
            "surprise": ["哇", "天", "震惊", "不敢相信", "厉害", "牛"],
            "confusion": ["?", "？", "什么", "为什么", "怎么", "不懂"],
            "casual": ["好", "嗯", "知道", "收到", "明白", "了解"],
            "thinking": ["想", "考虑", "思考", "可能", "也许", "大概"],
            "encouragement": ["加油", "努力", "坚持", "相信", "支持"],
            "sympathy": ["辛苦", "累", "不容易", "理解", "同情"],
            "excitement": ["棒", "赞", "牛", "厉害", "给力", "666", "amazing"]
        }

    def load_config(self):
        """从根目录的 config.yaml 文件中加载 gemini_apikey、代理地址和 bot_name"""
        config_path = os.path.join(os.getcwd(), "config.yaml")
        try:
            with open(config_path, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                api_key = config.get("gemini_apikey", "")
                proxy = config.get("proxy", None)
                bot_name = config.get("bot_name", "可琳雫")
                return api_key, proxy, bot_name
        except FileNotFoundError:
            _log.error("配置文件 config.yaml 未找到！")
        except Exception as e:
            _log.error(f"加载配置文件时出错: {e}")
        return "", None, "机器人"
    
    async def initialize(self, api):
        """初始化AI集成"""
        try:
            # 检查是否有API密钥
            if not self.api_key:
                _log.warning("未配置Gemini API密钥，将使用预设回复")
                return False

            _log.info("AI集成初始化成功，使用Gemini API")
            return True

        except Exception as e:
            _log.warning(f"AI集成初始化失败: {e}")
            return False
    
    async def generate_response(self, group_id: int, message: str, fake_user: Dict[str, Any], api=None) -> str:
        """生成AI回复"""
        try:
            if self.api_key:
                return await self._generate_ai_response(group_id, message, fake_user, api)
            else:
                return self._generate_preset_response(message)
        except Exception as e:
            _log.error(f"生成回复失败: {e}")
            return self._generate_preset_response(message)

    async def _generate_ai_response(self, group_id: int, message: str, fake_user: Dict[str, Any], api=None) -> str:
        """使用Gemini API生成回复"""
        try:
            # 获取聊天记录
            chat_history = await self._get_chat_history(group_id, api) if api else []

            # 构建角色设定提示
            personality_prompt = self._build_personality_prompt(message, fake_user, chat_history)

            # 调用Gemini API生成回复
            response = await self._call_gemini_api(personality_prompt)

            if response:
                # 后处理回复
                processed_response = self._post_process_response(response)
                return processed_response

        except Exception as e:
            _log.warning(f"AI回复生成失败: {e}")

        # 降级到预设回复
        return self._generate_preset_response(message)

    async def _call_gemini_api(self, prompt: str) -> str:
        """调用Gemini API"""
        try:
            url = "https://gemn.ariaxz.tk/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            messages = [
                {"role": "system", "content": "你是一个活泼的群友，要自然地参与群聊。"},
                {"role": "user", "content": prompt}
            ]

            payload = {
                "model": "gemini-2.0-flash-exp",
                "messages": messages,
                "max_tokens": 150,
                "temperature": 0.8
            }

            timeout = httpx.Timeout(30.0)
            connector_kwargs = {}
            if self.proxy:
                connector_kwargs["proxy"] = self.proxy

            async with httpx.AsyncClient(timeout=timeout, **connector_kwargs) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    return content.strip()
                else:
                    _log.error(f"Gemini API返回格式异常: {result}")
                    return ""

        except httpx.TimeoutException:
            _log.error("Gemini API调用超时")
            return ""
        except httpx.HTTPStatusError as e:
            _log.error(f"Gemini API HTTP错误: {e.response.status_code}")
            return ""
        except Exception as e:
            _log.error(f"调用Gemini API失败: {e}")
            return ""

    async def _get_chat_history(self, group_id: int, api, limit: int = 5) -> List[Dict[str, Any]]:
        """获取群聊历史记录"""
        try:
            if not api:
                return []

            # 尝试获取群聊历史记录（多种API格式兼容）
            history_result = None
            api_methods = [
                lambda: api.get_group_msg_history(group_id=group_id, message_seq=None, reverse_order=False, count=limit),
                lambda: api.get_group_msg_history(group_id, None, False, limit),
                lambda: api.get_group_msg_history(group_id=group_id, count=limit, reverse_order=False),
                lambda: api.get_group_msg_history(group_id, limit, False),
                lambda: api.get_group_msg_history(group_id, limit),
                lambda: api.get_group_msg_history(group_id)
            ]

            for method in api_methods:
                try:
                    history_result = await method()
                    break
                except Exception:
                    continue

            if not history_result:
                return []

            if not history_result:
                return []

            # 处理不同的返回格式
            messages = []
            if isinstance(history_result, dict):
                if 'data' in history_result and history_result['data']:
                    messages = history_result['data'].get('messages', [])
                elif 'messages' in history_result:
                    messages = history_result['messages']
                else:
                    return []
            elif isinstance(history_result, list):
                messages = history_result
            else:
                return []

            # 处理消息格式，转换为简单的聊天记录
            processed_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    sender = msg.get('sender', {})
                    nickname = sender.get('card') or sender.get('nickname', f'用户{msg.get("user_id", "")}')

                    # 处理消息内容
                    raw_message = msg.get('raw_message', '')
                    if isinstance(msg.get('message'), list):
                        # 提取文本内容
                        text_parts = []
                        for item in msg['message']:
                            if item.get('type') == 'text':
                                text_parts.append(item.get('data', {}).get('text', ''))
                        content = ''.join(text_parts).strip()
                    else:
                        content = raw_message.strip()

                    # 过滤掉太短或包含CQ码的消息
                    if len(content) >= 2 and 'CQ:' not in content:
                        time_str = time.strftime("%H:%M:%S", time.localtime(msg.get('time', time.time())))
                        processed_messages.append({
                            'T': time_str,
                            'N': nickname[:10],  # 限制昵称长度
                            'C': content[:50]    # 限制内容长度
                        })

            return processed_messages[-limit:] if processed_messages else []

        except Exception as e:
            _log.warning(f"获取聊天记录失败: {e}")
            return []

    def _build_personality_prompt(self, message: str, fake_user: Dict[str, Any], chat_history: List[Dict[str, Any]] = None) -> str:
        """构建角色设定提示"""
        nickname = fake_user.get('nickname', '群友')

        # 构建聊天历史文本
        history_text = ""
        if chat_history:
            history_lines = []
            for msg in chat_history:
                # 格式化为JSON格式
                json_str = json.dumps(msg, ensure_ascii=False)
                history_lines.append(json_str[1:-1])  # 去掉外层大括号
            history_text = "\n".join(history_lines)

        # 使用类似参考项目的prompt风格
        default_prompt = """【任务规则】
1. 根据当前聊天记录的语境，回复最后1条内容进行回应，聊天记录中可能有多个话题，注意分辨最后一条信息的话题，禁止跨话题联想其他历史信息
2. 用中文互联网常见的口语化短句回复，禁止使用超过30个字的长句
3. 模仿真实网友的交流特点：适当使用缩写、流行梗、表情符号（但每条最多1个），精准犀利地进行吐槽
4. 输出必须为纯文本，禁止任何格式标记或前缀
5. 使用00后常用网络语态（如：草/绝了/好耶）
6. 核心萌点：偶尔暴露二次元知识
7. 当出现多个话题时，优先回应最新的发言内容

【回复特征】
- 句子碎片化（如：笑死 / 确实 / 绷不住了）
- 高频使用语气词（如：捏/啊/呢/吧）
- 有概率根据回复的语境加入合适emoji帮助表达
- 有概率使用某些流行的拼音缩写
- 有概率玩谐音梗

【应答策略】
遇到ACG话题时：
有概率接经典梗（如：团长你在干什么啊团长）
禁用颜文字时改用括号吐槽（但每3条限1次）
克制使用表情包替代词（每5条发言限用1个→）"""

        full_prompt = f"""{default_prompt}
每条聊天记录的格式为: "T": "消息发送时间", "N": "发送者的昵称", "C": "消息内容"
请始终保持自然随意的对话风格，避免完整句式或逻辑论述。输出禁止包含任何格式标记或前缀和分析过程
在下面的历史聊天记录中，你在群聊中的昵称为{nickname}，现在请处理最新消息：
{history_text}
最新消息："{message}"
"""

        return full_prompt
    
    def _analyze_message_type(self, message: str) -> str:
        """分析消息类型"""
        message_lower = message.lower()
        
        for emotion_type, keywords in self.emotion_keywords.items():
            if any(keyword in message_lower for keyword in keywords):
                return emotion_type
        
        return "casual"
    
    def _post_process_response(self, response: str) -> str:
        """后处理AI回复"""
        if not response:
            return ""

        # 清理回复内容
        response = self._clean_model_output(response)

        # 移除可能的AI标识
        response = response.strip()

        # 移除常见的AI回复前缀
        prefixes_to_remove = [
            "作为", "我是", "AI", "助手", "机器人", "人工智能",
            "根据", "基于", "从技术角度", "客观来说"
        ]

        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                # 如果以这些词开头，使用预设回复
                return self._generate_preset_response("")

        # 限制长度
        if len(response) > 50:
            response = response[:47] + "..."



        return response

    def _clean_model_output(self, raw_output: str) -> str:
        """清理模型输出"""
        import re
        # 移除思考过程标记及内容
        cleaned = re.sub(r'<think>.*?</think>', '', raw_output, flags=re.DOTALL)
        # 移除多余空行和空格
        cleaned = re.sub(r'\n+', '\n', cleaned).strip()
        return cleaned
    
    def _generate_preset_response(self, message: str) -> str:
        """生成预设回复"""
        message_type = self._analyze_message_type(message)
        
        # 获取对应类型的回复
        responses = self.preset_responses.get(message_type, self.preset_responses["casual"])
        
        # 随机选择一个回复
        base_response = random.choice(responses)
        


        return base_response
    
    async def analyze_image_for_emoji(self, image_url: str) -> str:
        """分析图片内容用于表情分类"""
        try:
            # 优先使用Gemini API进行图片分析
            if self.api_key:
                try:
                    analysis_prompt = """请分析这个表情图片，并严格按照以下格式回复：

分析要求：
1. 识别图片中的主要元素和表情
2. 从以下分类中选择最合适的一个：
   开心、难过、愤怒、惊讶、疑惑、无语、赞同、可爱、调皮、思考、睡觉、吃东西、其他

3. 用5-15个字简短描述这个表情

回复格式（严格按照此格式）：
分类:描述

例如：
开心:哈哈大笑的表情
可爱:萌萌的小猫咪
无语:翻白眼的表情

请只回复"分类:描述"，不要添加其他内容。"""

                    # 调用Gemini API进行图片分析
                    response = await self._call_gemini_api_with_image(analysis_prompt, image_url)

                    if response and ':' in response:
                        # 清理回复，确保格式正确
                        response = response.strip()
                        parts = response.split(':', 1)
                        category = parts[0].strip()
                        description = parts[1].strip()

                        # 验证分类
                        valid_categories = [
                            "开心", "难过", "愤怒", "惊讶", "疑惑", "无语",
                            "赞同", "可爱", "调皮", "思考", "睡觉", "吃东西", "其他"
                        ]

                        if category in valid_categories:
                            _log.info(f"Gemini分析成功: {category}:{description[:30]}")
                            return f"{category}:{description[:50]}"

                except Exception as api_error:
                    _log.warning(f"Gemini API分析失败: {api_error}")

            # 如果AI分析失败，使用基于URL特征的简单分类
            _log.info("使用URL特征分析作为备选方案")
            url_lower = image_url.lower()

            # 根据文件扩展名进行分类
            if '.gif' in url_lower:
                return "调皮:动态表情"
            elif any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png']):
                if any(word in url_lower for word in ['meme', 'funny', 'joke']):
                    return "开心:搞笑图片"
                elif any(word in url_lower for word in ['cute', '可爱']):
                    return "可爱:可爱图片"
                else:
                    return "其他:表情图片"

            return "其他:表情图片"

        except Exception as e:
            _log.warning(f"图片分析失败: {e}")
            return "其他:表情图片"

    async def _call_gemini_api_with_image(self, prompt: str, image_url: str) -> str:
        """调用Gemini API进行图片分析"""
        try:
            url = "https://gemn.ariaxz.tk/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }

            # 构建包含图片的消息
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ]

            payload = {
                "model": "gemini-2.0-flash-exp",
                "messages": messages,
                "max_tokens": 100,
                "temperature": 0.7
            }

            timeout = httpx.Timeout(30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 200:
                    result = response.json()
                    if 'choices' in result and len(result['choices']) > 0:
                        content = result['choices'][0]['message']['content']
                        return content.strip()

        except Exception as e:
            _log.warning(f"Gemini图片分析失败: {e}")

        # 如果图片分析失败，使用基于URL的简单分析
        _log.info("图片分析失败，使用URL特征分析")
        url_lower = image_url.lower()

        if '.gif' in url_lower:
            return "调皮:动态表情"
        elif any(ext in url_lower for ext in ['.jpg', '.jpeg', '.png']):
            if any(word in url_lower for word in ['meme', 'funny', 'joke']):
                return "开心:搞笑图片"
            elif any(word in url_lower for word in ['cute', '可爱']):
                return "可爱:可爱图片"
            else:
                return "其他:表情图片"

        return "其他:表情图片"



    def get_response_with_emotion(self, message: str, target_emotion: str) -> str:
        """根据目标情感生成回复"""
        if target_emotion in self.preset_responses:
            responses = self.preset_responses[target_emotion]
            return random.choice(responses)
        else:
            return self._generate_preset_response(message)
    
    def is_ai_available(self) -> bool:
        """检查AI是否可用"""
        return bool(self.api_key)
    

