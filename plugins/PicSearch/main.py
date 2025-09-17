"""
图片搜索插件 - 使用OneBotV11消息处理
"""
import re
from typing import List, Optional

from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.utils.logger import get_log

from PluginManager.plugin_manager import feature_required
from utils.onebot_v11_handler import (
    extract_images, 
    send_forward_msg, 
    create_forward_node,
    create_text_segment,
    create_image_segment
)
from .image_utils import search_image, format_results_onebot, format_results_forward

bot = CompatibleEnrollment
_log = get_log()

class PicSearch(BasePlugin):
    """图片搜索插件"""
    
    name = "PicSearch"
    version = "2.0.0"

    async def on_load(self):
        """插件加载"""
        _log.info(f"{self.name} 插件已加载，版本: {self.version}")
        # 初始化搜索状态字典
        self.pending_search = {}
        # 使用更严格的消息去重机制 - 基于事件对象的ID
        self.processed_events = set()
        # 添加锁来避免并发处理
        import asyncio
        self.processing_lock = asyncio.Lock()

    async def send_search_results(self, event: GroupMessage, image_url: str):
        """
        发送搜图结果
        
        Args:
            event: 群消息事件
            image_url: 图片URL
        """
        try:
            await self.api.post_group_msg(event.group_id, text="🔍 正在搜图中，请稍候...")
            
            # 执行图片搜索
            results = await search_image(image_url)
            
            if not results:
                await self.api.post_group_msg(event.group_id, text="❌ 搜图失败，请稍后再试。")
                return
            
            # 使用合并转发格式，按引擎分组
            forward_messages = format_results_forward(results, event.self_id, max_results=10)

            if forward_messages:
                # 尝试使用合并转发发送结果
                _log.info(f"准备发送合并转发消息，共 {len(forward_messages)} 个引擎")

                try:
                    # 发送合并转发消息
                    await send_forward_msg(event.group_id, forward_messages)
                    _log.info("合并转发消息已发送，任务完成")
                    return  # 直接返回，不等待响应确认

                except Exception as e:
                    _log.error(f"合并转发发送异常: {e}")
                    # 发生异常才降级为文本消息
                    formatted_text = format_results_onebot(results, max_results=5)
                    if formatted_text and formatted_text != "未找到相关图片":
                        await self.api.post_group_msg(event.group_id, text=f"🔍 搜图结果：\n{formatted_text}")
                    else:
                        await self.api.post_group_msg(event.group_id, text="⚠️ 搜索完成但没有找到相关结果")
            else:
                await self.api.post_group_msg(event.group_id, text="⚠️ 搜索完成但没有找到相关结果")
                
        except Exception as e:
            _log.error(f"发送搜图结果失败: {e}")
            await self.api.post_group_msg(event.group_id, text=f"❌ 处理搜图请求时出错: {str(e)}")



    @bot.group_event()
    # @feature_required(feature_name="搜图")
    async def handle_group_message(self, event: GroupMessage):
        """
        处理群消息事件
        
        Args:
            event: 群消息事件
        """
        async with self.processing_lock:
            try:
                # 生成更强的事件唯一标识符进行去重
                event_id = f"{event.group_id}_{event.message_id}_{event.user_id}_{event.time}_{id(event)}"
                if event_id in self.processed_events:
                    _log.debug(f"重复事件，跳过处理: {event_id}")
                    return  # 已经处理过的事件，跳过
                
                # 将事件ID添加到已处理集合
                self.processed_events.add(event_id)
                
                # 清理旧的事件ID（保留最近50条）
                if len(self.processed_events) > 50:
                    # 移除一半最旧的记录
                    old_events = list(self.processed_events)[:25]
                    for old_event in old_events:
                        self.processed_events.discard(old_event)
                
                group_id = event.group_id
                user_id = event.user_id
                raw_message = event.raw_message.strip()
                
                _log.debug(f"处理群消息: {group_id} - {raw_message}")
                
                # 处理搜图命令
                if raw_message.startswith("/搜图"):
                    # 从消息链中提取图片
                    image_urls = extract_images(event)
                    
                    if image_urls:
                        # 使用第一张图片进行搜索
                        await self.send_search_results(event, image_urls[0])
                    else:
                        # 没有图片，等待用户发送图片
                        self.pending_search[group_id] = user_id
                        await self.api.post_group_msg(
                            group_id, 
                            text="📷 请发送图片以完成搜索，或者在 /搜图 命令后直接附带图片。"
                        )
                    return

                # 处理取消搜图（优先处理取消命令）
                if raw_message == "/取消" and group_id in self.pending_search:
                    if self.pending_search[group_id] == user_id:
                        del self.pending_search[group_id]
                        await self.api.post_group_msg(group_id, text="✅ 已取消搜图操作。")
                    return

                # 处理等待中的搜图请求
                if group_id in self.pending_search and self.pending_search[group_id] == user_id:
                    image_urls = extract_images(event)

                    if image_urls:
                        # 找到图片，执行搜索
                        del self.pending_search[group_id]
                        await self.send_search_results(event, image_urls[0])
                    else:
                        # 仍然没有图片
                        await self.api.post_group_msg(
                            group_id,
                            text="❌ 请发送包含图片的消息，或发送 /取消 取消搜图。"
                        )
                    return
                    
            except Exception as e:
                _log.error(f"处理群消息失败: {e}")
                await self.api.post_group_msg(
                    event.group_id, 
                    text="❌ 处理消息时发生错误，请稍后再试。"
                )
