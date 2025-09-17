import aiosqlite
import random
import time
import logging
from typing import Optional, Dict, Any, List

# 设置日志
_log = logging.getLogger("PassionateCowPlugin.utils")

async def init_database(db_path: str):
    """初始化数据库，创建表结构"""
    try:
        async with aiosqlite.connect(db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    qq_id INTEGER PRIMARY KEY,
                    length REAL NOT NULL DEFAULT 0.0,
                    role TEXT NOT NULL DEFAULT 'normal',
                    item TEXT DEFAULT '',
                    last_glue_time INTEGER DEFAULT 0,
                    last_jj_time INTEGER DEFAULT 0,
                    total_battles INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    created_at INTEGER DEFAULT 0,
                    updated_at INTEGER DEFAULT 0
                )
            ''')

            # 创建索引以提高查询性能
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_players_length
                ON players(length DESC)
            ''')

            await db.commit()
            _log.info(f"数据库初始化完成: {db_path}")

    except Exception as e:
        _log.error(f"数据库初始化失败: {e}")
        raise

async def get_player_data(db_path: str, qq_id: int) -> Optional[Dict[str, Any]]:
    """获取玩家数据"""
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT * FROM players WHERE qq_id = ?", (qq_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "qq_id": row[0],
                    "length": row[1],
                    "role": row[2],
                    "item": row[3],
                    "last_glue_time": row[4],
                    "last_jj_time": row[5],
                    "total_battles": row[6] if len(row) > 6 else 0,
                    "wins": row[7] if len(row) > 7 else 0,
                    "created_at": row[8] if len(row) > 8 else 0,
                    "updated_at": row[9] if len(row) > 9 else 0
                }
            return None
    except Exception as e:
        _log.error(f"获取玩家数据失败 (QQ: {qq_id}): {e}")
        return None

async def update_player_data(db_path: str, qq_id: int, data: Dict[str, Any]):
    """更新玩家数据"""
    try:
        current_time = int(time.time())
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO players
                (qq_id, length, role, item, last_glue_time, last_jj_time,
                 total_battles, wins, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                        COALESCE((SELECT created_at FROM players WHERE qq_id = ?), ?), ?)
                """,
                (
                    qq_id,
                    round(data.get("length", 0), 3),  # 精确到小数点后三位
                    data.get("role", "normal"),
                    data.get("item", ""),
                    data.get("last_glue_time", 0),
                    data.get("last_jj_time", 0),
                    data.get("total_battles", 0),
                    data.get("wins", 0),
                    qq_id,  # 用于COALESCE查询
                    current_time,  # 新建时的created_at
                    current_time   # updated_at
                )
            )
            await db.commit()
    except Exception as e:
        _log.error(f"更新玩家数据失败 (QQ: {qq_id}): {e}")
        raise

def determine_role(length: float) -> str:
    """根据长度确定角色"""
    if length >= 1000:
        return "牛头神"
    elif length >= 500:
        return "牛子子龙"
    elif length >= 200:
        return "牛主教"
    elif length >= 100:
        return "牛牛神父"
    elif length >= 15:
        return "伟哥执事"
    elif length > 0:
        return "正常人"
    elif length == 0:
        return "无性人"
    elif length >= -20:
        return "圣女"
    elif length >= -50:
        return "修女"
    elif length >= -100:
        return "色虐侍女"
    elif length >= -200:
        return "色虐领主"
    elif length >= -500:
        return "魅魔"
    elif length >= -1000:
        return "雅儿贝德"
    else:
        return "色虐"

def get_role_description(role: str) -> str:
    """获取角色描述"""
    descriptions = {
        "牛头神": "🐂 传说中的存在，拥有神话之力",
        "牛子子龙": "⚔️ 勇猛的战士，拥有牛胆技能",
        "牛主教": "⚖️ 威严的审判者，可以进行审判",
        "牛牛神父": "🔨 神圣的鞭打者，擅长鞭打技能",
        "伟哥执事": "⚡ 敏捷的战士，可以多重攻击",
        "正常人": "👤 普通的存在，没有特殊技能",
        "无性人": "⚪ 中性的存在，处于平衡状态",
        "圣女": "👼 纯洁的存在，拥有堕落技能",
        "修女": "🛡️ 虔诚的守护者，可以守护",
        "色虐侍女": "🗡️ 危险的存在，拥有腐蚀技能",
        "色虐领主": "💀 混乱的统治者，擅长混乱打击",
        "魅魔": "😈 诱惑的化身，可以引诱他人",
        "雅儿贝德": "🌑 深渊的主宰，拥有深渊之力",
        "色虐": "🔥 极端的存在，可以吞噬一切"
    }
    return descriptions.get(role, "❓ 未知角色")

async def get_leaderboard(db_path: str, msg, bot):
    """获取排行榜"""
    try:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                """
                SELECT qq_id, length, role, total_battles, wins
                FROM players
                ORDER BY length DESC
                LIMIT 10
                """
            )
            rows = await cursor.fetchall()

        if not rows:
            await bot.api.post_group_msg(
                group_id=msg.group_id,
                text="暂无排行榜数据，快去注册牛子吧！"
            )
            return

        leaderboard_text = "🏆 牛子排行榜 TOP 10\n\n"
        for i, (qq_id, length, role, battles, wins) in enumerate(rows, 1):
            win_rate = (wins / battles * 100) if battles > 0 else 0
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            leaderboard_text += (
                f"{medal} QQ:{qq_id}\n"
                f"   长度: {round(length, 3)}cm | {role}\n"
                f"   战绩: {wins}/{battles} (胜率{win_rate:.1f}%)\n\n"
            )

        await bot.api.post_group_msg(group_id=msg.group_id, text=leaderboard_text)

    except Exception as e:
        _log.error(f"获取排行榜失败: {e}")
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text="获取排行榜失败，请稍后再试。"
        )

async def reset_player(db_path: str, msg, bot):
    """重置玩家数据"""
    try:
        qq_id = msg.user_id
        player_data = await get_player_data(db_path, qq_id)

        if not player_data:
            await bot.api.post_group_msg(
                group_id=msg.group_id,
                text="你还没有注册，无需重置！"
            )
            return

        # 重新生成初始数据
        initial_length = random.uniform(-10, 10)
        role = determine_role(initial_length)

        await update_player_data(db_path, qq_id, {
            "length": initial_length,
            "role": role,
            "item": "",
            "last_glue_time": 0,
            "last_jj_time": 0,
            "total_battles": 0,
            "wins": 0
        })

        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"重置成功！你的新牛子长度是 {round(initial_length, 3)} cm，角色是 {role}"
        )

    except Exception as e:
        _log.error(f"重置玩家数据失败: {e}")
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text="重置失败，请稍后再试。"
        )

async def execute_role_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """执行角色技能"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)
    if not player_data or not opponent_data:
        await bot.api.post_group_msg(group_id=msg.group_id, text="请先注册！")
        return

    role = player_data["role"]
    if role == "伟哥执事":
        await wego_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "牛牛神父":
        await cow_priest_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "牛主教":
        await cow_bishop_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "牛子子龙":
        await cow_zilong_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "牛头神":
        await cow_head_skill(db_path, qq_id, msg, bot)
    elif role == "圣女":
        await saint_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "修女":
        await nun_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "色虐侍女":
        await sadistic_maid_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "色虐领主":
        await sadistic_lord_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "魅魔":
        await demon_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "雅儿贝德":
        await yaerbode_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    elif role == "色虐":
        await sadistic_skill(db_path, qq_id, opponent_qq_id, msg, bot)

async def wego_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """伟哥执事技能：多重攻击"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 多重攻击逻辑：对对手进行2次攻击
    attacks = 2
    total_damage = 0
    for _ in range(attacks):
        damage = random.uniform(5, 15)
        total_damage += damage
        opponent_data["length"] -= damage

    new_opponent_role = determine_role(opponent_data["length"])
    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data.get("item", "")
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"伟哥执事发动技能：多重攻击！对 {opponent_qq_id} 造成了 {total_damage} 点伤害，其牛子长度变为 {round(opponent_data['length'], 3)} cm，角色是 {new_opponent_role}"
    )

async def cow_priest_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """牛牛神父技能：鞭打"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 鞭打逻辑：使对手的牛子长度减少三分之一
    damage = opponent_data["length"] / 3
    opponent_data["length"] -= damage
    new_opponent_role = determine_role(opponent_data["length"])

    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data.get("item", "")
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"牛牛神父发动技能：鞭打！对 {opponent_qq_id} 造成了 {damage} 点伤害，其牛子长度变为 {round(opponent_data['length'], 3)} cm，角色是 {new_opponent_role}"
    )

async def cow_bishop_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """牛主教技能：审判"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    player_abs = abs(player_data["length"])
    opponent_abs = abs(opponent_data["length"])

    if player_abs > opponent_abs:
        # 获胜：对方长度绝对值折半，自己获得三倍长度
        opponent_data["length"] = opponent_abs / 2 * -1 if opponent_data["length"] < 0 else opponent_abs / 2
        player_data["length"] += abs(opponent_data["length"]) * 3
    else:
        # 失败：自己损失对应规则长度，80%概率断牛子
        player_data["length"] *= 0.2

    new_opponent_role = determine_role(opponent_data["length"])
    new_player_role = determine_role(player_data["length"])

    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data.get("item", "")
    })

    await update_player_data(db_path, qq_id, {
        "length": player_data["length"],
        "role": new_player_role,
        "item": player_data.get("item", "")
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=
        f"牛主教发动技能：审判！对战结果：{'胜利' if player_abs > opponent_abs else '失败'}！"
        f"你的牛子长度变为 {round(player_data['length'], 3)} cm，角色是 {new_player_role}。"
        f"对手 {opponent_qq_id} 的牛子长度变为 {round(opponent_data['length'], 3)} cm，角色是 {new_opponent_role}"
    )

async def cow_zilong_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """牛子子龙技能：牛胆"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 牛胆逻辑：暂时获得1.5倍长度进行比拼
    temp_length = player_data["length"] * 1.5
    player_abs = abs(temp_length)
    opponent_abs = abs(opponent_data["length"])

    if player_abs > opponent_abs:
        # 胜利：维持1.5倍长度
        player_data["length"] = temp_length
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"牛子子龙发动技能：牛胆！胜利！你的牛子长度变为 {round(temp_length, 3)} cm"
        )
    else:
        # 失败：扣除对应取整数值
        deduction = int(abs(temp_length))
        player_data["length"] -= deduction
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"牛子子龙发动技能：牛胆！失败！你的牛子长度减少 {deduction} cm，变为 {round(player_data['length'], 3)} cm"
        )

    new_player_role = determine_role(player_data["length"])
    await update_player_data(db_path, qq_id, {
        "length": player_data["length"],
        "role": new_player_role,
        "item": player_data.get("item", "")
    })

async def cow_head_skill(db_path, qq_id, msg, bot):
    """牛头神技能：神话之力"""
    player_data = await get_player_data(db_path, qq_id)
    # 神话之力逻辑：连续打胶10次，胜率为100%
    for _ in range(10):
        player_data["length"] += 0.5
    new_role = determine_role(player_data["length"])
    await update_player_data(db_path, qq_id, {
        "length": player_data["length"],
        "role": new_role,
        "item": player_data.get("item", "")
    })
    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"牛头神发动技能：神话之力！连续打胶10次成功！你的牛子长度变为 {round(player_data['length'], 3)} cm，角色是 {new_role}"
    )

async def saint_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """圣女技能：堕落"""
    try:
        player_data = await get_player_data(db_path, qq_id)
        opponent_data = await get_player_data(db_path, opponent_qq_id)

        if not player_data or not opponent_data:
            return

        # 修复逻辑：圣女技能应该是诱惑对方
        if opponent_data["length"] > 0:
            # 对正长度玩家：有概率让对方堕落
            success_rate = min(0.7, abs(player_data["length"]) / 100)  # 圣女越强，成功率越高
            if random.random() < success_rate:
                # 成功：对方损失长度，圣女获得部分长度
                damage = random.uniform(10, 20)
                opponent_data["length"] -= damage
                player_data["length"] += damage * 0.3  # 圣女获得30%
                result_msg = "堕落成功！对方被诱惑了"
            else:
                # 失败：圣女受到反噬
                damage = random.uniform(5, 10)
                player_data["length"] -= damage
                result_msg = "堕落失败！受到了反噬"
        else:
            # 对负长度玩家：互相影响
            mutual_change = random.uniform(3, 8)
            player_data["length"] -= mutual_change
            opponent_data["length"] -= mutual_change
            result_msg = "同类相斥！双方都受到了影响"

        # 更新角色
        new_player_role = determine_role(player_data["length"])
        new_opponent_role = determine_role(opponent_data["length"])

        # 更新数据库
        await update_player_data(db_path, qq_id, {
            "length": player_data["length"],
            "role": new_player_role,
            "item": player_data.get("item", "")
        })
        await update_player_data(db_path, opponent_qq_id, {
            "length": opponent_data["length"],
            "role": new_opponent_role,
            "item": opponent_data.get("item", "")
        })

        # 发送结果消息
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=(
                f"圣女发动技能：堕落！{result_msg}\n"
                f"你的牛子长度变为 {round(player_data['length'], 3)} cm，角色是 {new_player_role}\n"
                f"对手 {opponent_qq_id} 的牛子长度变为 {round(opponent_data['length'], 3)} cm，角色是 {new_opponent_role}"
            )
        )

    except Exception as e:
        _log.error(f"圣女技能执行失败: {e}")
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text="技能执行失败，请稍后再试。"
        )
async def nun_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """修女技能：守护"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 守护逻辑：有50%概率抵挡长度损失
    if random.random() < 0.5:  # 守护成功
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"修女发动技能：守护！成功抵挡了长度损失！"
        )
    else:  # 守护失败，复用圣女的jj规则
        await saint_skill(db_path, qq_id, opponent_qq_id, msg, bot)

async def sadistic_maid_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """色虐侍女技能：腐蚀"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 腐蚀逻辑：使对手打胶时有80%概率缩短长度
    opponent_data["item"] = "腐蚀"
    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": opponent_data["role"],
        "item": "腐蚀"
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"色虐侍女发动技能：腐蚀！{opponent_qq_id} 打胶时有80%概率缩短长度"
    )

async def sadistic_lord_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """色虐领主技能：混乱打击"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 混乱打击逻辑：无视长度，随机减少对手长度
    damage = random.uniform(10, 30)
    opponent_data["length"] -= damage
    new_opponent_role = determine_role(opponent_data["length"])

    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data.get("item", "")
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"色虐领主发动技能：混乱打击！对 {opponent_qq_id} 造成了 {damage} 点伤害，其牛子长度变为 {round(opponent_data['length'], 3)} cm，角色是 {new_opponent_role}"
    )

async def demon_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """魅魔技能：引诱"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 引诱逻辑：对方付出自身牛子绝对值长度的5%
    cost = abs(opponent_data["length"]) * 0.05
    opponent_data["length"] -= cost
    player_data["length"] += cost

    new_opponent_role = determine_role(opponent_data["length"])
    new_player_role = determine_role(player_data["length"])

    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data.get("item", "")
    })

    await update_player_data(db_path, qq_id, {
        "length": player_data["length"],
        "role": new_player_role,
        "item": player_data.get("item", "")
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=
        f"魅魔发动技能：引诱！{opponent_qq_id} 损失了 {cost} cm，你的牛子长度增加到 {round(player_data['length'], 3)} cm，角色是 {new_player_role}"
    )

async def yaerbode_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """雅儿贝德技能：深渊"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 深渊逻辑：对方牛子绝对值长度减10%
    reduction = abs(opponent_data["length"]) * 0.1
    opponent_data["length"] = opponent_data["length"] * 0.9 if opponent_data["length"] > 0 else opponent_data["length"] * 1.1
    new_opponent_role = determine_role(opponent_data["length"])

    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data.get("item", "")
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"雅儿贝德发动技能：深渊！{opponent_qq_id} 的牛子长度减少了 {reduction} cm，变为 {round(opponent_data['length'], 3)} cm，角色是 {new_opponent_role}"
    )

async def sadistic_skill(db_path, qq_id, opponent_qq_id, msg, bot):
    """色虐技能：吞噬"""
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 吞噬逻辑：吸收对方牛子长度的1/10
    absorption = abs(opponent_data["length"]) * 0.1
    opponent_data["length"] -= absorption
    player_data["length"] += absorption

    new_opponent_role = determine_role(opponent_data["length"])
    new_player_role = determine_role(player_data["length"])

    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data.get("item", "")
    })

    await update_player_data(db_path, qq_id, {
        "length": player_data["length"],
        "role": new_player_role,
        "item": player_data.get("item", "")
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=
        f"色虐发动技能：吞噬！吸收了 {opponent_qq_id} 的 {absorption} cm，你的牛子长度变为 {round(player_data['length'], 3)} cm，角色是 {new_player_role}"
    )

async def register_player(db_path, msg, bot):
    """注册玩家"""
    qq_id = msg.user_id
    player_data = await get_player_data(db_path, qq_id)
    if player_data:
        await bot.api.post_group_msg(group_id=msg.group_id, text="你已经注册过了！")
        return

    initial_length = random.uniform(-10, 10)
    role = determine_role(initial_length)

    await update_player_data(db_path, qq_id, {
        "length": initial_length,
        "role": role,
        "item": "",
        "last_glue_time": 0,
        "last_jj_time": 0
    })
    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"注册成功！你的初始牛子长度是 {round(initial_length, 3)} cm，角色是 {role}"
    )

async def apply_glue(db_path, msg, bot):
    """打胶操作"""
    try:
        qq_id = msg.user_id
        player_data = await get_player_data(db_path, qq_id)
        if not player_data:
            await bot.api.post_group_msg(group_id=msg.group_id, text="请先注册！")
            return

        # 检查冷却时间
        current_time = int(time.time())
        cooldown_time = 3 * 60 * 60  # 3小时冷却
        if current_time - player_data["last_glue_time"] < cooldown_time:
            remaining_time = cooldown_time - (current_time - player_data["last_glue_time"])
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            await bot.api.post_group_msg(
                group_id=msg.group_id,
                text=f"⏰ 打胶冷却中，剩余时间: {hours}小时{minutes}分钟"
            )
            return

        # 检查是否有腐蚀效果
        has_corruption = player_data.get("item") == "腐蚀"

        # 检查角色是否为牛头神
        if player_data["role"] == "牛头神":
            # 触发牛头神技能：神话之力
            total_gain = 0
            for _ in range(10):  # 连续打胶10次
                gain = 0.5
                if has_corruption and random.random() < 0.8:
                    gain = -0.3  # 腐蚀效果
                total_gain += gain
                player_data["length"] += gain

            new_role = determine_role(player_data["length"])
            await update_player_data(db_path, qq_id, {
                "length": player_data["length"],
                "role": new_role,
                "item": "",  # 清除腐蚀效果
                "last_glue_time": current_time,
                "last_jj_time": player_data["last_jj_time"],
                "total_battles": player_data.get("total_battles", 0),
                "wins": player_data.get("wins", 0)
            })

            corruption_msg = "（受到腐蚀影响）" if has_corruption else ""
            await bot.api.post_group_msg(
                group_id=msg.group_id,
                text=f"🐂 牛头神发动技能：神话之力！连续打胶10次{corruption_msg}！总变化 {round(total_gain, 3)} cm，你的牛子长度变为 {round(player_data['length'], 3)} cm，角色是 {new_role}"
            )
            return

        # 普通打胶逻辑
        base_change = random.uniform(0.1, 1.0)  # 更随机的变化
        success_rate = 0.6  # 60%成功率

        if random.random() < success_rate:
            change = base_change
            result_msg = "成功"
        else:
            change = -base_change * 0.5
            result_msg = "失败"

        # 检查腐蚀效果
        if has_corruption and random.random() < 0.8:
            change = -abs(change)  # 80%概率变为负数
            result_msg += "（受到腐蚀影响）"
            player_data["item"] = ""  # 清除腐蚀效果

        new_length = player_data["length"] + change
        new_role = determine_role(new_length)

        # 更新数据
        await update_player_data(db_path, qq_id, {
            "length": new_length,
            "role": new_role,
            "item": player_data["item"],
            "last_glue_time": current_time,
            "last_jj_time": player_data["last_jj_time"],
            "total_battles": player_data.get("total_battles", 0),
            "wins": player_data.get("wins", 0)
        })

        change_text = f"+{round(change, 3)}" if change >= 0 else f"{round(change, 3)}"
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"💦 打胶{result_msg}！变化 {change_text} cm，你的牛子长度变为 {round(new_length, 3)} cm，角色是 {new_role}"
        )

    except Exception as e:
        _log.error(f"打胶操作失败: {e}")
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text="打胶操作失败，请稍后再试。"
        )

async def jj_battle(db_path, msg, bot):
    """jj对战"""
    qq_id = msg.user_id
    player_data = await get_player_data(db_path, qq_id)
    if not player_data:
        await bot.api.post_group_msg(group_id=msg.group_id, text="请先注册！")
        return

    # 检查冷却时间
    current_time = int(time.time())
    if current_time - player_data["last_jj_time"] < 3 * 60 * 60:  # 3小时冷却
        remaining_time = 3 * 60 * 60 - (current_time - player_data["last_jj_time"])
        hours = remaining_time // 3600
        minutes = (remaining_time % 3600) // 60
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"jj对战冷却中，剩余时间: {hours}小时{minutes}分钟"
        )
        return

    # 提取被@的用户ID
    opponent_qq_id = None
    for segment in msg.message:
        if segment.get("type") == "at" and segment.get("data", {}).get("qq"):
            opponent_qq_id = int(segment["data"]["qq"])
            break

    if not opponent_qq_id:
        await bot.api.post_group_msg(group_id=msg.group_id, text="请@一个玩家进行对战！")
        return

    # 获取被@玩家的数据
    opponent_data = await get_player_data(db_path, opponent_qq_id)
    if not opponent_data:
        await bot.api.post_group_msg(group_id=msg.group_id, text="被@的玩家尚未注册！")
        return

    # 修复对战逻辑：只有发起者触发技能，避免双重技能导致的不平衡
    original_player_length = player_data["length"]
    original_opponent_length = opponent_data["length"]

    # 只触发发起者的技能
    await execute_role_skill(db_path, qq_id, opponent_qq_id, msg, bot)

    # 重新获取数据（技能可能已经修改了数据）
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 基于技能效果后的长度决定胜负
    if abs(player_data["length"]) > abs(opponent_data["length"]):
        result = "胜利"
        # 胜利者获得额外奖励
        bonus = random.uniform(1, 3)
        player_data["length"] += bonus if player_data["length"] >= 0 else -bonus
        # 更新胜利统计
        player_data["wins"] = player_data.get("wins", 0) + 1
    elif abs(player_data["length"]) < abs(opponent_data["length"]):
        result = "失败"
        # 失败者受到额外惩罚
        penalty = random.uniform(0.5, 2)
        player_data["length"] -= penalty if player_data["length"] >= 0 else -penalty
    else:
        result = "平局"
        # 平局双方都有小幅变化
        change = random.uniform(-1, 1)
        player_data["length"] += change
        opponent_data["length"] -= change

    # 更新角色
    new_player_role = determine_role(player_data["length"])
    new_opponent_role = determine_role(opponent_data["length"])

    # 更新战斗统计
    player_data["total_battles"] = player_data.get("total_battles", 0) + 1
    opponent_data["total_battles"] = opponent_data.get("total_battles", 0) + 1

    # 更新数据库
    await update_player_data(db_path, qq_id, {
        "length": player_data["length"],
        "role": new_player_role,
        "item": player_data["item"],
        "last_glue_time": player_data["last_glue_time"],
        "last_jj_time": current_time,
        "total_battles": player_data["total_battles"],
        "wins": player_data.get("wins", 0)
    })

    await update_player_data(db_path, opponent_qq_id, {
        "length": opponent_data["length"],
        "role": new_opponent_role,
        "item": opponent_data["item"],
        "last_glue_time": opponent_data["last_glue_time"],
        "last_jj_time": opponent_data["last_jj_time"],
        "total_battles": opponent_data["total_battles"],
        "wins": opponent_data.get("wins", 0)
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=(
            f"⚔️ 对战结果：{result}！\n"
            f"你的牛子长度: {round(player_data['length'], 3)} cm ({new_player_role})\n"
            f"对手的牛子长度: {round(opponent_data['length'], 3)} cm ({new_opponent_role})\n"
            f"战绩: {player_data.get('wins', 0)}/{player_data['total_battles']}"
        )
    )

async def use_item(db_path, msg, bot):
    """使用道具"""
    qq_id = msg.user_id
    player_data = await get_player_data(db_path, qq_id)
    if not player_data:
        await bot.api.post_group_msg(group_id=msg.group_id, text="请先注册！")
        return

    item = msg.raw_message.split()[1] if len(msg.raw_message.split()) > 1 else ""
    if not item:
        await bot.api.post_group_msg(group_id=msg.group_id, text="请指定要使用的道具！")
        return

    if item == "牛子逆转" and player_data["item"] == "牛子逆转":
        new_length = random.uniform(-10, 10)
        new_role = determine_role(new_length)

        await update_player_data(db_path, qq_id, {
            "length": new_length,
            "role": new_role,
            "item": "",
            "last_glue_time": player_data["last_glue_time"],
            "last_jj_time": player_data["last_jj_time"]
        })
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"使用牛子逆转成功！你的牛子长度变为 {round(new_length, 3)} cm，角色是 {new_role}"
        )
    else:
        await bot.api.post_group_msg(group_id=msg.group_id, text="你没有这个道具或者道具无效！")

async def query_player(db_path, msg, bot):
    """查询玩家信息"""
    qq_id = msg.user_id
    player_data = await get_player_data(db_path, qq_id)
    if not player_data:
        await bot.api.post_group_msg(group_id=msg.group_id, text="你尚未注册！")
        return

    # 更新角色
    new_role = determine_role(player_data["length"])
    if new_role != player_data["role"]:
        await update_player_data(db_path, qq_id, {
            "length": player_data["length"],
            "role": new_role,
            "item": player_data["item"],
            "last_glue_time": player_data["last_glue_time"],
            "last_jj_time": player_data["last_jj_time"]
        })

    glue_cooldown = max(0, 3 * 3600 - (int(time.time()) - player_data["last_glue_time"]))
    jj_cooldown = max(0, 3 * 3600 - (int(time.time()) - player_data["last_jj_time"]))
    glue_hours = glue_cooldown // 3600
    glue_minutes = (glue_cooldown % 3600) // 60
    jj_hours = jj_cooldown // 3600
    jj_minutes = (jj_cooldown % 3600) // 60

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=(
            f"你的牛子长度是 {round(player_data['length'], 3)} cm，角色是 {new_role}。\n"
            f"打胶冷却时间: {glue_hours}小时{glue_minutes}分钟\n"
            f"jj对战冷却时间: {jj_hours}小时{jj_minutes}分钟"
        )
    )