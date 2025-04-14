import aiosqlite
import random
import time

async def init_database(db_path):
    """初始化数据库，创建表结构"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS players (
                qq_id INTEGER PRIMARY KEY,
                length REAL,
                role TEXT,
                item TEXT,
                last_glue_time INTEGER,
                last_jj_time INTEGER
            )
        ''')
        await db.commit()

async def get_player_data(db_path, qq_id):
    """获取玩家数据"""
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
                "last_jj_time": row[5]
            }
        return None

async def update_player_data(db_path, qq_id, data):
    """更新玩家数据"""
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO players (qq_id, length, role, item, last_glue_time, last_jj_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                qq_id,
                round(data.get("length", 0), 3),  # 精确到小数点后三位
                data.get("role", "normal"),
                data.get("item", ""),
                data.get("last_glue_time", 0),
                data.get("last_jj_time", 0)
            )
        )
        await db.commit()

def determine_role(length):
    """根据长度确定角色"""
    if 0 < length < 15:
        return "正常人"
    elif 15 <= length < 100:
        return "伟哥执事"
    elif 100 <= length < 200:
        return "牛牛神父"
    elif 200 <= length < 500:
        return "牛主教"
    elif 500 <= length < 1000:
        return "牛子子龙"
    elif length >= 1000:
        return "牛头神"
    elif -20 <= length < 0:
        return "圣女"
    elif -50 <= length < -20:
        return "修女"
    elif -100 <= length < -50:
        return "色虐侍女"
    elif -200 <= length < -100:
        return "色虐领主"
    elif -500 <= length < -200:
        return "魅魔"
    elif -1000 <= length < -500:
        return "雅儿贝德"
    else:
        return "色虐"

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
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 对战正长度玩家时，判断对方是否让自己舒服
    if opponent_data["length"] > 0:
        # 对方牛子越长，修女越容易舒服
        comfort_threshold = max(10, opponent_data["length"] * 0.1)
        if random.uniform(0, opponent_data["length"]) > comfort_threshold:
            # 舒服：堕落，自己的牛子缩短，对方获得负长度
            player_data["length"] -= random.uniform(5, 10)
            opponent_data["length"] += player_data["length"] * 0.3
        else:
            # 不舒服：增加自己的长度，对方缩短
            player_data["length"] += random.uniform(2, 5)
            opponent_data["length"] -= random.uniform(2, 5)
    else:
        # 对战圣女或修女时，直接触发堕落
        player_data["length"] -= random.uniform(5, 10)
        opponent_data["length"] -= random.uniform(5, 10)

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
            f"圣女发动技能：堕落！\n"
            f"你的牛子长度变为 {round(player_data['length'], 3)} cm，角色是 {new_player_role}。\n"
            f"对手 {opponent_qq_id} 的牛子长度变为 {round(opponent_data['length'], 3)} cm，角色是 {new_opponent_role}。"
        )
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
    qq_id = msg.user_id
    player_data = await get_player_data(db_path, qq_id)
    if not player_data:
        await bot.api.post_group_msg(group_id=msg.group_id, text="请先注册！")
        return

    # 检查冷却时间
    current_time = int(time.time())
    if current_time - player_data["last_glue_time"] < 3 * 60 * 60:  # 3小时冷却
        remaining_time = 3 * 60 * 60 - (current_time - player_data["last_glue_time"])
        hours = remaining_time // 3600
        minutes = (remaining_time % 3600) // 60
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"打胶冷却中，剩余时间: {hours}小时{minutes}分钟"
        )
        return

    # 检查角色是否为牛头神
    if player_data["role"] == "牛头神":
        # 触发牛头神技能：神话之力
        for _ in range(10):  # 连续打胶10次
            player_data["length"] += 0.5
        new_role = determine_role(player_data["length"])
        await update_player_data(db_path, qq_id, {
            "length": player_data["length"],
            "role": new_role,
            "item": player_data["item"],
            "last_glue_time": current_time,
            "last_jj_time": player_data["last_jj_time"]
        })
        await bot.api.post_group_msg(
            group_id=msg.group_id,
            text=f"牛头神发动技能：神话之力！连续打胶10次成功！你的牛子长度变为 {round(player_data['length'], 3)} cm，角色是 {new_role}"
        )
        return

    # 普通打胶逻辑
    change = random.choice([0.5, -0.5])
    new_length = player_data["length"] + change
    new_role = determine_role(new_length)

    # 更新冷却时间
    await update_player_data(db_path, qq_id, {
        "length": new_length,
        "role": new_role,
        "item": player_data["item"],
        "last_glue_time": current_time,
        "last_jj_time": player_data["last_jj_time"]
    })
    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"打胶成功！你的牛子长度变为 {round(new_length, 3)} cm，角色是 {new_role}"
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

    # 触发双方技能
    await execute_role_skill(db_path, qq_id, opponent_qq_id, msg, bot)
    await execute_role_skill(db_path, opponent_qq_id, qq_id, msg, bot)

    # 更新玩家数据
    player_data = await get_player_data(db_path, qq_id)
    opponent_data = await get_player_data(db_path, opponent_qq_id)

    # 技能触发后直接决定胜负
    if player_data["length"] > opponent_data["length"]:
        result = "胜利"
    elif player_data["length"] < opponent_data["length"]:
        result = "失败"
    else:
        result = "平局"

    # 更新冷却时间
    await update_player_data(db_path, qq_id, {
        "length": player_data["length"],
        "role": player_data["role"],
        "item": player_data["item"],
        "last_glue_time": player_data["last_glue_time"],
        "last_jj_time": current_time
    })

    await bot.api.post_group_msg(
        group_id=msg.group_id,
        text=f"对战结果：{result}！你的牛子长度是 {round(player_data['length'], 3)} cm，角色是 {player_data['role']}。\n"
             f"对手的牛子长度是 {round(opponent_data['length'], 3)} cm，角色是 {opponent_data['role']}。"
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