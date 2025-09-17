import re
import base64
import os
import logging
import asyncio
import subprocess
import sys
from typing import Dict, Optional, Any
from meme_generator import get_memes, Meme, search_memes
from meme_generator.tools import MemeProperties, MemeSortBy, render_meme_list
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from utils.config_manager import get_config
from ncatbot.core.message import GroupMessage
from .meme_utils import get_avatar, generate_meme, get_member_name, handle_avatar_and_name, cleanup_thread_pool
from utils.group_forward_msg import send_group_msg_cq

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class MemeCreator(BasePlugin):
    name = "MemeCreator"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)
        self.memes: Dict[str, Meme] = {}

        # 统计信息
        self.meme_created_count = 0
        self.help_count = 0
        self.list_count = 0
        self.error_count = 0

        # 异步生成状态管理
        self.generating_users = set()  # 正在生成表情包的用户集合

        # 预加载的表情包关键词列表（用于快速检查）
        self.known_keywords = set()

    async def on_load(self):
        """插件加载时初始化"""
        try:
            await self._ensure_meme_resources()
            self.memes = {meme.key: meme for meme in get_memes()}

            # 构建已知关键词列表
            self._build_known_keywords()

            _log.info(f"MemeCreator v{self.version} 插件已加载，共加载 {len(self.memes)} 个表情包，{len(self.known_keywords)} 个关键词")
        except Exception as e:
            _log.error(f"MemeCreator插件加载失败: {e}")
            # 即使加载失败也要初始化空字典，避免后续错误
            self.memes = {}
            self.known_keywords = set()

    def _build_known_keywords(self):
        """构建已知的表情包关键词列表"""
        self.known_keywords.clear()

        # 添加表情包的key作为关键词
        for meme_key in self.memes.keys():
            self.known_keywords.add(meme_key.lower())

        # 添加表情包的关键词
        for meme in self.memes.values():
            if hasattr(meme, 'keywords') and meme.keywords:
                for keyword in meme.keywords:
                    self.known_keywords.add(keyword.lower())

        # 手动添加一些常见的中文关键词映射
        common_keywords = {
            "摸摸": "petpet",
            "摸头": "petpet",
            "拍拍": "petpet",
            "举牌": "hold_tight",
            "抱紧": "hold_tight",
            "鲁迅说": "luxun_say",
            "鲁迅": "luxun_say"
        }

        for cn_keyword, en_key in common_keywords.items():
            if en_key in self.memes:
                self.known_keywords.add(cn_keyword.lower())

        # 调试：输出一些关键词样例
        sample_keywords = list(self.known_keywords)[:10]
        _log.info(f"构建关键词列表完成，共 {len(self.known_keywords)} 个关键词")
        _log.info(f"关键词样例: {sample_keywords}")

        # 特别检查"摸摸"是否在列表中
        if "摸摸" in self.known_keywords:
            _log.info("✅ '摸摸' 关键词已加载")
        else:
            _log.warning("❌ '摸摸' 关键词未找到")
            # 查找包含"摸"的关键词
            momo_keywords = [k for k in self.known_keywords if "摸" in k]
            _log.info(f"包含'摸'的关键词: {momo_keywords}")

    async def _ensure_meme_resources(self):
        """确保表情包资源存在，如果不存在则自动下载"""
        try:
            # 检查是否有表情包资源
            memes = get_memes()
            if not memes:
                _log.warning("未找到表情包资源，开始自动下载...")
                await self._download_meme_resources()
                # 重新获取表情包列表
                memes = get_memes()
                if not memes:
                    _log.error("自动下载表情包资源失败")
                else:
                    _log.info(f"成功下载表情包资源，共 {len(memes)} 个")
            else:
                _log.info(f"表情包资源已存在，共 {len(memes)} 个")
        except Exception as e:
            _log.error(f"检查表情包资源时出错: {e}")

    async def _download_meme_resources(self):
        """下载表情包资源"""
        try:
            _log.info("开始下载表情包资源...")

            # 获取插件目录路径
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            meme_exe_path = os.path.join(plugin_dir, "meme.exe")

            # 获取代理配置
            try:
                config = get_config()
                proxy_url = config.get('proxy', '')
                _log.info(f"使用代理配置: {proxy_url}")
            except Exception as e:
                _log.warning(f"获取代理配置失败: {e}")
                proxy_url = "http://127.0.0.1:1100"  # 默认代理

            # 设置环境变量
            env = os.environ.copy()
            if proxy_url:
                env['HTTP_PROXY'] = proxy_url
                env['HTTPS_PROXY'] = proxy_url
                env['http_proxy'] = proxy_url
                env['https_proxy'] = proxy_url
                _log.info(f"设置代理环境变量: {proxy_url}")


            else:
                _log.warning("未配置代理，使用直连")

            # 尝试多种下载方式
            download_commands = []

            # 优先使用插件目录中的meme.exe
            if os.path.exists(meme_exe_path):
                download_commands.append([meme_exe_path, "download"])
                _log.info(f"找到本地meme.exe: {meme_exe_path}")

            # 备用下载方式
            download_commands.extend([
                ["meme", "download"],  # 系统PATH中的meme命令
                [sys.executable, "-m", "meme_generator.cli", "download"],  # Python模块方式
                [sys.executable, "-m", "meme_generator", "download"],  # 备用模块方式
            ])

            for cmd in download_commands:
                try:
                    _log.info(f"尝试命令: {' '.join(cmd)}")
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=plugin_dir,  # 设置工作目录为插件目录
                        env=env  # 使用包含代理的环境变量
                    )

                    stdout, stderr = await process.communicate()

                    if process.returncode == 0:
                        _log.info("表情包资源下载成功")
                        output_msg = stdout.decode('utf-8', errors='ignore')
                        _log.debug(f"下载输出: {output_msg}")
                        return True
                    else:
                        error_msg = stderr.decode('utf-8', errors='ignore')
                        _log.warning(f"命令失败 (返回码: {process.returncode}): {error_msg}")

                        # 如果是网络相关错误，提示代理问题
                        if any(keyword in error_msg.lower() for keyword in ['network', 'connection', 'timeout', 'proxy', '网络', '连接']):
                            _log.warning(f"可能是网络或代理问题，当前代理: {proxy_url}")

                except Exception as e:
                    _log.warning(f"命令执行失败: {e}")
                    continue

            # 如果命令行方式都失败，尝试直接使用Python代码下载
            try:
                _log.info("尝试使用Python代码直接下载...")
                import meme_generator

                # 检查是否有下载相关的模块或函数
                if hasattr(meme_generator, 'download'):
                    await asyncio.get_event_loop().run_in_executor(None, meme_generator.download)
                    _log.info("表情包资源下载成功（Python调用）")
                    return True
                else:
                    _log.warning("未找到下载函数")

            except Exception as e:
                _log.error(f"Python代码下载失败: {e}")

            _log.error("所有下载方式都失败了")
            return False

        except Exception as e:
            _log.error(f"下载表情包资源时出错: {e}")
            return False



    async def show_help(self, group_id: int):
        """显示帮助信息"""
        help_text = """🎭 表情包制作插件帮助

🎯 功能说明：
制作各种有趣的表情包，支持文字和图片自定义

🔍 使用方法：
• /m ls - 查看所有可用表情包列表
• 关键词 [文字] [@用户] - 制作表情包
• /m 序号 [文字] [@用户] - 通过序号制作表情包
• /表情包帮助 - 显示此帮助信息
• /表情包统计 - 查看使用统计

💡 使用示例：
摸摸 @某人
/m 1 你好
鲁迅说 这句话我没说过
petpet @用户1 @用户2

📊 表情包类型：
• 头像类：需要用户头像（@用户或发送图片）
• 文字类：需要输入文字内容
• 混合类：同时需要头像和文字

🎨 制作技巧：
• 可以@多个用户使用多个头像
• 可以发送图片替代头像
• 文字内容用空格分隔
• 支持中英文混合输入
• 使用完整关键词避免误触（如"摸摸"而非"摸"）

✨ 特色功能：
• 🎭 丰富的表情包模板
• 🖼️ 自动头像获取和处理
• 📝 智能文字排版
• 🎯 关键词快速匹配
• 📊 详细的使用统计

⚠️ 注意事项：
• 不同表情包需要的图片和文字数量不同
• 首次使用会自动下载表情包资源
• 部分表情包可能需要特定的参数
• 建议先查看表情包列表了解用法

🔧 版本: v2.0.0
💡 提示：发送"/m ls"查看所有可用的表情包！"""

        await self.api.post_group_msg(group_id, text=help_text)
        self.help_count += 1

    async def show_statistics(self, group_id: int):
        """显示使用统计"""
        stats_text = f"""📊 表情包制作插件统计

🎭 表情包数量: {len(self.memes)}
📈 制作成功: {self.meme_created_count} 次
📋 查看列表: {self.list_count} 次
❓ 查看帮助: {self.help_count} 次
❌ 制作失败: {self.error_count} 次

💡 使用提示：
• 发送"/m ls"查看表情包列表
• 发送"/表情包帮助"查看详细帮助
• 支持关键词和序号两种制作方式"""

        await self.api.post_group_msg(group_id, text=stats_text)

    def _is_known_meme_keyword(self, keyword: str) -> bool:
        """
        检查是否是已知的表情包关键词
        使用预加载的关键词列表进行快速检查
        """
        if not keyword or not self.known_keywords:
            _log.debug(f"关键词检查失败: keyword='{keyword}', known_keywords_count={len(self.known_keywords)}")
            return False

        # 检查是否在预加载的关键词列表中
        result = keyword.lower() in self.known_keywords
        _log.debug(f"关键词 '{keyword}' 检查结果: {result}")
        return result

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        raw_message = event.raw_message.strip()
        group_id = event.group_id
        user_id = event.user_id

        # 移除状态检查，允许用户同时使用其他命令
        # 表情包生成是后台任务，不应该阻塞其他功能

        # 帮助命令
        if raw_message in ["/表情包帮助", "/meme帮助", "表情包帮助"]:
            await self.show_help(group_id)
            return
        elif raw_message in ["/表情包统计", "/meme统计", "表情包统计"]:
            await self.show_statistics(group_id)
            return

        # 表情包列表命令
        if raw_message == "/m ls":
            try:
                if not self.memes:
                    await self.api.post_group_msg(group_id=group_id, text="❌ 表情包资源未加载，请稍后再试")
                    return

                keywords_image = render_meme_list(sort_by=MemeSortBy.Key, add_category_icon=True)
                base64_image = base64.b64encode(keywords_image).decode("utf-8")
                cq_image = f"[CQ:image,file=base64://{base64_image}]"
                await send_group_msg_cq(group_id, cq_image)
                self.list_count += 1
                _log.info(f"用户 {user_id} 在群 {group_id} 查看了表情包列表")
            except Exception as e:
                _log.error(f"生成表情包列表失败: {e}")
                await self.api.post_group_msg(group_id=group_id, text=f"❌ 生成表情包列表失败: {str(e)}")
                self.error_count += 1
            return

        # 检查表情包资源是否加载
        if not self.memes:
            return  # 静默返回，避免频繁提示

        # 新的识别策略：只处理明确的表情包触发条件
        keyword_to_use = None

        # 1. 处理 /m 序号命令
        if raw_message.startswith("/m "):
            match = re.match(r"/m\s+(\d+)", raw_message)
            if not match:
                return
            index = int(match.group(1)) - 1
            if not (0 <= index < len(self.memes)):
                await self.api.post_group_msg(group_id=group_id, text=f"❌ 无效的表情包序号: {index + 1}")
                self.error_count += 1
                return
            # /m 命令有效，使用原始消息作为关键词
            keyword_to_use = raw_message

        # 2. 处理关键词命令：必须是已知的表情包关键词
        else:
            # 提取第一个词作为关键词
            first_word = raw_message.split()[0] if raw_message.split() else ""
            if not first_word:
                return

            # 排除其他斜杠命令
            if first_word.startswith("/"):
                return

            # 排除纯数字
            if first_word.isdigit():
                return

            # 核心检查：必须是已知的表情包关键词才处理
            if not self._is_known_meme_keyword(first_word):
                _log.debug(f"关键词 '{first_word}' 不在已知列表中，跳过处理")
                return

            keyword_to_use = first_word

        # 立即响应用户，表情包正在后台生成
        await self.api.post_group_msg(group_id=group_id, text="🎨 表情包生成中，请稍候...")

        # 创建后台任务生成表情包，不阻塞主线程
        task = asyncio.create_task(self._generate_meme_task(keyword_to_use, event, user_id, group_id, raw_message))
        # 添加异常处理回调
        task.add_done_callback(self._handle_task_exception)

    async def _generate_meme_task(self, keyword, event, user_id, group_id, raw_message):
        """后台任务：查找并生成表情包"""
        # 标记用户开始生成表情包（用于统计，不阻塞其他命令）
        self.generating_users.add(user_id)

        try:
            # 在后台任务中解析消息和查找表情包
            meme = None
            text_list = []
            qq_numbers = []

            # 解析消息（在后台进行）
            try:
                for segment in event.message:
                    if segment["type"] == "text":
                        text_content = segment["data"]["text"].strip()
                        if text_content:
                            parts = text_content.split()
                            if len(parts) > 1:
                                text_list.extend(parts[1:])  # 跳过第一个词（关键词）
                    elif segment["type"] == "at":
                        qq_numbers.append(segment["data"]["qq"])
            except Exception as e:
                _log.error(f"后台解析消息时出错: {e}")
                return

            # 检查是否是 /m 指令
            if keyword.startswith("/m"):
                match = re.match(r"/m\s+(\d+)", raw_message)
                if match:
                    index = int(match.group(1)) - 1
                    if 0 <= index < len(self.memes):
                        meme = list(self.memes.values())[index]
            elif not keyword.isdigit():  # 避免纯数字触发
                # 在后台任务中进行表情包搜索
                _log.info(f"后台搜索表情包: {keyword}")
                try:
                    memes = search_memes(keyword)
                    if not memes:
                        _log.debug(f"未找到关键词 '{keyword}' 对应的表情包")
                        return  # 静默返回
                except Exception as e:
                    _log.error(f"搜索表情包时出错: {e}")
                    return

                # 如果返回的是字符串列表，将其转换为表情包对象
                if isinstance(memes, list) and all(isinstance(m, str) for m in memes):
                    memes = [self.memes.get(m) for m in memes if m in self.memes]

                # 默认选择第一个表情包
                meme = memes[0] if isinstance(memes, list) else memes

                # 验证表情包是否有效
                if not meme or not hasattr(meme, 'key') or meme.key not in self.memes:
                    _log.debug(f"表情包验证失败: {keyword}")
                    return  # 静默返回

            if not meme:
                _log.debug(f"未找到有效的表情包: {keyword}")
                return

            _log.info(f"找到表情包: {meme.key}")

            # 处理图片和用户信息
            image_data = []
            names = []
            # 检查是否有用户发送的图片
            image_segments = [segment for segment in event.message if segment["type"] == "image"]
            if image_segments:
                for segment in image_segments:
                    image_url = segment["data"].get("url")
                    if image_url:
                        try:
                            # 使用 get_avatar 函数下载图片数据
                            image_data_io = await get_avatar(image_url)
                            if image_data_io:
                                image_data.append(image_data_io)
                                names.append(f"用户图片_{len(image_data)}")
                            else:
                                _log.warning(f"下载用户图片失败: {image_url}")
                        except Exception as e:
                            _log.error(f"处理用户图片失败: {e}")

            # 如果没有用户图片，处理多个 @ 的头像和名称
            if not image_data and qq_numbers:
                for qq_number in qq_numbers:
                    try:
                        avatar_data, name = await handle_avatar_and_name(self.api, group_id, int(qq_number))
                        if avatar_data:
                            image_data.append(avatar_data)
                            names.append(name or f"用户_{qq_number}")
                        else:
                            _log.warning(f"获取用户 {qq_number} 头像失败")
                    except Exception as e:
                        _log.error(f"处理用户 {qq_number} 头像时出错: {e}")

            # 如果需要的图片数量大于已提供的头像或用户图片数量，用发送者的头像补充
            while len(image_data) < meme.info.params.min_images:
                try:
                    avatar_data, name = await handle_avatar_and_name(self.api, group_id, user_id)
                    if avatar_data:
                        image_data.append(avatar_data)
                        names.append(name or f"用户_{user_id}")
                    else:
                        await self.api.post_group_msg(group_id=group_id, text="❌ 获取头像失败，无法生成表情包")
                        self.error_count += 1
                        return
                except Exception as e:
                    _log.error(f"获取发送者头像时出错: {e}")
                    await self.api.post_group_msg(group_id=group_id, text="❌ 获取头像失败，无法生成表情包")
                    self.error_count += 1
                    return

        except Exception as e:
            _log.error(f"处理图片数据时出错: {e}")
            await self.api.post_group_msg(group_id=group_id, text=f"❌ 处理图片数据失败: {str(e)}")
            self.error_count += 1
            return

        # 参数验证和表情包生成
        try:
            # 验证文字数量
            min_texts = meme.info.params.min_texts
            max_texts = meme.info.params.max_texts

            if min_texts == 0 and max_texts == 0:
                text_list = []
            elif len(text_list) < min_texts or len(text_list) > max_texts:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text=f"❌ 文字数量不匹配: 需要 {min_texts} ~ {max_texts} 个，实际 {len(text_list)} 个"
                )
                self.error_count += 1
                return

            # 验证图片数量
            min_images = meme.info.params.min_images
            max_images = meme.info.params.max_images

            if len(image_data) < min_images or len(image_data) > max_images:
                await self.api.post_group_msg(
                    group_id=group_id,
                    text=f"❌ 图片数量不匹配: 需要 {min_images} ~ {max_images} 张，实际 {len(image_data)} 张"
                )
                self.error_count += 1
                return

            # 如果没有图片但需要图片，使用发送者头像
            if len(image_data) == 0 and min_images > 0:
                avatar_data, name = await handle_avatar_and_name(self.api, group_id, user_id)
                if not avatar_data:
                    await self.api.post_group_msg(group_id=group_id, text="❌ 获取头像失败，无法生成表情包")
                    self.error_count += 1
                    return
                image_data.append(avatar_data)
                names.append(name or f"用户_{user_id}")

            # 生成表情包 - 异步处理
            _log.info(f"开始异步生成表情包: {meme.key}, 用户: {user_id}, 群: {group_id}")

            meme_image = await generate_meme(meme, image_data, text_list, {}, names)

            if isinstance(meme_image, str):
                # 返回的是错误信息
                error_msg = meme_image

                # 如果是资源缺失错误，尝试自动下载资源
                if "图片资源缺失" in error_msg or "ImageAssetMissing" in error_msg:
                    _log.warning(f"检测到资源缺失: {meme.key}")

                    # 检查是否已经在下载中，避免重复下载
                    if hasattr(self, '_downloading') and self._downloading:
                        await self.api.post_group_msg(group_id=group_id, text="⏳ 资源正在下载中，请稍后再试...")
                        return

                    self._downloading = True
                    await self.api.post_group_msg(group_id=group_id, text="🔄 检测到资源缺失，正在自动下载...")

                    try:
                        # 尝试自动下载资源
                        download_success = await self._download_meme_resources()

                        if download_success:
                            # 下载成功，重新加载表情包并尝试生成
                            try:
                                # 保存原始的meme key
                                original_meme_key = meme.key

                                # 重新加载表情包
                                _log.info("重新加载表情包资源...")
                                self.memes = {m.key: m for m in get_memes()}
                                reloaded_meme = self.memes.get(original_meme_key)

                                if reloaded_meme:
                                    _log.info(f"重新尝试异步生成表情包: {original_meme_key}")
                                    await self.api.post_group_msg(group_id=group_id, text="✅ 资源下载成功，重新生成中...")

                                    # 重新异步生成表情包
                                    meme_image = await generate_meme(reloaded_meme, image_data, text_list, {}, names)

                                    if isinstance(meme_image, str):
                                        # 仍然失败，可能是其他问题
                                        _log.error(f"重新生成失败: {meme_image}")
                                        await self.api.post_group_msg(group_id=group_id, text=f"❌ 重新生成失败: {meme_image}")
                                        self.error_count += 1
                                        return
                                    elif not meme_image:
                                        _log.error("重新生成返回空结果")
                                        await self.api.post_group_msg(group_id=group_id, text="❌ 重新生成失败：返回空结果")
                                        self.error_count += 1
                                        return
                                    else:
                                        # 成功生成，更新变量并继续执行
                                        _log.info(f"重新生成成功: {original_meme_key}")
                                        meme = reloaded_meme
                                        # 继续执行后面的发送逻辑，不要return
                                else:
                                    _log.error(f"重新加载后找不到表情包: {original_meme_key}")
                                    await self.api.post_group_msg(group_id=group_id, text="❌ 重新加载表情包失败")
                                    self.error_count += 1
                                    return
                            except Exception as e:
                                _log.error(f"重新生成表情包时出错: {e}")
                                await self.api.post_group_msg(group_id=group_id, text=f"❌ 重新生成时出错: {str(e)}")
                                self.error_count += 1
                                return
                        else:
                            # 下载失败，提供手动解决方案
                            try:
                                config = get_config()
                                proxy_info = config.get('proxy', '未配置')
                            except:
                                proxy_info = '未知'

                            help_msg = f"""❌ 表情包资源缺失且自动下载失败

🔧 解决方案：
1. 检查代理配置：当前代理 {proxy_info}
2. 手动下载资源：在命令行运行 `meme download`
3. 或者尝试其他表情包，如：摸摸、举牌、鲁迅说

💡 提示：
• 确保代理服务正常运行
• 检查网络连接
• 联系管理员获取帮助"""

                            await self.api.post_group_msg(group_id=group_id, text=help_msg)
                            self.error_count += 1
                            return
                    finally:
                        # 无论成功失败都要重置下载状态
                        self._downloading = False
                else:
                    await self.api.post_group_msg(group_id=group_id, text=f"❌ 生成表情包失败: {error_msg}")
                    self.error_count += 1
                    return

            if not meme_image:
                await self.api.post_group_msg(group_id=group_id, text="❌ 生成表情包失败")
                self.error_count += 1
                return

            # 发送表情包
            base64_image = base64.b64encode(meme_image).decode('utf-8')
            cq_image = f"[CQ:image,file=base64://{base64_image}]"
            await send_group_msg_cq(group_id, cq_image)

            # 更新统计
            self.meme_created_count += 1
            _log.info(f"成功生成表情包: {meme.key}, 用户: {user_id}, 群: {group_id}")

        except Exception as e:
            _log.error(f"生成表情包时出错: {e}")
            await self.api.post_group_msg(group_id=group_id, text=f"❌ 生成表情包失败: {str(e)}")
            self.error_count += 1
        finally:
            # 无论成功失败都要清除用户生成状态
            self.generating_users.discard(user_id)

    def _handle_task_exception(self, task):
        """处理后台任务异常"""
        try:
            task.result()  # 这会重新抛出任务中的异常
        except Exception as e:
            _log.error(f"后台表情包生成任务异常: {e}")

    async def on_unload(self):
        """插件卸载时清理资源"""
        try:
            _log.info("MemeCreator插件正在卸载，清理资源...")
            cleanup_thread_pool()
            _log.info("MemeCreator插件资源清理完成")
        except Exception as e:
            _log.error(f"插件卸载时清理资源失败: {e}")
