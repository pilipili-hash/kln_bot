import logging
import time
from typing import Dict, Optional, Tuple
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import GroupMessage, PrivateMessage
from ncatbot.utils.config import config
from ncatbot.utils.logger import get_log
from .game import Game, LocalData
from .model import GameData, StateDecide
from .robot import ai_action
from .utils import Format
from .weapon import Weapon

_log = get_log()
bot = CompatibleEnrollment

class DemonRoulettePlugin(BasePlugin):
    name = "DemonRoulettePlugin"  # 插件名称
    version = "2.0.0"        # 插件版本

    async def on_load(self):
        # 初始化插件属性
        self.game_count = 0
        self.pvp_game_count = 0
        self.pve_game_count = 0
        self.error_count = 0
        self.last_request_time = 0
        self.rate_limit_delay = 2.0  # 请求间隔限制

        _log.info(f"{self.name} v{self.version} 插件已加载")
        _log.info("恶魔轮盘游戏功能已启用")

    async def on_unload(self):
        _log.info(f"{self.name} 插件已卸载")

    async def get_statistics(self) -> str:
        """获取使用统计"""
        success_rate = 0
        if self.game_count > 0:
            success_rate = ((self.game_count - self.error_count) / self.game_count) * 100

        return f"""📊 恶魔轮盘统计

🎮 总游戏数: {self.game_count}
👥 PVP对战: {self.pvp_game_count}
🤖 人机对战: {self.pve_game_count}
❌ 错误次数: {self.error_count}
✅ 成功率: {success_rate:.1f}%
⏱️ 请求间隔: {self.rate_limit_delay}秒"""

    @bot.group_event()
    async def handle_group_message(self, msg: GroupMessage):
        """处理群消息"""
        await self.process_br_command(msg)

    COMMANDS = {
        "br帮助": "show_help",
        "恶魔轮盘帮助": "show_help",
        "br开始": "br_start_game",
        "br加入": "br_start_game",
        "br准备": "br_start_game",
        "开枪": "game_shut_action",
        "br人机对战": "start_robot_game",
        "br人机": "start_robot_game",
        "brai": "start_robot_game",
        "结束游戏": "end_game",
        "br结束": "end_game",
        "br当前状态": "br_current_state",
        "br状态": "br_current_state",
        "br设置血量": "br_set_life",
        "br统计": "show_statistics",
        "恶魔轮盘统计": "show_statistics",
    }

    async def process_br_command(self, msg: GroupMessage):
        """处理恶魔轮盘命令"""
        try:
            raw_message = msg.raw_message.strip()
            command = raw_message.split()[0] if raw_message else ""

            # 检查是否是恶魔轮盘相关命令
            if not any(cmd in raw_message for cmd in ["br", "恶魔轮盘", "开枪", "使用", "结束游戏"]):
                return

            method_name = self.COMMANDS.get(command, "use_item" if command.startswith("使用") else None)
            if method_name:
                _log.info(f"用户 {msg.user_id} 在群 {msg.group_id} 执行命令: {command}")
                await getattr(self, method_name)(msg)

        except Exception as e:
            self.error_count += 1
            _log.error(f"处理恶魔轮盘命令时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 命令处理失败，请稍后再试")

    async def show_help(self, msg: GroupMessage):
        """显示帮助信息"""
        await self.api.post_group_msg(msg.group_id, text=self.br_help_message, reply=msg.message_id)

    async def show_statistics(self, msg: GroupMessage):
        """显示统计信息"""
        try:
            stats = await self.get_statistics()
            await self.api.post_group_msg(msg.group_id, text=stats)
        except Exception as e:
            _log.error(f"获取统计信息时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 获取统计信息失败")

    async def validate_game_state(self, session_uid, player_id, check_turn=False):
        game_data = await LocalData.read_data(session_uid)
        if not game_data:
            return None, "当前没有正在进行的游戏。"

        if check_turn:
            is_player_turn = (game_data["round_self"] and player_id == game_data["player_id"]) or \
                             (not game_data["round_self"] and player_id == game_data["player_id2"])
            if not is_player_turn:
                current_player = game_data["player_name"] if game_data["round_self"] else game_data["player_name2"]
                return None, f"现在是 {current_player} 的回合，请等待对手行动。"

        return game_data, None

    br_help_message = """
游戏指令
- br开始/br加入/br准备 —— 开始游戏
- br继续 ——继续未结束的游戏（如果有）
- br设置血量 —— 设置血量
- 开枪 —— 开枪(开始游戏后,第一次“开枪”决定先手而不是开枪)
- 使用道具 xxx —— 使用道具
- 结束游戏 —— 结束游戏
- br人机对战 —— 开始人机对战
"""

    async def br_start_game(self, msg: GroupMessage):
        """开始或加入游戏"""
        session_uid = msg.group_id
        player_id = msg.user_id

        try:
            game_data = await LocalData.read_data(session_uid)
            player_name = msg.sender.card if msg.sender.card else msg.sender.nickname

            # 检查是否有正在进行的游戏
            if game_data and game_data.get("player_id2") and game_data.get("is_start"):
                await self.api.post_group_msg(msg.group_id, text="🎮 检测到正在进行的游戏，游戏继续！")
                game_state = await Game.state(game_data, session_uid)
                await self.api.post_group_msg(msg.group_id, text=game_state["msg"])
                return

            # 创建新游戏
            if not game_data:
                self.game_count += 1
                self.pvp_game_count += 1

                game_data = await LocalData.new_data(player_id, session_uid, False)
                game_data["player_name"] = player_name
                await LocalData.save_data(session_uid, game_data)

                _log.info(f"用户 {player_id} 在群 {session_uid} 发起恶魔轮盘游戏")
                await self.api.post_group_msg(
                    msg.group_id,
                    text=f"🎯 玩家 {player_name} 发起了恶魔轮盘游戏！\n⏳ 请等待另外一个用户加入游戏\n💡 发送 'br开始' 加入游戏"
                )
                return

            # 检查是否是同一玩家
            if game_data.get("player_id") == player_id:
                await self.api.post_group_msg(msg.group_id, text="❌ 你已经发起了游戏，请等待其他玩家加入！")
                return

            # 检查游戏是否已满
            if game_data.get("player_id2"):
                await self.api.post_group_msg(msg.group_id, text="❌ 本群游戏玩家已满，请等待当前游戏结束")
                return

            # 玩家2加入游戏
            game_data["player_id2"] = player_id
            game_data["player_name2"] = player_name
            game_data["is_start"] = True
            await LocalData.save_data(session_uid, game_data)

            _log.info(f"用户 {player_id} 加入群 {session_uid} 的恶魔轮盘游戏")
            await self.api.post_group_msg(
                msg.group_id,
                text=f"🎮 玩家 {player_name} 加入游戏，游戏开始！\n💡 发送 '开枪 1' 或 '开枪 2' 进行射击"
            )

        except Exception as e:
            self.error_count += 1
            _log.error(f"开始游戏时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 游戏启动失败，请稍后再试")

    async def game_shut_action(self, msg: GroupMessage):
        """处理开枪动作"""
        session_uid = msg.group_id
        player_id = msg.user_id

        try:
            game_data, error_msg = await self.validate_game_state(session_uid, player_id, check_turn=True)
            if error_msg:
                await self.api.post_group_msg(msg.group_id, text=f"❌ {error_msg}")
                return

            # 首次开枪逻辑 - 分发道具
            if not game_data.get("is_start"):
                game_data, _, new_weapon1, new_weapon2 = await Weapon.new_item(game_data)
                game_data["is_start"] = True
                await LocalData.save_data(session_uid, game_data)

                out_msg = f"""🎁 道具分发：
{game_data["player_name"]}: {await Format.creat_item(new_weapon1)}
{game_data["player_name2"]}: {await Format.creat_item(new_weapon2)}

💡 现在可以开始射击了！"""
                await self.api.post_group_msg(msg.group_id, text=out_msg)

            # 解析目标
            parts = msg.raw_message.split()
            if len(parts) < 2:
                await self.api.post_group_msg(msg.group_id, text="❌ 请指定攻击目标\n💡 格式：开枪 1（攻击对方）或 开枪 2（攻击自己）")
                return

            target = parts[1].strip()
            if target not in ["1", "2"]:
                await self.api.post_group_msg(msg.group_id, text="❌ 无效目标\n💡 1=攻击对方，2=攻击自己")
                return

            # 执行开枪
            current_player = game_data["player_name"] if game_data["round_self"] else game_data["player_name2"]
            target_desc = "对方" if target == "1" else "自己"

            _log.info(f"玩家 {current_player} 在群 {session_uid} 开枪攻击{target_desc}")

            game_data, out_msg = await Game.start(game_data, target == "2")
            await self.api.post_group_msg(msg.group_id, text=f"🔫 {current_player} 向{target_desc}开枪！\n{out_msg}")
            await LocalData.save_data(session_uid, game_data)

            # 更新游戏状态
            state_data = await Game.state(game_data, session_uid)
            await self.api.post_group_msg(msg.group_id, text=state_data["msg"])

            # 检查游戏是否结束
            if state_data["is_finish"]:
                await LocalData.delete_data(session_uid)
                await self.api.post_group_msg(msg.group_id, text="🎉 游戏已结束！")
                return

            # 如果是人机对战，触发 AI 操作
            if game_data.get("is_robot_game"):
                await self.ai_do(game_data, state_data, session_uid)

        except Exception as e:
            self.error_count += 1
            _log.error(f"处理开枪动作时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 开枪失败，请稍后再试")

    async def start_robot_game(self, msg: GroupMessage):
        """开始人机对战"""
        session_uid = msg.group_id
        player_id = msg.user_id

        try:
            # 检查是否已有游戏
            existing_game = await LocalData.read_data(session_uid)
            if existing_game:
                await self.api.post_group_msg(msg.group_id, text="❌ 当前群已有游戏进行中，请先结束当前游戏")
                return

            self.game_count += 1
            self.pve_game_count += 1

            player_name = msg.sender.card if msg.sender.card else msg.sender.nickname

            # 创建人机对战游戏
            game_data = await LocalData.new_data(player_id, session_uid, True)
            game_data["player_name"] = player_name
            game_data["player_id2"] = "gemini_ai"
            game_data["player_name2"] = "Gemini AI"
            game_data["is_start"] = True

            # 分发道具
            game_data, _, new_weapon1, new_weapon2 = await Weapon.new_item(game_data)
            await LocalData.save_data(session_uid, game_data)

            _log.info(f"用户 {player_id} 在群 {session_uid} 开始人机对战")

            out_msg = f"""🤖 人机对战开始！

🎮 玩家：{player_name}
🤖 对手：Gemini AI
🎯 你作为先手开始游戏

🎁 道具分发：
{game_data["player_name"]}: {await Format.creat_item(new_weapon1)}
{game_data["player_name2"]}: {await Format.creat_item(new_weapon2)}

💡 发送 '开枪 1' 或 '开枪 2' 开始游戏！"""
            await self.api.post_group_msg(msg.group_id, text=out_msg)

        except Exception as e:
            self.error_count += 1
            _log.error(f"开始人机对战时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 人机对战启动失败，请稍后再试")

    async def end_game(self, msg: GroupMessage):
        """结束当前游戏"""
        session_uid = msg.group_id
        player_id = msg.user_id

        try:
            game_data = await LocalData.read_data(session_uid)

            if not game_data:
                await self.api.post_group_msg(msg.group_id, text="❌ 当前没有正在进行的游戏")
                return

            # 检查权限
            if player_id not in [game_data["player_id"], game_data.get("player_id2")]:
                await self.api.post_group_msg(msg.group_id, text="❌ 您不是游戏玩家，无权限结束游戏")
                return

            player_name = msg.sender.card if msg.sender.card else msg.sender.nickname
            _log.info(f"用户 {player_id} 在群 {session_uid} 结束恶魔轮盘游戏")

            await LocalData.delete_data(session_uid)
            await self.api.post_group_msg(msg.group_id, text=f"🎮 游戏已被 {player_name} 结束，数据已清除")

        except Exception as e:
            self.error_count += 1
            _log.error(f"结束游戏时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 结束游戏失败，请稍后再试")

    async def br_current_state(self, msg: GroupMessage):
        """查看当前游戏状态"""
        session_uid = msg.group_id

        try:
            game_data = await LocalData.read_data(session_uid)

            if not game_data:
                await self.api.post_group_msg(msg.group_id, text="❌ 当前没有正在进行的游戏")
                return

            state_data = await Game.state(game_data, session_uid)
            await self.api.post_group_msg(msg.group_id, text=f"🎮 当前游戏状态：\n{state_data['msg']}")

        except Exception as e:
            self.error_count += 1
            _log.error(f"查看游戏状态时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 获取游戏状态失败")

    async def br_set_life(self, msg: GroupMessage):
        """设置游戏血量"""
        session_uid = msg.group_id
        player_id = msg.user_id

        try:
            game_data = await LocalData.read_data(session_uid)

            if not game_data:
                await self.api.post_group_msg(msg.group_id, text="❌ 当前没有正在进行的游戏")
                return

            if game_data.get("is_start"):
                await self.api.post_group_msg(msg.group_id, text="❌ 游戏已开始，无法修改血量")
                return

            # 检查权限
            if player_id != game_data["player_id"]:
                await self.api.post_group_msg(msg.group_id, text="❌ 只有游戏发起者可以设置血量")
                return

            # 解析血量值
            parts = msg.raw_message.split()
            if len(parts) < 2:
                await self.api.post_group_msg(msg.group_id, text="❌ 请输入血量值\n💡 格式：br设置血量 [数值]\n📝 示例：br设置血量 5")
                return

            try:
                life = int(parts[1].strip())
                if life < 1 or life > 8:
                    raise ValueError
            except ValueError:
                await self.api.post_group_msg(msg.group_id, text="❌ 请输入有效的血量值（1-8）")
                return

            game_data["lives"] = life
            game_data["enemy_lives"] = life
            await LocalData.save_data(session_uid, game_data)

            _log.info(f"用户 {player_id} 在群 {session_uid} 设置血量为 {life}")
            await self.api.post_group_msg(msg.group_id, text=f"✅ 血量已设置为 {life} 点")

        except Exception as e:
            self.error_count += 1
            _log.error(f"设置血量时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 设置血量失败，请稍后再试")

    async def ai_do(self, game_data: GameData, state_data: StateDecide, session_uid: str):
        action = ai_action(game_data)
        if not action:
            _log.error("无法解析 AI 操作")
            return

        if action.action_type == "开枪":
            target = int(action.argument)
            if_reload, out_msg = await Game.check_weapon(game_data, session_uid)
            if if_reload:
                await self.api.post_group_msg(session_uid, text=out_msg)
                
                await self.ai_do(game_data, state_data,  session_uid)
                return

            game_data, out_msg = await Game.start(game_data, target == "2")
            await self.api.post_group_msg(session_uid, text=out_msg)
            game_state = await Game.state(game_data, session_uid)
            await self.api.post_group_msg(session_uid, text=game_state["msg"])
            await LocalData.save_data(session_uid, game_data)

            if game_data["round_self"]:
                return

            await self.ai_do(game_data, state_data, session_uid)

        elif action.action_type == "使用":
            item = action.argument
            t_items = "items" if game_data["round_self"] else "enemy_items"  # 修复拼写错误

            if "knife" in item:
                game_data = await Weapon.use_knife(game_data)
                game_data[t_items]["knife"] -= 1
                await LocalData.save_data(session_uid, game_data)
                await self.api.post_group_msg(session_uid, text="刀已使用,你下一次攻击伤害为2(无论是否有子弹)")

            elif "handcuffs" in item:
                game_data = await Weapon.use_handcuffs(game_data)
                game_data[t_items]["handcuffs"] -= 1
                await LocalData.save_data(session_uid, game_data)
                await self.api.post_group_msg(session_uid, text="手铐已使用, 跳过对方一回合")
                if not state_data["is_finish"]:
                    await self.ai_do(game_data, state_data,session_uid)

            elif "cigarettes" in item:
                game_data = await Weapon.use_cigarettes(game_data)
                game_data[t_items]["cigarettes"] -= 1
                await LocalData.save_data(session_uid, game_data)
                await self.api.post_group_msg(session_uid, text="香烟已使用, 血量加1")

            elif "glass" in item:
                game_data, msg = await Weapon.use_glass(game_data)
                game_data[t_items]["glass"] -= 1
                await LocalData.save_data(session_uid, game_data)
                await self.api.post_group_msg(session_uid, text=f"放大镜已使用,{'是实弹' if msg else '是空弹'}")

            elif "drink" in item:
                game_data = await Weapon.use_drink(game_data)
                game_data[t_items]["drink"] -= 1
                await LocalData.save_data(session_uid, game_data)
                game_state = await Game.state(game_data, session_uid)
                await self.api.post_group_msg(session_uid, text=f"饮料已使用,退弹一发\n{game_state['msg']}")

            await self.ai_do(game_data, state_data,  session_uid)

    async def use_item(self, msg: GroupMessage):
        """使用道具"""
        session_uid = msg.group_id
        player_id = msg.user_id

        try:
            game_data, error_msg = await self.validate_game_state(session_uid, player_id, check_turn=True)
            if error_msg:
                await self.api.post_group_msg(msg.group_id, text=f"❌ {error_msg}")
                return

            # 提取道具名称
            parts = msg.raw_message.split()
            if len(parts) < 2:
                await self.api.post_group_msg(msg.group_id, text="❌ 请输入要使用的道具名称\n💡 格式：使用 [道具名]\n📝 示例：使用 刀")
                return

            item_name = parts[1].strip()
            t_items = "items" if game_data["round_self"] else "enemy_items"
            current_player = game_data["player_name"] if game_data["round_self"] else game_data["player_name2"]

            if "刀" in item_name:
                if game_data[t_items]["knife"] <= 0:
                    await self.api.post_group_msg(msg.group_id, text="❌ 你没有刀")
                    return
                game_data = await Weapon.use_knife(game_data)
                game_data[t_items]["knife"] -= 1
                await LocalData.save_data(session_uid, game_data)
                _log.info(f"玩家 {current_player} 在群 {session_uid} 使用了刀")
                await self.api.post_group_msg(msg.group_id, text="🔪 刀已使用！下一次攻击伤害翻倍")

            elif "手铐" in item_name:
                if game_data[t_items]["handcuffs"] <= 0:
                    await self.api.post_group_msg(msg.group_id, text="❌ 你没有手铐")
                    return
                game_data = await Weapon.use_handcuffs(game_data)
                game_data[t_items]["handcuffs"] -= 1
                await LocalData.save_data(session_uid, game_data)
                _log.info(f"玩家 {current_player} 在群 {session_uid} 使用了手铐")
                await self.api.post_group_msg(msg.group_id, text="🔗 手铐已使用！跳过对方一回合")

            elif "香烟" in item_name:
                if game_data[t_items]["cigarettes"] <= 0:
                    await self.api.post_group_msg(msg.group_id, text="❌ 你没有香烟")
                    return
                game_data = await Weapon.use_cigarettes(game_data)
                game_data[t_items]["cigarettes"] -= 1
                await LocalData.save_data(session_uid, game_data)
                _log.info(f"玩家 {current_player} 在群 {session_uid} 使用了香烟")
                await self.api.post_group_msg(msg.group_id, text="🚬 香烟已使用！血量恢复1点")

            elif "放大镜" in item_name:
                if game_data[t_items]["glass"] <= 0:
                    await self.api.post_group_msg(msg.group_id, text="❌ 你没有放大镜")
                    return
                game_data, is_real_bullet = await Weapon.use_glass(game_data)
                game_data[t_items]["glass"] -= 1
                await LocalData.save_data(session_uid, game_data)
                _log.info(f"玩家 {current_player} 在群 {session_uid} 使用了放大镜")
                bullet_type = "实弹" if is_real_bullet else "空弹"
                await self.api.post_group_msg(msg.group_id, text=f"🔍 放大镜已使用！当前子弹是：{bullet_type}")

            elif "饮料" in item_name:
                if game_data[t_items]["drink"] <= 0:
                    await self.api.post_group_msg(msg.group_id, text="❌ 你没有饮料")
                    return
                game_data = await Weapon.use_drink(game_data)
                game_data[t_items]["drink"] -= 1
                await LocalData.save_data(session_uid, game_data)
                _log.info(f"玩家 {current_player} 在群 {session_uid} 使用了饮料")
                game_state = await Game.state(game_data, session_uid)
                await self.api.post_group_msg(msg.group_id, text=f"🥤 饮料已使用！退出当前子弹\n{game_state['msg']}")

            else:
                await self.api.post_group_msg(msg.group_id, text="❌ 无效的道具名称\n💡 可用道具：刀、手铐、香烟、放大镜、饮料")

        except Exception as e:
            self.error_count += 1
            _log.error(f"使用道具时出错: {e}")
            await self.api.post_group_msg(msg.group_id, text="❌ 使用道具失败，请稍后再试")

