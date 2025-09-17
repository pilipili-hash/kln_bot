import aiohttp
import asyncio
import logging
import time
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
import base64
from datetime import datetime
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
from ncatbot.core.element import MessageChain, Text, Image as NCImage
import os

# 设置日志
_log = logging.getLogger(__name__)

bot = CompatibleEnrollment

class HotSearchPlugin(BasePlugin):
    name = "HotSearchPlugin"
    version = "2.0.0"

    def __init__(self, event_bus=None, time_task_scheduler=None, debug=False, **kwargs):
        super().__init__(event_bus, time_task_scheduler, debug=debug, **kwargs)

        # 统计信息
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.help_count = 0
        self.platform_stats = {}  # 各平台使用统计

        # 频率控制
        self.last_request_time = {}
        self.request_interval = 3.0  # 3秒间隔

    # 定义支持的平台配置（类级别）
    platforms = {
            "coolapk": {
                "name": "酷安",
                "api_url": "https://news.666240.xyz/api/s?id=coolapk",
                "color": "#4CAF50",  # 绿色主题
                "emoji": "📱",
                "commands": ["/酷安热搜", "酷安热搜"]
            },
            "weibo": {
                "name": "微博",
                "api_url": "https://news.666240.xyz/api/s?id=weibo",
                "color": "#E6162D",  # 红色主题
                "emoji": "🔥",
                "commands": ["/微博热搜", "微博热搜"]
            },
            "bilibili": {
                "name": "哔哩哔哩", 
                "api_url": "https://news.666240.xyz/api/s?id=bilibili",
                "color": "#00A1D6",  # 蓝色主题
                "emoji": "📺",
                "commands": ["/B站热搜", "B站热搜", "/哔哩热搜", "哔哩热搜"]
            },
            "tieba": {
                "name": "贴吧",
                "api_url": "https://news.666240.xyz/api/s?id=tieba",
                "color": "#2979FF",  # 蓝色主题
                "emoji": "🔍",
                "commands": ["/贴吧热搜", "贴吧热搜"]
            },
            "douyin": {
                "name": "抖音",
                "api_url": "https://news.666240.xyz/api/s?id=douyin",
                "color": "#080808",  # 蓝色主题
                "emoji": "🎵",
                "commands": ["/抖音热搜", "抖音热搜"]
            },
            "thepaper": {
                "name": "澎湃",
                "api_url": "https://news.666240.xyz/api/s?id=thepaper",
                "color": "#E96C56",  # 蓝色主题
                "emoji": "📰",
                "commands": ["/新闻", "新闻"]
            }            
        }

    async def on_load(self):
        """插件加载时初始化"""
        try:
            # 初始化各平台统计
            for platform_id in self.platforms.keys():
                self.platform_stats[platform_id] = {
                    'request_count': 0,
                    'success_count': 0,
                    'error_count': 0
                }
            _log.info(f"HotSearchPlugin v{self.version} 插件已加载，支持 {len(self.platforms)} 个平台")
        except Exception as e:
            _log.error(f"HotSearchPlugin插件加载失败: {e}")

    def _check_frequency_limit(self, user_id: int) -> tuple[bool, float]:
        """检查用户请求频率限制"""
        current_time = time.time()

        if user_id in self.last_request_time:
            time_diff = current_time - self.last_request_time[user_id]
            if time_diff < self.request_interval:
                remaining_time = self.request_interval - time_diff
                return False, remaining_time

        self.last_request_time[user_id] = current_time
        return True, 0.0

    async def fetch_hot_search_data(self, platform_id):
        """获取指定平台的热搜数据"""
        if platform_id not in self.platforms:
            return None
            
        platform_config = self.platforms[platform_id]
        api_url = platform_config["api_url"]
        
        # 添加请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Referer': 'https://news.666240.xyz/'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        return None
        except (aiohttp.ClientTimeout, Exception):
            return None

    def create_hot_search_image(self, data, platform_id):
        """生成热搜图片 - 现代 Tailwind 风格卡片"""
        if not data or data.get("status") != "success":
            return None

        if platform_id not in self.platforms:
            return None
            
        platform_config = self.platforms[platform_id]
        theme_color = platform_config["color"]
        items = data.get("items", [])[:10]  # 取前10条热搜
        updated_time = data.get("updatedTime", 0)
        
        # --- 设计参数 (类 Tailwind 风格) ---
        width = 800
        header_height = 120
        item_height = 75
        footer_height = 60
        padding = 32
        total_height = header_height + len(items) * item_height + footer_height

        # --- 颜色 (类 Tailwind 调色板) ---
        colors = {
            "bg": "#f8fafc",      # slate-50
            "card": "#ffffff",    # white
            "shadow": "#0000001a",
            "text_primary": "#1e293b", # slate-800
            "text_secondary": "#64748b", # slate-500
            "border": "#e2e8f0",  # slate-200
        }

        # --- 创建画布 ---
        img = Image.new('RGB', (width, total_height), color=colors["bg"])
        draw = ImageDraw.Draw(img)

        # --- 加载字体 ---
        try:
            font_regular = ImageFont.truetype("msyh.ttc", 16)
            font_bold = ImageFont.truetype("msyhbd.ttc", 16)
            font_title = ImageFont.truetype("msyhbd.ttc", 24)
            font_small = ImageFont.truetype("msyh.ttc", 12)
            font_rank = ImageFont.truetype("msyhbd.ttc", 18)
            # 尝试加载 Emoji 字体以解决乱码问题
            font_emoji = ImageFont.truetype("seguiemj.ttf", 24)
            font_emoji_tag = ImageFont.truetype("seguiemj.ttf", 16)
        except IOError:
            font_regular = font_bold = font_title = font_small = font_rank = ImageFont.load_default()
            font_emoji = font_title # Fallback
            font_emoji_tag = font_regular # Fallback

        # --- 绘制卡片和阴影 ---
        card_rect = [padding, padding, width - padding, total_height - padding]
        shadow_rect = [card_rect[0] + 5, card_rect[1] + 5, card_rect[2] + 5, card_rect[3] + 5]
        draw.rounded_rectangle(shadow_rect, radius=16, fill=colors["shadow"])
        draw.rounded_rectangle(card_rect, radius=16, fill=colors["card"])

        header_y = padding + 30
        # 平台图标和名称
        icon_text = platform_config['emoji']
        # 使用 Emoji 专用字体绘制图标，解决乱码
        draw.text((padding * 2, header_y), icon_text, font=font_emoji, fill=theme_color)
        title_text = f"{platform_config['name']} 热搜榜"
        draw.text((padding * 2 + 40, header_y), title_text, fill=colors["text_primary"], font=font_title)
        
        # 更新时间
        if updated_time:
            time_str = datetime.fromtimestamp(updated_time / 1000).strftime("%Y-%m-%d %H:%M")
        else:
            time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        subtitle_text = f"更新于 {time_str}"
        draw.text((padding * 2 + 40, header_y + 35), subtitle_text, fill=colors["text_secondary"], font=font_small)

        # 头部底部分隔线
        draw.line([(padding, header_height), (width - padding, header_height)], fill=colors["border"], width=1)

        # --- 绘制热搜列表 ---
        list_start_y = header_height
        for i, item in enumerate(items):
            y_pos = list_start_y + i * item_height
            
            # 排名 (垂直居中)
            rank_text = str(i + 1)
            rank_color = theme_color if i < 3 else colors["text_secondary"]
            rank_bbox = draw.textbbox((0, 0), rank_text, font=font_rank)
            rank_height = rank_bbox[3] - rank_bbox[1]
            draw.text((padding * 2, y_pos + (item_height - rank_height) // 2), rank_text, fill=rank_color, font=font_rank)

            # 标题 (自动换行和垂直居中)
            title = item.get("title", "未知标题")
            max_title_width = width - (padding * 4 + 40 + 60) # 计算标题最大宽度
            
            # 使用 textwrap 进行自动换行
            wrapped_lines = textwrap.wrap(title, width=40, placeholder="...") # 这里的width是字符数估算
            
            # 限制最多两行，第二行末尾加省略号
            if len(wrapped_lines) > 2:
                wrapped_lines = wrapped_lines[:2]
                wrapped_lines[1] = textwrap.shorten(wrapped_lines[1], width=40, placeholder="...")

            line_height = font_bold.getbbox("A")[3] + 4 # 行高
            total_text_height = len(wrapped_lines) * line_height
            text_start_y = y_pos + (item_height - total_text_height) // 2

            for j, line in enumerate(wrapped_lines):
                draw.text((padding * 2 + 40, text_start_y + j * line_height), line, fill=colors["text_primary"], font=font_bold)

            # 热度值 (绘制在标题下方，如果标题只有一行)
            extra_info = item.get("extra", {}).get("info", "")
            if extra_info and len(wrapped_lines) == 1:
                 draw.text((padding * 2 + 40, text_start_y + line_height), extra_info, fill=colors["text_secondary"], font=font_small)

            # 热度标签 (右侧，垂直居中)
            hot_text = item.get("extra", {}).get("tag", "")
            tag_font = font_regular
            if i < 3: 
                hot_text = "🔥"
                tag_font = font_emoji_tag # 对前三的热度标签使用Emoji字体

            if hot_text:
                tag_bbox = draw.textbbox((0, 0), hot_text, font=tag_font)
                tag_width = tag_bbox[2] - tag_bbox[0]
                tag_height = tag_bbox[3] - tag_bbox[1]
                draw.text((width - padding * 2 - tag_width, y_pos + (item_height - tag_height) // 2), hot_text, fill=rank_color, font=tag_font)

            # 分隔线
            if i < len(items) - 1:
                line_y = y_pos + item_height
                draw.line([(padding * 2, line_y), (width - padding * 2, line_y)], fill=colors["border"], width=1)

        # --- 绘制底部 ---
        footer_y = total_height - padding - 25
        footer_text = "Powered by siyangyuan & kln_bot"
        footer_bbox = draw.textbbox((0, 0), footer_text, font=font_small)
        footer_width = footer_bbox[2] - footer_bbox[0]
        draw.text(((width - footer_width) // 2, footer_y), footer_text, fill=colors["text_secondary"], font=font_small)

        # --- 保存图片 ---
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG', quality=95, optimize=True)
        img_buffer.seek(0)
        
        image_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        return f"base64://{image_base64}"

    async def show_help_message(self, group_id):
        """显示帮助信息"""
        help_text = """🔥 热搜插件帮助 v2.0.0

🎯 功能说明：
获取各大平台的实时热搜榜单，以精美图片形式展示

📱 支持平台：
"""

        for platform_id, platform_config in self.platforms.items():
            emoji = platform_config['emoji']
            name = platform_config['name']
            commands = ' | '.join(platform_config['commands'])
            help_text += f"{emoji} {name}：{commands}\n"

        help_text += """
📝 使用说明：
• 直接发送对应命令获取热搜榜单
• 所有热搜数据将以精美图片形式展示
• 支持实时更新，数据来源官方API

✨ 特色功能：
• 🎨 精美的卡片式设计
• 📊 显示热度值和排名
• ⏰ 实时更新时间显示
• 🔥 前三名特殊标识
• 📱 移动端友好的图片格式

⚠️ 注意事项：
• 请求间隔为3秒，避免频繁调用
• 数据来源于各平台官方API
• 图片生成可能需要几秒时间

🔧 其他命令：
• /热搜 - 显示此帮助信息
• /热搜统计 - 查看使用统计

💡 提示：选择你感兴趣的平台，发送对应命令即可获取最新热搜！"""

        await self.api.post_group_msg(group_id, text=help_text)
        self.help_count += 1

    async def show_statistics(self, group_id):
        """显示使用统计"""
        success_rate = (self.success_count / self.request_count * 100) if self.request_count > 0 else 0

        stats_text = f"""📊 热搜插件统计

🔥 总请求数: {self.request_count} 次
✅ 成功次数: {self.success_count} 次
❌ 失败次数: {self.error_count} 次
📊 成功率: {success_rate:.1f}%
❓ 查看帮助: {self.help_count} 次

📱 各平台使用统计:
"""

        for platform_id, platform_config in self.platforms.items():
            stats = self.platform_stats.get(platform_id, {'request_count': 0, 'success_count': 0})
            emoji = platform_config['emoji']
            name = platform_config['name']
            platform_success_rate = (stats['success_count'] / stats['request_count'] * 100) if stats['request_count'] > 0 else 0
            stats_text += f"{emoji} {name}: {stats['request_count']}次 (成功率{platform_success_rate:.1f}%)\n"

        stats_text += f"""
⏱️ 请求间隔: {self.request_interval} 秒

💡 使用提示：
• 发送"/热搜"查看帮助信息
• 支持{len(self.platforms)}个主流平台热搜"""

        await self.api.post_group_msg(group_id, text=stats_text)

    async def handle_hot_search_request(self, event: GroupMessage, platform_id):
        """处理热搜请求的通用方法"""
        group_id = event.group_id
        user_id = event.user_id
        platform_config = self.platforms.get(platform_id)

        if not platform_config:
            await self.api.post_group_msg(group_id, text="❌ 不支持的平台")
            return

        # 频率控制检查
        can_request, remaining_time = self._check_frequency_limit(user_id)
        if not can_request:
            await self.api.post_group_msg(
                group_id,
                text=f"⏰ 请求过于频繁，请等待 {remaining_time:.1f} 秒后再试"
            )
            return

        # 更新统计
        self.request_count += 1
        self.platform_stats[platform_id]['request_count'] += 1

        # 发送处理中消息
        await self.api.post_group_msg(
            group_id,
            text=f"🔍 正在获取{platform_config['name']}热搜，请稍候..."
        )

        try:
            # 获取热搜数据
            data = await self.fetch_hot_search_data(platform_id)

            if not data:
                await self.api.post_group_msg(
                    group_id,
                    text=f"❌ 获取{platform_config['name']}热搜失败，请稍后再试"
                )
                self.error_count += 1
                self.platform_stats[platform_id]['error_count'] += 1
                return

            if data.get("status") != "success":
                await self.api.post_group_msg(
                    group_id,
                    text=f"❌ {platform_config['name']}热搜数据异常，请稍后再试"
                )
                self.error_count += 1
                self.platform_stats[platform_id]['error_count'] += 1
                return

            # 生成图片
            image_data = self.create_hot_search_image(data, platform_id)

            if not image_data:
                await self.api.post_group_msg(group_id, text="❌ 生成热搜图片失败")
                self.error_count += 1
                self.platform_stats[platform_id]['error_count'] += 1
                return

            # 构建消息链，包含图片
            message_chain = MessageChain([
                Text(f"{platform_config['emoji']} {platform_config['name']}热搜榜单\n"),
                NCImage(image_data)
            ])

            await self.api.post_group_msg(group_id, rtf=message_chain)

            # 更新成功统计
            self.success_count += 1
            self.platform_stats[platform_id]['success_count'] += 1
            _log.info(f"成功获取{platform_config['name']}热搜: 用户{user_id}, 群{group_id}")

        except Exception as e:
            _log.error(f"处理{platform_config['name']}热搜时发生错误: {e}")
            await self.api.post_group_msg(
                group_id,
                text=f"❌ 处理请求时发生错误: {str(e)}"
            )
            self.error_count += 1
            self.platform_stats[platform_id]['error_count'] += 1

    @bot.group_event()
    async def handle_group_message(self, event: GroupMessage):
        """统一处理群消息事件"""
        raw_message = event.raw_message.strip()
        group_id = event.group_id

        # 检查是否是帮助命令
        if raw_message in ["/热搜", "/热搜帮助", "热搜", "热搜帮助"]:
            await self.show_help_message(group_id)
            return
        elif raw_message in ["/热搜统计", "热搜统计"]:
            await self.show_statistics(group_id)
            return

        # 检查是否匹配任何平台的命令
        for platform_id, platform_config in self.platforms.items():
            if raw_message in platform_config["commands"]:
                await self.handle_hot_search_request(event, platform_id)
                return

    async def on_unload(self):
        """插件卸载时清理资源"""
        try:
            _log.info("HotSearchPlugin插件正在卸载...")
            # 清理统计数据
            self.platform_stats.clear()
            _log.info("HotSearchPlugin插件卸载完成")
        except Exception as e:
            _log.error(f"插件卸载时出错: {e}")
        
