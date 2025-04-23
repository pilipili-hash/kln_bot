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
    version = "0.0.1"        # 插件版本

    async def on_load(self):
        _log.info(f"{self.name} 插件已加载")
        _log.info(f"插件版本: {self.version}")

        # 注册事件处理函数
    @bot.group_event()
    async def handle_group_message(self, msg: GroupMessage):
           # 恶魔轮盘逻辑
            await self.process_br_command(msg)

    async def on_unload(self):
        _log.info(f"{self.name} 插件已卸载")

    COMMANDS = {
        "br帮助": "show_help",
        "br开始": "br_start_game",
        "开枪": "game_shut_action",
        "br人机对战": "start_robot_game",
        "br人机": "start_robot_game",
        "brai": "start_robot_game",
        "结束游戏": "end_game",
        "br当前状态": "br_current_state",
        "br设置血量": "br_set_life",
    }

    async def process_br_command(self, msg: GroupMessage):
        command = msg.raw_message.split()[0]
        method_name = self.COMMANDS.get(command, "use_item" if command.startswith("使用") else None)
        if method_name:
            await getattr(self, method_name)(msg)

    async def show_help(self, msg: GroupMessage):
        await self.api.post_group_msg(msg.group_id, text=self.br_help_message, reply=msg.message_id)

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
        session_uid = msg.group_id
        player_id = msg.user_id

        game_data = await LocalData.read_data(session_uid)
        if game_data and game_data.get("player_id2"):
            await self.api.post_group_msg(msg.group_id, text="检测到在进行的游戏,游戏继续!")
            game_state = await Game.state(game_data, session_uid)
            await self.api.post_group_msg(msg.group_id, text=game_state["msg"])
            return

        if not game_data:
            game_data = await LocalData.new_data(player_id, session_uid, False)
            game_data["player_name"] = msg.sender.card if msg.sender.card else msg.sender.nickname  # 更新玩家1名称
            await LocalData.save_data(session_uid, game_data)
            await self.api.post_group_msg(
                msg.group_id,
                text=f"玩家 {msg.sender.card if msg.sender.card else msg.sender.nickname} 发起了恶魔轮盘游戏!\n请等待另外一个用户加入游戏"
            )
            return

        if game_data.get("player_id") == player_id:
            await self.api.post_group_msg(msg.group_id, text="你已经发起了游戏，请等待其他玩家加入!")
            return

        if game_data.get("player_id2"):
            await self.api.post_group_msg(msg.group_id, text="本群游戏玩家已满了呢.")
            return

        game_data["player_id2"] = player_id  # 设置玩家2 ID
        game_data["player_name2"] = msg.sender.card if msg.sender.card else msg.sender.nickname  # 设置玩家2名称
        game_data["is_start"] = True  # 游戏开始
        await LocalData.save_data(session_uid, game_data)
        await self.api.post_group_msg(
            msg.group_id,
            text=f"玩家 {msg.sender.card if msg.sender.card else msg.sender.nickname} 加入游戏,游戏开始."
        )

    async def game_shut_action(self, msg: GroupMessage):
        session_uid = msg.group_id
        player_id = msg.user_id
        game_data, error_msg = await self.validate_game_state(session_uid, player_id, check_turn=True)
        if error_msg:
            await self.api.post_group_msg(msg.group_id, text=error_msg)
            return

        # 首次开枪逻辑
        if not game_data.get("is_start"):
            game_data, _, new_weapon1, new_weapon2 = await Weapon.new_item(game_data)
            game_data["is_start"] = True
            await LocalData.save_data(session_uid, game_data)

            out_msg = f"""
道具新增:
{game_data["player_name"]}: {await Format.creat_item(new_weapon1)}
{game_data["player_name2"]}: {await Format.creat_item(new_weapon2)}
"""
            await self.api.post_group_msg(msg.group_id, text=out_msg)

        # 开枪逻辑
        target = msg.raw_message.split(" ", 1)[1].strip() if " " in msg.raw_message else ""
        if target not in ["1", "2"]:
            await self.api.post_group_msg(msg.group_id, text="请输入攻击目标,1为对方,2为自己")
            return

        game_data, out_msg = await Game.start(game_data, target == "2")
        await self.api.post_group_msg(msg.group_id, text=out_msg)
        await LocalData.save_data(session_uid, game_data)

        # 更新游戏状态
        state_data = await Game.state(game_data, session_uid)
        await self.api.post_group_msg(msg.group_id, text=state_data["msg"])

        # 检查游戏是否结束
        if state_data["is_finish"]:
            await LocalData.delete_data(session_uid)
            await self.api.post_group_msg(msg.group_id, text="游戏已结束！")
            return

        # 如果是人机对战，触发 AI 操作
        if game_data.get("is_robot_game"):
            await self.ai_do(game_data, state_data, session_uid)

    async def start_robot_game(self, msg: GroupMessage):
        session_uid = msg.group_id
        player_id = msg.user_id

        game_data = await LocalData.new_data(player_id, session_uid, True)
        game_data["player_id2"] = "gemini_ai"
        game_data["player_name2"] = "Gemini AI"
        game_data["is_start"] = True

        game_data, _, new_weapon1, new_weapon2 = await Weapon.new_item(game_data)
        await LocalData.save_data(session_uid, game_data)

        out_msg = f"""
玩家 {msg.sender.card if msg.sender.card else msg.sender.nickname} 发起了与 Gemini AI 的恶魔轮盘游戏!
你作为先手开始游戏。

道具新增:
{game_data["player_name"]}: {await Format.creat_item(new_weapon1)}
{game_data["player_name2"]}: {await Format.creat_item(new_weapon2)}
"""
        await self.api.post_group_msg(msg.group_id, text=out_msg)

    async def end_game(self, msg: GroupMessage):
        session_uid = msg.group_id
        player_id = msg.user_id
        game_data = await LocalData.read_data(session_uid)

        if not game_data:
            await self.api.post_group_msg(msg.group_id, text="当前没有正在进行的游戏。")
            return

        # 检查权限
        if player_id not in [game_data["player_id"], game_data["player_id2"]]:
            await self.api.post_group_msg(msg.group_id, text="您不是游戏玩家，无权限结束游戏。")
            return

        await LocalData.delete_data(session_uid)
        await self.api.post_group_msg(msg.group_id, text="游戏已结束，数据已清除。")

    async def br_current_state(self, msg: GroupMessage):
        session_uid = msg.group_id
        game_data = await LocalData.read_data(session_uid)

        if not game_data:
            await self.api.post_group_msg(msg.group_id, text="当前没有正在进行的游戏。")
            return

        state_data = await Game.state(game_data, session_uid)
        await self.api.post_group_msg(msg.group_id, text=state_data["msg"])

    async def br_set_life(self, msg: GroupMessage):
        session_uid = msg.group_id
        player_id = msg.user_id
        game_data = await LocalData.read_data(session_uid)

        if not game_data:
            await self.api.post_group_msg(msg.group_id, text="当前没有正在进行的游戏。")
            return

        if game_data["is_start"]:
            await self.api.post_group_msg(msg.group_id, text="游戏已开始，无法修改血量。")
            return

        try:
            life = int(msg.raw_message.split(" ", 1)[1].strip())
            if life < 1 or life > 8:
                raise ValueError
        except (IndexError, ValueError):
            await self.api.post_group_msg(msg.group_id, text="请输入有效的血量值（1-8）。")
            return

        game_data["lives"] = life
        game_data["enemy_lives"] = life
        await LocalData.save_data(session_uid, game_data)
        await self.api.post_group_msg(msg.group_id, text=f"血量已设置为 {life}。")

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
            t_items = "items" if game_data["round_self"] else "eneny_items"

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
        session_uid = msg.group_id
        player_id = msg.user_id
        game_data, error_msg = await self.validate_game_state(session_uid, player_id, check_turn=True)
        if error_msg:
            await self.api.post_group_msg(msg.group_id, text=error_msg)
            return

        # 提取道具名称
        item_name = msg.raw_message.split(" ", 1)[1].strip() if " " in msg.raw_message else None
        if not item_name:
            await self.api.post_group_msg(msg.group_id, text="请输入要使用的道具名称。")
            return

        t_items = "items" if game_data["round_self"] else "eneny_items"

        if "刀" in item_name:
            if game_data[t_items]["knife"] <= 0:
                await self.api.post_group_msg(msg.group_id, text="你没有刀。")
                return
            game_data = await Weapon.use_knife(game_data)
            game_data[t_items]["knife"] -= 1
            await LocalData.save_data(session_uid, game_data)
            await self.api.post_group_msg(msg.group_id, text="刀已使用，你下一次攻击伤害为2（无论是否有子弹）。")

        elif "手铐" in item_name:
            if game_data[t_items]["handcuffs"] <= 0:
                await self.api.post_group_msg(msg.group_id, text="你没有手铐。")
                return
            game_data = await Weapon.use_handcuffs(game_data)
            game_data[t_items]["handcuffs"] -= 1
            await LocalData.save_data(session_uid, game_data)
            await self.api.post_group_msg(msg.group_id, text="手铐已使用，跳过对方一回合。")

        elif "香烟" in item_name:
            if game_data[t_items]["cigarettes"] <= 0:
                await self.api.post_group_msg(msg.group_id, text="你没有香烟。")
                return
            game_data = await Weapon.use_cigarettes(game_data)
            game_data[t_items]["cigarettes"] -= 1
            await LocalData.save_data(session_uid, game_data)
            await self.api.post_group_msg(msg.group_id, text="香烟已使用，血量加1。")

        elif "放大镜" in item_name:
            if game_data[t_items]["glass"] <= 0:
                await self.api.post_group_msg(msg.group_id, text="你没有放大镜。")
                return
            game_data, is_real_bullet = await Weapon.use_glass(game_data)
            game_data[t_items]["glass"] -= 1
            await LocalData.save_data(session_uid, game_data)
            await self.api.post_group_msg(msg.group_id, text=f"放大镜已使用，{'是实弹' if is_real_bullet else '是空弹'}。")

        elif "饮料" in item_name:
            if game_data[t_items]["drink"] <= 0:
                await self.api.post_group_msg(msg.group_id, text="你没有饮料。")
                return
            game_data = await Weapon.use_drink(game_data)
            game_data[t_items]["drink"] -= 1
            await LocalData.save_data(session_uid, game_data)
            game_state = await Game.state(game_data, session_uid)
            await self.api.post_group_msg(msg.group_id, text=f"饮料已使用，退弹一发。\n{game_state['msg']}")

        else:
            await self.api.post_group_msg(msg.group_id, text="无效的道具名称。")

