"""
Setu插件 - 基于Lolicon API v2的高级涩图功能
支持标签搜索、作者搜索、尺寸选择、AI过滤等高级功能
"""
import aiohttp
import re
import random
import string
import base64
import time
from typing import List, Dict, Any, Optional, Union
from io import BytesIO
from datetime import datetime

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.utils.logger import get_log

from PluginManager.plugin_manager import feature_required
from utils.onebot_v11_handler import (
    send_forward_msg,
    create_forward_node,
    create_text_segment,
    create_image_segment
)
from utils.config_manager import get_config
from utils.error_handler import retry_async, safe_async

bot = CompatibleEnrollment
_log = get_log()

class Setu(BasePlugin):
    """Setu插件 - 基于Lolicon API v2的高级涩图功能"""

    name = "Setu"
    version = "3.0.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 请求限制
        self.last_request_time = {}
        self.request_interval = 3  # 3秒间隔

        # 缓存机制
        self.cache = {}
        self.cache_ttl = 300  # 5分钟缓存

        # 支持的尺寸
        self.supported_sizes = ["original", "regular", "small", "thumb", "mini"]

        # 支持的排序方式
        self.supported_orders = ["date", "date_d", "popular", "popular_d"]

    def _check_request_limit(self, user_id: int) -> bool:
        """检查用户请求频率限制"""
        current_time = time.time()
        if user_id in self.last_request_time:
            time_diff = current_time - self.last_request_time[user_id]
            if time_diff < self.request_interval:
                return False

        self.last_request_time[user_id] = current_time
        return True

    def _get_remaining_cooldown(self, user_id: int) -> int:
        """获取剩余冷却时间"""
        if user_id not in self.last_request_time:
            return 0

        current_time = time.time()
        time_diff = current_time - self.last_request_time[user_id]
        remaining = self.request_interval - time_diff
        return max(0, int(remaining))

    def _get_cache_key(self, **kwargs) -> str:
        """生成缓存键"""
        cache_data = {k: v for k, v in kwargs.items() if v is not None}
        return f"setu_{hash(str(sorted(cache_data.items())))}"

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache:
            return False

        cache_time, _ = self.cache[cache_key]
        return time.time() - cache_time < self.cache_ttl

    def _get_cached_result(self, cache_key: str) -> Optional[List[Dict[str, Any]]]:
        """获取缓存结果"""
        if self._is_cache_valid(cache_key):
            _, result = self.cache[cache_key]
            # 验证缓存结果的类型
            if isinstance(result, list):
                return result
            else:
                _log.warning(f"缓存中的数据类型错误: {type(result)}, 清除缓存")
                del self.cache[cache_key]
                return None
        return None

    def _set_cache(self, cache_key: str, result: List[Dict[str, Any]]):
        """设置缓存"""
        self.cache[cache_key] = (time.time(), result)

        # 清理过期缓存
        current_time = time.time()
        expired_keys = [
            key for key, (cache_time, _) in self.cache.items()
            if current_time - cache_time > self.cache_ttl
        ]
        for key in expired_keys:
            del self.cache[key]

    async def on_load(self):
        """插件加载"""
        _log.info(f"{self.name} 插件已加载，版本: {self.version}")
        _log.info("支持的功能：标签搜索、作者搜索、尺寸选择、AI过滤、排序等")

        # 测试API连接
        try:
            test_result = await self._test_api_connection()
            if test_result:
                _log.info("API连接测试成功")
            else:
                _log.warning("API连接测试失败")
        except Exception as e:
            _log.error(f"API连接测试异常: {e}")

    async def _test_api_connection(self) -> bool:
        """测试API连接"""
        try:
            api_url = "https://api.lolicon.app/setu/v2"
            params = {"num": 1, "r18": 0}

            timeout = aiohttp.ClientTimeout(total=10, connect=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(api_url, params=params) as response:
                    _log.info(f"测试API响应状态: {response.status}")
                    if response.status == 200:
                        text = await response.text()
                        _log.info(f"测试API响应长度: {len(text)}")
                        try:
                            data = await response.json()
                            _log.info(f"测试API响应类型: {type(data)}")
                            if isinstance(data, dict):
                                _log.info(f"测试API响应键: {list(data.keys())}")
                                return True
                            else:
                                _log.error(f"API返回非字典类型: {type(data)}")
                                return False
                        except Exception as json_error:
                            _log.error(f"JSON解析失败: {json_error}")
                            _log.error(f"原始响应: {text[:200]}...")
                            return False
                    else:
                        _log.error(f"API测试失败，状态码: {response.status}")
                        return False
        except Exception as e:
            _log.error(f"API测试异常: {e}")
            return False



    @retry_async(max_attempts=3, delay=1.0)
    async def fetch_setu(self,
                        num: int = 1,
                        r18: int = 0,
                        tag: Optional[List[str]] = None,
                        keyword: Optional[str] = None,
                        uid: Optional[List[int]] = None,
                        size: Optional[List[str]] = None,
                        proxy: Optional[str] = None,
                        date_after: Optional[int] = None,
                        date_before: Optional[int] = None,
                        exclude_ai: bool = False) -> Optional[List[Dict[str, Any]]]:
        """
        调用 Lolicon API v2 获取涩图

        Args:
            num: 数量，范围 1-20
            r18: 0为非 R18，1为 R18，2为混合
            tag: 标签列表，支持多个标签
            keyword: 关键词搜索
            uid: 作者UID列表
            size: 图片尺寸列表 ["original", "regular", "small", "thumb", "mini"]
            proxy: 代理地址
            date_after: 在此日期之后的作品 (时间戳)
            date_before: 在此日期之前的作品 (时间戳)
            exclude_ai: 是否排除AI作品

        Returns:
            List[Dict]: 涩图数据列表或None
        """
        # 检查缓存
        try:
            cache_key = self._get_cache_key(
                num=num, r18=r18, tag=tag, keyword=keyword, uid=uid,
                size=size, date_after=date_after, date_before=date_before, exclude_ai=exclude_ai
            )
            _log.info(f"生成缓存键: {cache_key}")

            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                _log.info("返回缓存的涩图结果")
                return cached_result
        except Exception as cache_error:
            _log.error(f"缓存检查失败: {cache_error}")
            # 继续执行API请求

        api_url = "https://api.lolicon.app/setu/v2"
        params = {
            "num": num,
            "r18": r18,
        }

        # 添加可选参数
        # 根据Lolicon API v2文档，数组参数应该直接传递
        if tag:
            params["tag"] = tag

        if keyword:
            params["keyword"] = keyword

        if uid:
            params["uid"] = uid

        if size:
            params["size"] = size
        else:
            # 默认请求多个尺寸
            params["size"] = ["original", "regular"]

        if proxy:
            params["proxy"] = proxy

        if date_after:
            params["dateAfter"] = date_after

        if date_before:
            params["dateBefore"] = date_before

        if exclude_ai:
            params["excludeAI"] = True

        # 获取代理配置
        proxy_config = get_config("proxy", {})
        proxy_url = None

        # 支持字典和字符串两种代理配置格式
        if isinstance(proxy_config, dict):
            if proxy_config.get("enabled") and proxy_config.get("http"):
                proxy_url = proxy_config["http"]
        elif isinstance(proxy_config, str):
            # 直接使用字符串作为代理URL
            proxy_url = proxy_config
        else:
            _log.warning(f"代理配置格式不支持: {type(proxy_config)}")

        try:
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                _log.info(f"请求API: {api_url}, 参数: {params}")
                async with session.get(api_url, params=params, proxy=proxy_url) as response:
                    _log.info(f"API响应状态码: {response.status}")

                    if response.status == 200:
                        # 先获取原始文本，用于调试
                        response_text = await response.text()
                        _log.info(f"API响应内容: {response_text[:500]}...")  # 只记录前500字符

                        try:
                            # 尝试解析JSON
                            data = await response.json()
                        except Exception as json_error:
                            _log.error(f"JSON解析失败: {json_error}")
                            _log.error(f"响应内容: {response_text}")
                            return None

                        # 检查响应数据类型
                        if not isinstance(data, dict):
                            _log.error(f"API返回的不是字典类型，而是: {type(data)}")
                            _log.error(f"响应内容: {data}")
                            return None

                        if data.get("error"):
                            _log.error(f"API错误: {data['error']}")
                            return None

                        result = data.get("data", [])
                        _log.info(f"获取到 {len(result)} 张图片")

                        # 缓存结果
                        self._set_cache(cache_key, result)
                        return result
                    else:
                        response_text = await response.text()
                        _log.error(f"API请求失败，状态码: {response.status}")
                        _log.error(f"错误响应: {response_text}")
                        return None
        except Exception as e:
            _log.error(f"获取涩图失败: {e}")
            _log.error(f"异常类型: {type(e)}")
            import traceback
            _log.error(f"异常堆栈: {traceback.format_exc()}")
            return None

    @safe_async(default_return=None)
    async def fetch_and_modify_image(self, image_url: str) -> Optional[str]:
        """
        下载图片并在末尾添加随机字符串以修改 MD5
        
        Args:
            image_url: 图片URL
            
        Returns:
            str: 修改后的图片数据的 base64:// 格式，或None
        """
        try:
            proxy_config = get_config("proxy", {})
            proxy = None

            # 支持字典和字符串两种代理配置格式
            if isinstance(proxy_config, dict):
                if proxy_config.get("enabled") and proxy_config.get("http"):
                    proxy = proxy_config["http"]
            elif isinstance(proxy_config, str):
                # 直接使用字符串作为代理URL
                proxy = proxy_config
            else:
                _log.warning(f"代理配置格式不支持: {type(proxy_config)}")
            
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(image_url, proxy=proxy) as response:
                    if response.status == 200:
                        image_data = await response.read()

                        # 添加随机字符串修改MD5
                        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
                        modified_image_data = image_data + random_string.encode('utf-8')

                        # 返回 base64:// 格式
                        base64_data = base64.b64encode(modified_image_data).decode('utf-8')
                        return f"base64://{base64_data}"
                    else:
                        _log.warning(f"图片下载失败，状态码: {response.status}")
                        return None
        except Exception as e:
            import traceback
            _log.error(f"图片处理错误: {e}")
            _log.error(f"错误类型: {type(e).__name__}")
            _log.error(f"错误堆栈: {traceback.format_exc()}")
            return None

    async def send_setu(self, event: GroupMessage,
                        num: int = 1,
                        r18: int = 0,
                        tag: Optional[List[str]] = None,
                        keyword: Optional[str] = None,
                        uid: Optional[List[int]] = None,
                        exclude_ai: bool = False):
        """
        发送涩图到群聊

        Args:
            event: 群消息事件
            num: 数量
            r18: R18标志
            tag: 标签列表
            keyword: 关键词
            uid: 作者UID列表
            exclude_ai: 是否排除AI作品
        """
        try:
            # 获取涩图数据
            setu_data = await self.fetch_setu(
                num=num,
                r18=r18,
                tag=tag,
                keyword=keyword,
                uid=uid,
                exclude_ai=exclude_ai
            )

            if not setu_data:
                await self.api.post_group_msg(event.group_id, text="❌ 获取涩图失败，请稍后再试。")
                return

            # 构建合并转发消息
            forward_messages = []

            # 添加标题消息
            r18_text = "🔞 R18" if r18 == 1 else "🌟 全年龄" if r18 == 0 else "🎲 混合"

            # 构建搜索条件描述
            search_info = []
            if tag:
                search_info.append(f"🏷️ 标签: {', '.join(tag)}")
            if keyword:
                search_info.append(f"🔍 关键词: {keyword}")
            if uid:
                search_info.append(f"👤 作者UID: {', '.join(map(str, uid))}")
            if exclude_ai:
                search_info.append("🚫 排除AI作品")

            title_content = [
                create_text_segment(f"🎨 涩图推荐 ({r18_text})"),
                create_text_segment(f"\n📊 共 {len(setu_data)} 张图片")
            ]

            if search_info:
                title_content.append(create_text_segment(f"\n📋 搜索条件:\n{chr(10).join(search_info)}"))

            title_content.append(create_text_segment(f"\n⏰ 获取时间: {datetime.now().strftime('%H:%M:%S')}"))

            forward_messages.append(
                create_forward_node("涩图姬", event.self_id, title_content)
            )

            # 处理每张图片
            for i, item in enumerate(setu_data):
                try:
                    content_segments = []

                    # 基本信息
                    title = item.get("title", "未知标题")
                    author = item.get("author", "未知作者")
                    pid = item.get("pid", "未知")

                    # 处理标签
                    tags_data = item.get("tags", [])
                    if isinstance(tags_data, list):
                        tags = ", ".join(tags_data)
                    elif isinstance(tags_data, str):
                        tags = tags_data
                    else:
                        tags = str(tags_data)
                    
                    # 添加文本信息
                    content_segments.append(
                        create_text_segment(f"🎨 {title}")
                    )
                    content_segments.append(
                        create_text_segment(f"\n👤 作者: {author}")
                    )
                    content_segments.append(
                        create_text_segment(f"\n🆔 PID: {pid}")
                    )
                    if tags:
                        content_segments.append(
                            create_text_segment(f"\n🏷️ 标签: {tags}")
                        )
                    
                    # 处理图片
                    image_urls = item.get("urls", {})
                    image_url = None

                    # 验证image_urls是字典类型
                    if isinstance(image_urls, dict):
                        image_url = image_urls.get("original") or image_urls.get("regular")
                    else:
                        # 如果urls字段直接是字符串URL
                        if isinstance(image_urls, str):
                            image_url = image_urls

                    if image_url:
                        # 下载并修改图片
                        modified_image = await self.fetch_and_modify_image(image_url)
                        if modified_image:
                            content_segments.append(
                                create_text_segment("\n🖼️ 图片:")
                            )
                            content_segments.append(
                                create_image_segment(modified_image)
                            )
                        else:
                            content_segments.append(
                                create_text_segment(f"\n❌ 图片获取失败\n🔗 原链接: {image_url}")
                            )
                    else:
                        content_segments.append(
                            create_text_segment("\n❌ 无可用图片链接")
                        )
                    
                    # 创建转发节点
                    forward_messages.append(
                        create_forward_node(f"图片 {i+1}", event.self_id, content_segments)
                    )
                    
                except Exception as e:
                    _log.error(f"处理涩图 {i} 失败: {e}")
                    # 添加错误节点
                    error_content = [
                        create_text_segment(f"❌ 处理第 {i+1} 张图片时出错: {str(e)}")
                    ]
                    forward_messages.append(
                        create_forward_node(f"错误 {i+1}", event.self_id, error_content)
                    )

            # 发送合并转发消息
            success = await send_forward_msg(event.group_id, forward_messages)
            if not success:
                # 降级处理：发送简单文本消息
                await self.send_fallback_setu_info(event.group_id, setu_data)
                
        except Exception as e:
            _log.error(f"发送涩图失败: {e}")
            await self.api.post_group_msg(event.group_id, text=f"❌ 发送涩图时出错: {str(e)}")

    async def send_fallback_setu_info(self, group_id: int, setu_data: List[Dict[str, Any]]):
        """
        发送降级的涩图信息（当合并转发失败时）
        
        Args:
            group_id: 群号
            setu_data: 涩图数据列表
        """
        try:
            for i, item in enumerate(setu_data[:3]):  # 降级时只显示前3个
                title = item.get("title", "未知标题")
                author = item.get("author", "未知作者")
                pid = item.get("pid", "未知")
                tags = ", ".join(item.get("tags", [])[:5])  # 只显示前5个标签
                
                info_text = f"🎨 {title}\n"
                info_text += f"👤 作者: {author}\n"
                info_text += f"🆔 PID: {pid}\n"
                if tags:
                    info_text += f"🏷️ 标签: {tags}\n"
                
                await self.api.post_group_msg(group_id, text=info_text)
                
        except Exception as e:
            _log.error(f"发送降级涩图信息失败: {e}")

    def _parse_setu_command(self, message: str) -> Optional[Dict[str, Any]]:
        """
        解析涩图命令

        支持的命令格式：
        /涩图 [数量] [r18] [参数...]
        /涩图 3 0 tag:萝莉,白丝 keyword:可爱 uid:123456 noai

        Args:
            message: 原始消息

        Returns:
            Dict: 解析后的参数字典或None
        """
        # 基础命令匹配
        if not message.startswith("/涩图"):
            return None

        # 移除命令前缀
        args_str = message[3:].strip()
        if not args_str:
            return {"num": 1, "r18": 0}

        # 分割参数
        args = args_str.split()
        params = {"num": 1, "r18": 0}

        # 解析数字参数（数量和R18）
        numeric_args = []
        other_args = []

        for arg in args:
            if arg.isdigit():
                numeric_args.append(int(arg))
            else:
                other_args.append(arg)

        # 处理数字参数
        if len(numeric_args) >= 1:
            params["num"] = numeric_args[0]
        if len(numeric_args) >= 2:
            params["r18"] = numeric_args[1]

        # 处理其他参数
        for arg in other_args:
            if ":" in arg:
                key, value = arg.split(":", 1)
                if key == "tag":
                    params["tag"] = [t.strip() for t in value.split(",") if t.strip()]
                elif key == "keyword":
                    params["keyword"] = value
                elif key == "uid":
                    try:
                        params["uid"] = [int(u.strip()) for u in value.split(",") if u.strip().isdigit()]
                    except ValueError:
                        continue
            elif arg.lower() in ["noai", "no-ai", "excludeai"]:
                params["exclude_ai"] = True

        return params

    def _validate_setu_params(self, params: Dict[str, Any]) -> Optional[str]:
        """
        验证涩图参数

        Args:
            params: 参数字典

        Returns:
            str: 错误信息，None表示验证通过
        """
        # 验证数量
        if not (1 <= params.get("num", 1) <= 20):
            return "❌ 数量必须在 1-20 之间"

        # 验证R18标志
        if params.get("r18", 0) not in [0, 1, 2]:
            return "❌ R18标志无效，必须是 0(全年龄)、1(R18) 或 2(混合)"

        # 验证标签数量
        tags = params.get("tag", [])
        if tags and len(tags) > 10:
            return "❌ 标签数量不能超过10个"

        # 验证UID数量
        uids = params.get("uid", [])
        if uids and len(uids) > 5:
            return "❌ 作者UID数量不能超过5个"

        # 验证关键词长度
        keyword = params.get("keyword", "")
        if keyword and len(keyword) > 50:
            return "❌ 关键词长度不能超过50个字符"

        return None

    def _get_help_text(self) -> str:
        """获取帮助文本"""
        return """🎨 涩图功能使用说明

📝 基础命令格式：
• /涩图 - 获取1张全年龄涩图
• /涩图 3 - 获取3张全年龄涩图
• /涩图 3 0 - 获取3张全年龄涩图
• /涩图 1 1 - 获取1张R18涩图
• /涩图 2 2 - 获取2张混合内容涩图

🔍 高级搜索命令：
• /涩图 2 0 tag:萝莉,白丝 - 获取2张带指定标签的全年龄涩图
• /涩图 1 0 keyword:可爱 - 获取1张关键词搜索的全年龄涩图
• /涩图 1 0 uid:123456 - 获取指定作者的1张全年龄涩图
• /涩图 1 0 noai - 获取1张排除AI的全年龄涩图

💡 组合搜索示例：
• /涩图 3 0 tag:猫娘 keyword:可爱 noai
• /涩图 2 0 tag:萝莉,白丝 uid:123456

📊 参数说明：
• 数量：1-20张图片
• R18：0(全年龄) 1(R18) 2(混合)
• 标签：最多10个，用逗号分隔
• UID：最多5个作者，用逗号分隔
• 关键词：最多50个字符

⚠️ 注意事项：
• 请求间隔：3秒
• 支持缓存：5分钟
• 合并转发显示，失败时降级为文本
• 详细帮助：/帮助 涩图功能"""

    @bot.group_event()
    @feature_required("Setu", commands=["/涩图"])
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件

        支持的命令格式：
        /涩图 - 获取1张全年龄涩图
        /涩图 3 - 获取3张全年龄涩图
        /涩图 3 0 - 获取3张全年龄涩图
        /涩图 1 1 - 获取1张R18涩图
        /涩图 2 0 tag:萝莉,白丝 - 获取2张带指定标签的全年龄涩图
        /涩图 1 0 keyword:可爱 - 获取1张关键词搜索的全年龄涩图
        /涩图 1 0 uid:123456 - 获取指定作者的1张全年龄涩图
        /涩图 1 0 noai - 获取1张排除AI的全年龄涩图

        Args:
            event: 群消息事件
        """
        try:
            raw_message = event.raw_message.strip()
            user_id = event.user_id
            group_id = event.group_id

            # 解析命令
            params = self._parse_setu_command(raw_message)
            if not params:
                return

            # 检查请求频率限制
            if not self._check_request_limit(user_id):
                remaining = self._get_remaining_cooldown(user_id)
                await self.api.post_group_msg(
                    group_id,
                    text=f"⏰ 请求过于频繁，请等待 {remaining} 秒后再试"
                )
                return

            # 验证参数
            error_msg = self._validate_setu_params(params)
            if error_msg:
                help_text = self._get_help_text()
                await self.api.post_group_msg(group_id, text=f"{error_msg}\n\n{help_text}")
                return

            # 发送处理中消息
            processing_msg = "🎨 正在搜索"
            if params.get("tag"):
                processing_msg += f"标签「{', '.join(params['tag'])}」的"
            if params.get("keyword"):
                processing_msg += f"关键词「{params['keyword']}」的"
            processing_msg += "涩图，请稍候..."

            await self.api.post_group_msg(group_id, text=processing_msg)

            # 处理涩图请求
            await self.send_setu(
                event,
                num=params.get("num", 1),
                r18=params.get("r18", 0),
                tag=params.get("tag"),
                keyword=params.get("keyword"),
                uid=params.get("uid"),
                exclude_ai=params.get("exclude_ai", False)
            )

        except Exception as e:
            _log.error(f"处理涩图命令失败: {e}")
            await self.api.post_group_msg(
                event.group_id,
                text="❌ 处理命令时发生错误，请稍后再试。"
            )

