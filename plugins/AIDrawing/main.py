import aiohttp
import random
import json
import re
import traceback
import yaml
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image, Reply
from PluginManager.plugin_manager import feature_required

bot = CompatibleEnrollment

class AIDrawing(BasePlugin):
    name = "AIDrawing"  # 插件名称
    version = "2.0.0"  # 插件版本
    description = "AI绘图插件，支持文本生成图片和随机绘图"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 加载AI绘图配置
        ai_drawing_config = self.load_config()

        # API 配置 - 从配置文件读取
        self.SD_API_URL = ai_drawing_config.get('api_url', 'https://sd.exacg.cc/api/v1/generate_image')
        self.SD_RANDOM_TAG_URL = ai_drawing_config.get('random_tag_url', 'https://sd.exacg.cc/random_tag')
        self.SD_API_KEY = ai_drawing_config.get('api_key', '')
        self.TRANSLATE_API_URL = ai_drawing_config.get('translate_api_url', 'https://deepl.borber.top/translate')

        # 默认参数配置
        self.default_width = ai_drawing_config.get('default_width', 512)
        self.default_height = ai_drawing_config.get('default_height', 768)
        self.default_steps = ai_drawing_config.get('default_steps', 20)
        self.default_cfg = ai_drawing_config.get('default_cfg', 7.0)
        self.max_retries = ai_drawing_config.get('max_retries', 3)
        self.timeout = ai_drawing_config.get('timeout', 120)

        # 可用模型列表
        self.models = {
            0: "MiaoMiao Harem 1.7",
            1: "Miaomiao Harem vPred Dogma 1.1",
            2: "MiaoMiao Pixel 像素 1.0",
            3: "NoobAIXL V1.1",
            4: "NoobAIXL V1.0",
            5: "illustrious_pencil 融合",
            6: "Wainsfw illustrious v14",
            7: "Qwen image",
            8: "Qwen Image Edit版",
            9: "Qwen Image Edit版(服务器2)"
        }

    def load_config(self):
        """从配置文件加载AI绘图相关配置"""
        try:
            with open('config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('ai_drawing', {})
        except Exception as e:
            print(f"加载AI绘图配置失败: {e}")
            return {}

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")
        print(f"API密钥: {'已配置' if self.SD_API_KEY else '未配置'}")
        if not self.SD_API_KEY:
            print("警告: 未配置API密钥，请在config.yaml中设置ai_drawing.api_key")
    
    async def translate_to_english(self, text: str) -> str:
        """将中文文本翻译为英文"""
        # 判断是否包含中文
        if not re.search(r'[\u4e00-\u9fff]', text):
            return text  # 如果不包含中文，直接返回原文
            
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": "把这句话翻译成英文:"+text,
                    "target": "en"  # 目标语言为英文
                }
                
                async with session.post(
                    self.TRANSLATE_API_URL, 
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=30
                ) as response:
                    if response.status == 200:
                        try:
                            result = json.loads(await response.text())
                            if result.get("success"):
                                translated = result["data"]["translatedText"]
                                return translated
                        except json.JSONDecodeError:
                            pass
            
            # 尝试备用翻译方法
            return await self.backup_translate(text)
        except Exception:
            # 使用备用翻译方法
            return await self.backup_translate(text)

    async def backup_translate(self, text: str) -> str:
        """备用翻译方法 - 使用简单的词典进行关键词翻译"""
        # 常见中文词汇的英文对照表
        translation_dict = {
            "穿着": "wearing",
            "黑色": "black",
            "JK": "JK",
            "服": "uniform",
            "制服": "uniform",
            "高中生": "high school student",
            "女孩": "girl",
            "男孩": "boy",
            "可爱": "cute",
            "漂亮": "beautiful",
            "帅气": "handsome",
            "动漫": "anime",
            "风格": "style",
            "蓝色": "blue",
            "红色": "red",
            "绿色": "green",
            "白色": "white",
            "粉色": "pink",
            "长发": "long hair",
            "短发": "short hair",
            "眼睛": "eyes",
            "微笑": "smile",
            "公园": "park",
            "学校": "school",
            "教室": "classroom",
            "背景": "background"
        }
        
        # 简单的替换翻译
        translated = text
        for cn, en in translation_dict.items():
            translated = translated.replace(cn, en)
        
        # 如果翻译前后没有变化，尝试添加一些通用描述
        if translated == text:
            translated = f"anime style, {text}, beautiful detailed"
        
        return translated
    
    async def get_random_tag(self) -> str:
        """从API获取随机标签"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.SD_RANDOM_TAG_URL, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "tag" in result and result["tag"]:
                            return result["tag"]
            return None
        except Exception as e:
            print(f"获取随机标签失败: {e}")
            return None
    
    async def generate_image(self, prompt: str, model_index: int = None, width: int = None, height: int = None,
                           steps: int = None, cfg: float = None, seed: int = None) -> str:
        """调用SD API生成图片"""
        try:
            # 使用传入参数或默认配置
            if seed is None:
                seed = random.randint(1, 2147483647)
            if model_index is None:
                model_index = random.randint(0, 7)  # 只使用图片生成模型，不包括编辑模型
            if width is None:
                width = self.default_width
            if height is None:
                height = self.default_height
            if steps is None:
                steps = self.default_steps
            if cfg is None:
                cfg = self.default_cfg

            payload = {
                "prompt": prompt,
                "negative_prompt": "lowres, {bad}, error, fewer, extra, missing, worst quality, jpeg artifacts, bad quality, watermark, unfinished, displeasing, chromatic aberration, signature, extra digits, artistic error, username, scan, [abstract]",
                "width": width,
                "height": height,
                "steps": steps,
                "cfg": cfg,
                "model_index": model_index,
                "seed": seed
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.SD_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.SD_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload,
                    timeout=self.timeout
                ) as response:
                    if response.status == 200:
                        # 尝试解析JSON响应
                        try:
                            result = await response.json()
                            
                            # 处理不同类型的返回格式
                            # 1. 直接检查顶层
                            if "image_url" in result:
                                return result["image_url"]
                                
                            # 2. 检查data对象内的image_url
                            if "data" in result and isinstance(result["data"], dict):
                                data = result["data"]
                                
                                if "image_url" in data:
                                    return data["image_url"]
                                    
                                if "images" in data and data["images"] and len(data["images"]) > 0:
                                    return data["images"][0]
                            
                            # 3. 检查其他常见格式
                            if "image" in result:
                                # 可能是base64图片
                                if isinstance(result["image"], str):
                                    if result["image"].startswith("data:image"):
                                        return result["image"]
                                    elif result["image"].startswith("http"):
                                        return result["image"]
                                    else:
                                        # 假设是base64但没有前缀
                                        return f"data:image/png;base64,{result['image']}"
                            
                            if "images" in result and result["images"]:
                                # 某些API返回图片数组
                                if isinstance(result["images"][0], str):
                                    if result["images"][0].startswith("data:image"):
                                        return result["images"][0]
                                    elif result["images"][0].startswith("http"):
                                        return result["images"][0]
                                    else:
                                        # 假设是base64但没有前缀
                                        return f"data:image/png;base64,{result['images'][0]}"
                            
                            # 4. 递归搜索JSON中的任何URL或图片数据
                            url = self.find_image_url_in_json(result)
                            if url:
                                return url
                        except Exception:
                            pass
            
            return None
        except Exception:
            return None

    def find_image_url_in_json(self, json_obj, depth=0, max_depth=5):
        """递归搜索JSON中的图片URL"""
        if depth > max_depth:  # 防止过深递归
            return None
            
        if isinstance(json_obj, dict):
            # 直接检查常见的键名
            for key in ['image_url', 'url', 'image', 'img', 'src']:
                if key in json_obj and isinstance(json_obj[key], str):
                    value = json_obj[key]
                    if value.startswith('http') or value.startswith('data:image'):
                        return value
            
            # 递归检查所有值
            for key, value in json_obj.items():
                result = self.find_image_url_in_json(value, depth + 1, max_depth)
                if result:
                    return result
                    
        elif isinstance(json_obj, list):
            # 递归检查列表中的所有项
            for item in json_obj:
                result = self.find_image_url_in_json(item, depth + 1, max_depth)
                if result:
                    return result
                    
        # 检查字符串是否像URL
        elif isinstance(json_obj, str) and len(json_obj) > 10:
            if json_obj.startswith('http') and ('.jpg' in json_obj or '.png' in json_obj or '.jpeg' in json_obj):
                return json_obj
                
        return None
    
    def generate_wait_message(self) -> str:
        """生成等待消息"""
        messages = [
            "正在绘制图片，请稍候...",
            "AI画笔正在挥舞，请稍等片刻...",
            "正在创作中，马上就好...",
            "AI正在发挥创意，请耐心等待...",
            "正在将想象变为现实，稍等片刻..."
        ]
        return random.choice(messages)
    
    async def send_image(self, group_id, message_id, image_url, description=None, translation=None):
        """发送图片消息，自动尝试多种发送方式"""
        try:
            # 方式1: 使用Reply和Image组合
            message = MessageChain([
                Reply(message_id),
                Image(image_url)
            ])
            await self.api.post_group_msg(group_id, rtf=message)
            return True
        except Exception:
            try:
                # 方式2: 只使用Image
                message = MessageChain([
                    Image(image_url)
                ])
                await self.api.post_group_msg(group_id, rtf=message)
                return True
            except Exception:
                try:
                    # 方式3: 使用Text+Image
                    text_content = "已完成绘制！"
                    if description:
                        text_content += f"\n描述: {description}"
                    if translation:
                        text_content += f"\n翻译: {translation}"
                    
                    message = MessageChain([
                        Text(text_content + "\n"),
                        Image(image_url)
                    ])
                    await self.api.post_group_msg(group_id, rtf=message)
                    return True
                except Exception:
                    # 最后的尝试: 仅发送文本和链接
                    text_content = "已完成绘制，但发送图片时出错。"
                    if description:
                        text_content += f"\n描述: {description}"
                    if translation:
                        text_content += f"\n翻译: {translation}"
                    text_content += f"\n图片链接: {image_url}"
                    
                    await self.api.post_group_msg(group_id, text=text_content)
                    return True
        return False

    def get_help_text(self) -> str:
        """获取帮助文本"""
        help_text = f"""
🎨 AI绘图插件帮助 v{self.version}

📝 基本命令：
• /画图 [描述] - 根据描述生成图片
• /随机画图 - 使用随机标签生成图片
• /画图帮助 - 显示此帮助信息
• /画图模型 - 查看可用模型列表

🎯 高级命令：
• /画图 [描述] -m [模型索引] - 指定模型生成
• /画图 [描述] -s [尺寸] - 指定尺寸 (如: 512x768)
• /画图 [描述] -cfg [数值] - 指定CFG强度 (1-10)
• /画图 [描述] -steps [数值] - 指定生成步数 (1-50)

📋 使用示例：
• /画图 一只可爱的猫咪
• /画图 动漫风格的女孩 -m 3 -s 768x512
• /画图 风景画 -cfg 8.5 -steps 30

🤖 可用模型 (0-7为图片生成，8-9为图片编辑)：
{self.get_models_text()}

💡 提示：
• 支持中文描述，会自动翻译为英文
• 建议使用详细的描述词获得更好效果
• 生成时间约1-2分钟，请耐心等待
"""
        return help_text.strip()

    def get_models_text(self) -> str:
        """获取模型列表文本"""
        models_text = ""
        for idx, name in self.models.items():
            if idx <= 7:  # 只显示图片生成模型
                models_text += f"• {idx}: {name}\n"
        return models_text.strip()

    def parse_advanced_params(self, message: str) -> tuple:
        """解析高级参数"""
        # 提取基本prompt
        parts = message.split(' -')
        prompt = parts[0].strip()

        # 默认参数
        model_index = None
        width = None
        height = None
        cfg = None
        steps = None

        # 解析参数
        for part in parts[1:]:
            part = part.strip()
            if part.startswith('m '):
                try:
                    model_index = int(part[2:].strip())
                    if model_index < 0 or model_index > 7:  # 只允许图片生成模型
                        model_index = None
                except:
                    pass
            elif part.startswith('s '):
                try:
                    size = part[2:].strip()
                    if 'x' in size:
                        w, h = size.split('x')
                        width = max(64, min(2048, int(w.strip())))
                        height = max(64, min(2048, int(h.strip())))
                except:
                    pass
            elif part.startswith('cfg '):
                try:
                    cfg = max(1.0, min(10.0, float(part[4:].strip())))
                except:
                    pass
            elif part.startswith('steps '):
                try:
                    steps = max(1, min(50, int(part[6:].strip())))
                except:
                    pass

        return prompt, model_index, width, height, cfg, steps

    @bot.group_event()
    # @feature_required("AI绘图","画图")
    async def handle_group_message(self, event: GroupMessage):
        """处理群消息事件"""
        message = event.raw_message.strip()

        # 帮助命令
        if message in ["/画图帮助", "/画图 帮助", "/ai画图帮助"]:
            await self.api.post_group_msg(event.group_id, text=self.get_help_text())
            return

        # 模型列表命令
        if message in ["/画图模型", "/画图 模型"]:
            models_text = f"🤖 可用模型列表：\n\n{self.get_models_text()}\n\n💡 使用方法：/画图 [描述] -m [模型索引]"
            await self.api.post_group_msg(event.group_id, text=models_text)
            return

        # 检查是否是画图命令
        if message.startswith("/画图"):
            # 检查API密钥
            if not self.SD_API_KEY:
                await self.api.post_group_msg(event.group_id, text="❌ API密钥未配置，请联系管理员在config.yaml中设置ai_drawing.api_key")
                return

            # 提取prompt和参数
            prompt_part = message[4:].strip()

            if not prompt_part:
                await self.api.post_group_msg(event.group_id, text="请在/画图后面添加描述，例如：/画图 一只可爱的猫\n输入 /画图帮助 查看详细使用方法")
                return

            # 解析高级参数
            prompt, model_index, width, height, cfg, steps = self.parse_advanced_params(prompt_part)

            # 生成参数信息
            param_info = []
            if model_index is not None:
                param_info.append(f"模型: {self.models.get(model_index, '未知')}")
            if width and height:
                param_info.append(f"尺寸: {width}x{height}")
            if cfg is not None:
                param_info.append(f"CFG: {cfg}")
            if steps is not None:
                param_info.append(f"步数: {steps}")

            # 发送等待消息
            wait_msg = self.generate_wait_message()
            if param_info:
                wait_msg += f"\n参数: {', '.join(param_info)}"
            await self.api.post_group_msg(event.group_id, text=wait_msg)

            try:
                # 如果是中文，翻译为英文
                english_prompt = await self.translate_to_english(prompt)

                # 确保提示词中有足够的描述性内容
                if len(english_prompt) < 10:
                    english_prompt += ", anime style, high quality, detailed"

                # 添加重试机制
                for retry in range(self.max_retries):
                    try:
                        # 调用API生成图片，传入解析的参数
                        image_url = await self.generate_image(
                            english_prompt,
                            model_index=model_index,
                            width=width,
                            height=height,
                            cfg=cfg,
                            steps=steps
                        )

                        if image_url:
                            # 构建描述信息
                            description = f"原始描述: {prompt}"
                            if param_info:
                                description += f"\n参数: {', '.join(param_info)}"

                            # 发送图片
                            success = await self.send_image(
                                event.group_id,
                                event.message_id,
                                image_url,
                                description,
                                f"英文提示词: {english_prompt}"
                            )
                            if success:
                                break  # 成功发送，跳出重试循环

                        # 如果重试次数未用完，且没有成功获取图片，则重试
                        if retry < self.max_retries - 1 and not image_url:
                            await self.api.post_group_msg(event.group_id, text=f"第{retry+1}次尝试失败，正在重试...")
                        elif retry == self.max_retries - 1 and not image_url:
                            await self.api.post_group_msg(event.group_id, text="绘制失败，已达到最大重试次数。API可能暂时不可用或配置有误。")

                    except Exception as e:
                        if retry == self.max_retries - 1:
                            raise  # 最后一次尝试时，将错误向上传递
            except Exception as e:
                await self.api.post_group_msg(event.group_id, text=f"绘制过程中发生错误: {str(e)[:100]}")
        
        # 随机画图命令
        elif message.strip() == "/随机画图":
            # 检查API密钥
            if not self.SD_API_KEY:
                await self.api.post_group_msg(event.group_id, text="❌ API密钥未配置，请联系管理员在config.yaml中设置ai_drawing.api_key")
                return

            # 发送等待消息
            await self.api.post_group_msg(event.group_id, text=self.generate_wait_message())

            try:
                # 获取随机标签
                random_tag = await self.get_random_tag()

                if not random_tag:
                    await self.api.post_group_msg(event.group_id, text="获取随机标签失败，请稍后再试。")
                    return

                # 添加重试机制
                for retry in range(self.max_retries):
                    try:
                        # 调用API生成图片
                        image_url = await self.generate_image(random_tag)

                        if image_url:
                            # 发送随机标签和图片
                            message = MessageChain([
                                Reply(event.message_id),
                                Text(f"🎲 随机画图\n{random_tag}\n"),
                                Image(image_url)
                            ])

                            try:
                                await self.api.post_group_msg(event.group_id, rtf=message)
                                break  # 成功发送，跳出重试循环
                            except Exception:
                                # 备用发送方式：先发文本，再发图片
                                await self.api.post_group_msg(event.group_id, text=f"🎲 随机画图\n{random_tag}")
                                success = await self.send_image(
                                    event.group_id,
                                    event.message_id,
                                    image_url,
                                    "随机生成的图片"
                                )
                                if success:
                                    break

                        # 如果重试次数未用完，且没有成功获取图片，则重试
                        if retry < self.max_retries - 1 and not image_url:
                            await self.api.post_group_msg(event.group_id, text=f"第{retry+1}次尝试失败，正在重试...")
                        elif retry == self.max_retries - 1 and not image_url:
                            await self.api.post_group_msg(event.group_id, text="绘制失败，已达到最大重试次数。API可能暂时不可用或配置有误。")

                    except Exception as e:
                        if retry == self.max_retries - 1:
                            raise  # 最后一次尝试时，将错误向上传递
            except Exception as e:
                await self.api.post_group_msg(event.group_id, text=f"随机画图过程中发生错误: {str(e)[:100]}")
