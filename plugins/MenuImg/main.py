from .database_utils import load_menu_data, extract_members, generate_temp_image, send_image, update_menu_from_file, get_plugin_by_index, get_plugin_by_name, get_plugin_help_content
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage
import re

# 导入标准化帮助文档
try:
    from help_docs.plugin_help_docs import get_plugin_help, get_all_plugin_helps
except ImportError:
    # 如果导入失败，提供默认实现
    def get_plugin_help(plugin_name: str) -> dict:
        return None
    def get_all_plugin_helps() -> dict:
        return {}

# 导入ncatbot的数据库管理器
try:
    from plugins.DatabasePlugin.main import DatabaseManager
    HAS_DATABASE_MANAGER = True
    print("✅ 使用 DatabasePlugin.DatabaseManager")
except ImportError:
    HAS_DATABASE_MANAGER = False
    print("⚠️ 未找到DatabaseManager，将使用本地状态管理")

bot = CompatibleEnrollment  # 兼容回调函数注册器

class MenuImg(BasePlugin):
    name = "MenuImg"  # 插件名称
    version = "0.0.2"  # 插件版本
    # dependencies={"Pillow":">=9.0.0"}
    
    @bot.group_event()
    async def on_group_event(self, msg: GroupMessage):
        if msg.raw_message == "菜单":
            menu_data = await load_menu_data(msg.group_id)  # 添加 await 调用异步函数
            if not menu_data:
                await self.api.post_group_msg(msg.group_id, text="菜单数据不存在或数据格式错误")
                return

            members = extract_members(menu_data)  # 提取成员信息
            image_path = generate_temp_image(members)  # 生成临时图片

            if image_path:
                await send_image(self.api, msg.group_id, image_path)  # 发送图片

        elif msg.raw_message == "更新菜单":
            result = await update_menu_from_file(msg.group_id)  # 获取详细的更新结果
            if result and result.get("success"):
                # 构建详细的更新反馈信息
                stats = result.get("stats", {})
                response = "✅ 菜单更新成功！\n\n"
                response += f"📊 更新统计：\n"
                response += f"• 原有项目：{stats.get('existing_count', 0)} 项\n"
                response += f"• 新数据项目：{stats.get('new_count', 0)} 项\n"
                response += f"• 合并后项目：{stats.get('merged_count', 0)} 项\n"

                if stats.get('added_count', 0) > 0:
                    response += f"• ➕ 新增：{stats.get('added_count', 0)} 项\n"
                    if stats.get('added_items'):
                        response += f"  └─ {', '.join(stats['added_items'][:5])}"
                        if len(stats['added_items']) > 5:
                            response += f" 等{len(stats['added_items'])}项"
                        response += "\n"

                if stats.get('removed_count', 0) > 0:
                    response += f"• ➖ 删除：{stats.get('removed_count', 0)} 项\n"
                    if stats.get('removed_items'):
                        response += f"  └─ {', '.join(stats['removed_items'][:5])}"
                        if len(stats['removed_items']) > 5:
                            response += f" 等{len(stats['removed_items'])}项"
                        response += "\n"

                if stats.get('kept_count', 0) > 0:
                    response += f"• 🔄 保持原状：{stats.get('kept_count', 0)} 项\n"

                response += "\n💡 发送\"菜单\"查看更新后的菜单"
                await self.api.post_group_msg(msg.group_id, text=response)
            else:
                error_msg = result.get("error", "未知错误") if result else "未知错误"
                await self.api.post_group_msg(
                    msg.group_id,
                    text=f"❌ 菜单更新失败\n\n错误信息：{error_msg}\n\n💡 请检查 static/menu.json 文件是否存在且格式正确"
                )

        elif msg.raw_message.startswith("/帮助"):
            # 处理帮助命令
            await self._handle_help_command(msg)

        elif msg.raw_message.startswith("/开启"):
            # 处理开启插件命令（支持序号转换）
            await self._handle_enable_command(msg)

        elif msg.raw_message.startswith("/关闭"):
            # 处理关闭插件命令（支持序号转换）
            await self._handle_disable_command(msg)

    async def _handle_help_command(self, msg: GroupMessage):
        """处理帮助命令"""
        command = msg.raw_message.strip()

        if command == "/帮助":
            # 生成总览帮助的合并转发消息
            forward_messages = await self._generate_overview_help_forward_messages()

            if forward_messages:
                from utils.group_forward_msg import _message_sender
                success = await _message_sender.send_group_forward_msg(msg.group_id, forward_messages)

                if not success:
                    # 合并转发失败，回退到菜单图片
                    menu_data = await load_menu_data(msg.group_id)
                    if not menu_data:
                        await self.api.post_group_msg(msg.group_id, text="菜单数据不存在或数据格式错误")
                        return

                    members = extract_members(menu_data)
                    image_path = generate_temp_image(members)

                    if image_path:
                        await send_image(self.api, msg.group_id, image_path)
                        await self.api.post_group_msg(
                            msg.group_id,
                            text="💡 使用提示：\n"
                                 "• /帮助 [数字] - 查看对应插件详细帮助\n"
                                 "• /帮助 [插件名] - 查看插件详细帮助\n"
                                 "• /开启 [插件名] - 开启插件\n"
                                 "• /关闭 [插件名] - 关闭插件"
                        )
            else:
                # 生成失败，回退到菜单图片
                menu_data = await load_menu_data(msg.group_id)
                if not menu_data:
                    await self.api.post_group_msg(msg.group_id, text="菜单数据不存在或数据格式错误")
                    return

                members = extract_members(menu_data)
                image_path = generate_temp_image(members)

                if image_path:
                    await send_image(self.api, msg.group_id, image_path)
                    await self.api.post_group_msg(
                        msg.group_id,
                        text="💡 使用提示：\n"
                             "• /帮助 [数字] - 查看对应插件详细帮助\n"
                             "• /帮助 [插件名] - 查看插件详细帮助\n"
                             "• /开启 [插件名] - 开启插件\n"
                             "• /关闭 [插件名] - 关闭插件"
                    )
        else:
            # 处理具体帮助查询
            query = command[3:].strip()  # 移除"/帮助"前缀

            # 尝试按数字查找
            if query.isdigit():
                index = int(query) - 1  # 转换为0基索引
                plugin_info = await get_plugin_by_index(msg.group_id, index)
                if plugin_info:
                    plugin_name = plugin_info['title']
                else:
                    plugin_name = None
            else:
                # 按名称查找
                plugin_info = await get_plugin_by_name(msg.group_id, query)
                plugin_name = query if plugin_info else None

            if plugin_info:
                # 获取插件真实的帮助内容（不是menu.json的content）
                plugin_help_content = await get_plugin_help_content(plugin_info['title'])
                status_text = "✅ 已开启" if plugin_info['status'] == "1" else "❌ 已关闭"

                # 生成插件帮助的合并转发消息
                forward_messages = await self._generate_plugin_help_forward_messages(
                    plugin_info['title'],
                    plugin_help_content,
                    status_text
                )

                if forward_messages:
                    from utils.group_forward_msg import _message_sender
                    success = await _message_sender.send_group_forward_msg(msg.group_id, forward_messages)

                    if not success:
                        # 合并转发失败，回退到文本帮助
                        response = f"📖 {plugin_info['title']} 帮助\n"
                        response += "=" * 30 + "\n\n"
                        response += f"📊 状态：{status_text}\n\n"
                        response += f"📝 简介：{plugin_info['title']}插件\n\n"

                        # 如果有插件真实帮助内容，显示它
                        if plugin_help_content:
                            response += f"📋 详细说明：\n{plugin_help_content}\n\n"

                        response += "💡 提示：\n"
                        response += f"• /开启 {plugin_info['title']} - 开启此插件\n"
                        response += f"• /关闭 {plugin_info['title']} - 关闭此插件"

                        await self.api.post_group_msg(msg.group_id, text=response)
                else:
                    # 生成失败，回退到文本帮助
                    response = f"📖 {plugin_info['title']} 帮助\n"
                    response += "=" * 30 + "\n\n"
                    response += f"📊 状态：{status_text}\n\n"
                    response += f"📝 简介：{plugin_info['title']}插件\n\n"

                    # 如果有插件真实帮助内容，显示它
                    if plugin_help_content:
                        response += f"📋 详细说明：\n{plugin_help_content}\n\n"

                    response += "💡 提示：\n"
                    response += f"• /开启 {plugin_info['title']} - 开启此插件\n"
                    response += f"• /关闭 {plugin_info['title']} - 关闭此插件"

                    await self.api.post_group_msg(msg.group_id, text=response)
            else:
                await self.api.post_group_msg(
                    msg.group_id,
                    text=f"❌ 未找到 '{query}' 对应的插件\n\n💡 提示：发送 /帮助 查看所有可用插件"
                )

    async def _handle_enable_command(self, msg: GroupMessage):
        """处理开启插件命令（支持序号转换）"""
        command = msg.raw_message.strip()
        query = command[3:].strip()  # 移除"/开启"前缀

        if not query:
            return  # 让PluginManager处理空参数的情况

        # 如果是数字，转换为插件名称
        if query.isdigit():
            index = int(query) - 1  # 转换为0基索引
            plugin_info = await get_plugin_by_index(msg.group_id, index)
            if plugin_info:
                plugin_name = plugin_info['title']
                # 构造新的消息，让PluginManager处理
                new_message = f"/开启 {plugin_name}"

                # 创建新的消息对象
                new_msg = GroupMessage(
                    group_id=msg.group_id,
                    user_id=msg.user_id,
                    raw_message=new_message,
                    message_id=msg.message_id,
                    time=msg.time
                )

                # 调用PluginManager的逻辑
                await self._call_plugin_manager(new_msg, "开启")
            else:
                await self.api.post_group_msg(
                    msg.group_id,
                    text=f"❌ 序号 {query} 对应的插件不存在\n\n💡 发送 /帮助 查看可用插件"
                )
        else:
            # 如果是名称，不处理，让PluginManager处理
            return

    async def _handle_disable_command(self, msg: GroupMessage):
        """处理关闭插件命令（支持序号转换）"""
        command = msg.raw_message.strip()
        query = command[3:].strip()  # 移除"/关闭"前缀

        if not query:
            return  # 让PluginManager处理空参数的情况

        # 如果是数字，转换为插件名称
        if query.isdigit():
            index = int(query) - 1  # 转换为0基索引
            plugin_info = await get_plugin_by_index(msg.group_id, index)
            if plugin_info:
                plugin_name = plugin_info['title']
                # 构造新的消息，让PluginManager处理
                new_message = f"/关闭 {plugin_name}"

                # 创建新的消息对象
                new_msg = GroupMessage(
                    group_id=msg.group_id,
                    user_id=msg.user_id,
                    raw_message=new_message,
                    message_id=msg.message_id,
                    time=msg.time
                )

                # 调用PluginManager的逻辑
                await self._call_plugin_manager(new_msg, "关闭")
            else:
                await self.api.post_group_msg(
                    msg.group_id,
                    text=f"❌ 序号 {query} 对应的插件不存在\n\n💡 发送 /帮助 查看可用插件"
                )
        else:
            # 如果是名称，不处理，让PluginManager处理
            return

    async def _call_plugin_manager(self, msg: GroupMessage, action: str):
        """调用PluginManager的逻辑"""
        if HAS_DATABASE_MANAGER:
            try:
                # 简化权限检查 - 使用配置文件
                from utils.config_manager import get_config
                master_list = get_config("master", [])

                if msg.user_id not in master_list:
                    await self.api.post_group_msg(
                        msg.group_id,
                        text="您没有权限执行此操作"
                    )
                    return

                # 执行数据库操作
                db_manager = DatabaseManager()
                command = msg.raw_message.strip()

                if command.startswith(f"/{action}"):
                    title = command[3:].strip()  # 移除"/开启"或"/关闭"前缀
                    status = "1" if action == "开启" else "0"

                    if await db_manager.update_feature_status(msg.group_id, title, status):
                        await self.api.post_group_msg(
                            msg.group_id,
                            text=f"功能 '{title}' 已{action}"
                        )
                    else:
                        await self.api.post_group_msg(
                            msg.group_id,
                            text=f"功能 '{title}' {action}失败，请检查功能名称是否正确"
                        )

            except Exception as e:
                await self.api.post_group_msg(
                    msg.group_id,
                    text=f"❌ {action}插件时出错：{str(e)}"
                )
        else:
            await self.api.post_group_msg(
                msg.group_id,
                text="⚠️ 插件管理功能不可用"
            )

    async def on_load(self):
        print(f"{self.name} 插件已加载")
        print(f"插件版本: {self.version}")

    async def _generate_overview_help_forward_messages(self) -> list:
        """生成总览帮助的合并转发消息"""
        try:
            from utils.config_manager import get_config

            messages = []
            bot_name = get_config("bot_name", "NCatBot")

            # 添加标题消息
            title_msg = {
                "type": "node",
                "data": {
                    "name": f"{bot_name}助手",
                    "uin": get_config("bt_uin", 123456),
                    "content": f"🤖 {bot_name} 插件帮助\n\n欢迎使用 {bot_name}！以下是常用功能说明："
                }
            }
            messages.append(title_msg)

            # 基本命令
            basic_commands = (
                "⚡ 基本命令\n\n"
                "• 菜单 - 查看所有插件状态和功能列表\n"
                "• /帮助 [插件名] - 查看指定插件的详细帮助\n"
                "• /帮助 [数字] - 通过序号查看帮助\n"
                "• /开启 [插件名] - 启用指定插件功能\n"
                "• /关闭 [插件名] - 禁用指定插件功能"
            )

            basic_msg = {
                "type": "node",
                "data": {
                    "name": f"{bot_name}助手",
                    "uin": get_config("bt_uin", 123456),
                    "content": basic_commands
                }
            }
            messages.append(basic_msg)

            # AI对话功能
            ai_content = (
                "🤖 AI智能对话\n\n"
                "• @机器人 [消息] - 触发AI对话\n"
                "• 机器人 [消息] - 以\"机器人\"开头触发对话\n"
                "• /修改设定 [角色设定] - 修改AI角色设定\n"
                "• /查看设定 - 查看当前AI角色设定\n\n"
                "💡 示例：\n"
                "机器人 今天天气怎么样？\n"
                "/修改设定 你是一个可爱的猫娘"
            )

            ai_msg = {
                "type": "node",
                "data": {
                    "name": f"{bot_name}助手",
                    "uin": get_config("bt_uin", 123456),
                    "content": ai_content
                }
            }
            messages.append(ai_msg)

            # 常用功能
            features_content = (
                "🎯 常用功能\n\n"
                "• /搜图 - 以图搜图功能\n"
                "• /签到 - 每日签到\n"
                "• /今日老婆 - 随机二次元老婆\n"
                "• /今日运势 - 查看今日运势\n"
                "• /setu - 随机图片（需开启）\n"
                "• /添加cyc [内容] - 添加戳一戳回复\n"
                "• /cyc帮助 - 查看戳一戳功能帮助"
            )

            features_msg = {
                "type": "node",
                "data": {
                    "name": f"{bot_name}助手",
                    "uin": get_config("bt_uin", 123456),
                    "content": features_content
                }
            }
            messages.append(features_msg)

            # 注意事项
            tips_content = (
                "⚠️ 注意事项\n\n"
                "• 部分功能需要管理员权限才能使用\n"
                "• 插件的启用/禁用状态可通过\"菜单\"命令查看\n"
                "• 发送 /帮助 [插件名] 可查看具体插件的详细说明\n"
                "• 如遇问题请联系管理员\n\n"
                "📞 获取更多帮助：\n"
                "发送\"菜单\"查看所有可用插件"
            )

            tips_msg = {
                "type": "node",
                "data": {
                    "name": f"{bot_name}助手",
                    "uin": get_config("bt_uin", 123456),
                    "content": tips_content
                }
            }
            messages.append(tips_msg)

            return messages

        except Exception as e:
            print(f"[ERROR] 生成总览帮助合并转发消息失败: {e}")
            return None

    async def _generate_plugin_help_forward_messages(self, plugin_title: str, help_content: str, status_text: str) -> list:
        """生成插件帮助的合并转发消息"""
        try:
            from utils.config_manager import get_config

            messages = []
            bot_name = get_config("bot_name", "NCatBot")

            # 尝试从标准化文档获取帮助内容
            standard_help = get_plugin_help(plugin_title)

            if standard_help:
                # 使用标准化帮助文档
                description = standard_help.get('description', '暂无描述')
                version = standard_help.get('version', '未知版本')
                standard_help_content = standard_help.get('help_content', '')

                # 插件基本信息
                basic_info = (
                    f"📋 {plugin_title} 插件详情\n\n"
                    f"🔖 状态：{status_text}\n"
                    f"📦 版本：{version}\n"
                    f"📝 描述：{description}"
                )

                basic_msg = {
                    "type": "node",
                    "data": {
                        "name": f"{bot_name}助手",
                        "uin": get_config("bt_uin", 123456),
                        "content": basic_info
                    }
                }
                messages.append(basic_msg)

                # 使用标准化帮助内容
                if standard_help_content:
                    # 将帮助内容按段落分割
                    content_parts = standard_help_content.split('\n\n')
                    current_content = ""

                    for part in content_parts:
                        if len(current_content + part) > 800:  # 限制单条消息长度
                            if current_content:
                                content_msg = {
                                    "type": "node",
                                    "data": {
                                        "name": f"{bot_name}助手",
                                        "uin": get_config("bt_uin", 123456),
                                        "content": current_content.strip()
                                    }
                                }
                                messages.append(content_msg)
                            current_content = part + "\n\n"
                        else:
                            current_content += part + "\n\n"

                    # 添加最后一部分
                    if current_content.strip():
                        content_msg = {
                            "type": "node",
                            "data": {
                                "name": f"{bot_name}助手",
                                "uin": get_config("bt_uin", 123456),
                                "content": current_content.strip()
                            }
                        }
                        messages.append(content_msg)

                return messages

            # 如果没有标准化文档，使用原有逻辑
            # 插件基本信息
            basic_info = (
                f"📋 {plugin_title} 插件详情\n\n"
                f"🔖 状态：{status_text}\n"
                f"📝 这是 {plugin_title} 插件的详细说明"
            )

            basic_msg = {
                "type": "node",
                "data": {
                    "name": f"{bot_name}助手",
                    "uin": get_config("bt_uin", 123456),
                    "content": basic_info
                }
            }
            messages.append(basic_msg)

            # 详细帮助内容
            if help_content and help_content.strip():
                # 将长内容分段
                content_parts = help_content.split('\n\n')
                current_content = ""

                for part in content_parts:
                    if len(current_content + part) > 800:  # 限制单条消息长度
                        if current_content:
                            content_msg = {
                                "type": "node",
                                "data": {
                                    "name": f"{bot_name}助手",
                                    "uin": get_config("bt_uin", 123456),
                                    "content": current_content.strip()
                                }
                            }
                            messages.append(content_msg)
                        current_content = part + "\n\n"
                    else:
                        current_content += part + "\n\n"

                # 添加最后一部分
                if current_content.strip():
                    content_msg = {
                        "type": "node",
                        "data": {
                            "name": f"{bot_name}助手",
                            "uin": get_config("bt_uin", 123456),
                            "content": current_content.strip()
                        }
                    }
                    messages.append(content_msg)
            else:
                # 没有详细内容时的默认消息
                default_msg = {
                    "type": "node",
                    "data": {
                        "name": f"{bot_name}助手",
                        "uin": get_config("bt_uin", 123456),
                        "content": f"📖 {plugin_title} 插件功能\n\n该插件提供相关功能和服务。\n如需更多帮助，请联系管理员。"
                    }
                }
                messages.append(default_msg)

            return messages

        except Exception as e:
            print(f"[ERROR] 生成插件帮助合并转发消息失败: {e}")
            return None

    async def generate_help_image_for_plugin(self, plugin_name: str) -> str:
        """为指定插件生成帮助图片"""
        try:
            # 直接导入图片生成器
            import importlib.util

            # 加载图片生成器模块
            spec = importlib.util.spec_from_file_location(
                "help_image_generator",
                "plugins/HelpSystem/help_image_generator.py"
            )
            help_image_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(help_image_module)

            # 获取图片生成器实例
            generator = help_image_module.help_image_generator

            if plugin_name:
                # 生成指定插件的帮助图片
                help_data = {
                    'title': f'[帮助] {plugin_name} 插件帮助',
                    'description': f'这是 {plugin_name} 插件的详细说明。\n提供相关功能和服务。',
                    'commands': [
                        {
                            'name': f'/{plugin_name.lower()}',
                            'description': f'使用 {plugin_name} 插件的基本命令'
                        },
                        {
                            'name': f'/开启 {plugin_name}',
                            'description': f'启用 {plugin_name} 插件'
                        },
                        {
                            'name': f'/关闭 {plugin_name}',
                            'description': f'禁用 {plugin_name} 插件'
                        }
                    ],
                    'examples': [
                        f'发送相关命令使用 {plugin_name} 功能',
                        f'/开启 {plugin_name}',
                        f'/关闭 {plugin_name}'
                    ],
                    'tips': [
                        '发送 菜单 查看所有插件状态',
                        '发送 /帮助 查看总览帮助',
                        '如需更多帮助，请联系管理员'
                    ]
                }

                # 生成图片
                image_path = generator.generate_help_image(help_data)
                return image_path
            else:
                # 生成总览帮助图片
                help_data = {
                    'title': '[帮助] NCatBot 插件帮助',
                    'description': '欢迎使用 NCatBot！以下是常用功能说明。\n发送 /帮助 插件名 查看详细说明。',
                    'commands': [
                        {'name': '菜单', 'description': '查看所有插件状态和功能列表'},
                        {'name': '/帮助 插件名', 'description': '查看指定插件的详细帮助'},
                        {'name': '/帮助 数字', 'description': '通过序号查看插件帮助'},
                        {'name': '/开启 插件名', 'description': '启用指定插件功能'},
                        {'name': '/关闭 插件名', 'description': '禁用指定插件功能'},
                        {'name': '机器人 你好', 'description': 'AI智能对话功能'}
                    ],
                    'examples': [
                        '菜单',
                        '/帮助 AI回复',
                        '/帮助 1',
                        '/开启 智能聊天',
                        '机器人 今天天气怎么样？'
                    ],
                    'tips': [
                        '发送 菜单 查看所有插件状态',
                        '@ 机器人或以"机器人"开头可触发AI对话',
                        '管理员可以使用 /开启 和 /关闭 命令管理插件',
                        '部分功能需要管理员权限才能使用'
                    ]
                }

                # 生成图片
                image_path = generator.generate_help_image(help_data)
                return image_path

        except Exception as e:
            print(f"[ERROR] 生成插件帮助图片失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def generate_help_image_for_plugin_with_content(self, plugin_title: str, plugin_description: str, help_content: str, status_text: str) -> str:
        """为指定插件生成包含真实内容的帮助图片"""
        try:
            # 直接导入图片生成器
            import importlib.util

            # 加载图片生成器模块
            spec = importlib.util.spec_from_file_location(
                "help_image_generator",
                "plugins/HelpSystem/help_image_generator.py"
            )
            help_image_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(help_image_module)

            # 获取图片生成器实例
            generator = help_image_module.help_image_generator

            # 解析帮助内容，提取命令和示例
            commands = []
            examples = []
            tips = []

            if help_content:
                lines = help_content.split('\n')
                current_section = None

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # 检测章节标题
                    if '基本使用：' in line or '管理命令：' in line or '联网功能：' in line:
                        current_section = 'commands'
                        continue
                    elif '特色功能：' in line:
                        current_section = 'features'
                        continue
                    elif '提示：' in line:
                        current_section = 'tips'
                        continue

                    # 提取命令（以 • 开头的行）
                    if line.startswith('•') and current_section == 'commands':
                        # 分离命令名和描述
                        if ' - ' in line:
                            cmd_part, desc_part = line[1:].strip().split(' - ', 1)
                            commands.append({
                                'name': cmd_part.strip(),
                                'description': desc_part.strip()
                            })
                        else:
                            commands.append({
                                'name': line[1:].strip(),
                                'description': f'使用 {plugin_title} 功能'
                            })

                    # 提取特色功能作为示例
                    elif line.startswith('•') and current_section == 'features':
                        examples.append(line[1:].strip())

                    # 提取提示
                    elif line.startswith('•') and current_section == 'tips':
                        tips.append(line[1:].strip())

            # 如果没有解析到命令，添加默认命令
            if not commands:
                commands = [
                    {'name': f'/开启 {plugin_title}', 'description': f'启用 {plugin_title} 插件'},
                    {'name': f'/关闭 {plugin_title}', 'description': f'禁用 {plugin_title} 插件'}
                ]

            # 如果没有示例，添加默认示例
            if not examples:
                examples = [
                    f'发送相关命令使用 {plugin_title} 功能',
                    f'/开启 {plugin_title}',
                    f'/关闭 {plugin_title}'
                ]

            # 如果没有提示，添加默认提示
            if not tips:
                tips = [
                    '发送 菜单 查看所有插件状态',
                    '发送 /帮助 查看总览帮助',
                    '如需更多帮助，请联系管理员'
                ]

            # 清理所有特殊字符的函数
            def clean_text(text):
                """移除所有可能导致乱码的特殊字符"""
                if not text:
                    return text
                import re
                # 移除所有emoji和特殊Unicode字符
                text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)  # 表情符号
                text = re.sub(r'[\U0001F300-\U0001F5FF]', '', text)  # 符号和象形文字
                text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text)  # 交通和地图符号
                text = re.sub(r'[\U0001F1E0-\U0001F1FF]', '', text)  # 旗帜
                text = re.sub(r'[\U00002600-\U000027BF]', '', text)  # 杂项符号
                text = re.sub(r'[\U0001F900-\U0001F9FF]', '', text)  # 补充符号
                # 替换常见特殊字符
                text = text.replace('✅', '[已开启]').replace('❌', '[已关闭]')
                text = text.replace('📝', '[简介]').replace('📋', '[详细说明]')
                text = text.replace('💡', '[提示]').replace('🤖', '[AI]')
                text = text.replace('•', '·').replace('⚡', '[命令]')
                return text.strip()

            # 构建完整的帮助数据（使用插件真实帮助内容，不使用menu.json的content）
            clean_status = clean_text(status_text)
            clean_description = clean_text(plugin_description)
            clean_help_content = clean_text(help_content) if help_content else None

            # 构建描述部分
            description_parts = [f'{clean_status}', f'[简介] {clean_description}']
            if clean_help_content:
                description_parts.append(f'[详细说明]\n{clean_help_content}')

            help_data = {
                'title': f'{plugin_title} 帮助',
                'description': '\n\n'.join(description_parts),
                'commands': [{'name': clean_text(cmd['name']), 'description': clean_text(cmd['description'])} for cmd in commands],
                'examples': [clean_text(example) for example in examples]
                # 删除tips部分，减少图片长度
            }

            # 生成图片
            image_path = generator.generate_help_image(help_data)
            return image_path

        except Exception as e:
            print(f"[ERROR] 生成插件详细帮助图片失败: {e}")
            import traceback
            traceback.print_exc()
            return None

