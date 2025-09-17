# SignIn 签到系统帮助文档

SIGNIN_HELP = {
    "plugin_name": "签到系统",
    "version": "2.0.0",
    "description": "每日签到打卡系统，记录你的坚持与成长",
    "author": "NcatBot",
    "commands": [
        {
            "command": "签到",
            "description": "每日签到，获得精美签到卡片",
            "usage": "签到",
            "example": "签到",
            "permission": "所有用户"
        },
        {
            "command": "/签到帮助",
            "description": "显示签到系统帮助信息",
            "usage": "/签到帮助 或 签到帮助",
            "example": "/签到帮助",
            "permission": "所有用户"
        },
        {
            "command": "/签到统计",
            "description": "查看个人签到统计数据",
            "usage": "/签到统计 或 签到统计",
            "example": "/签到统计",
            "permission": "所有用户"
        },
        {
            "command": "/签到排行",
            "description": "查看群内签到排行榜",
            "usage": "/签到排行 或 签到排行",
            "example": "/签到排行",
            "permission": "所有用户"
        }
    ],
    "features": [
        "🎨 精美的签到卡片设计，质感十足",
        "💭 温暖有趣的日常分享内容",
        "✨ 贴心实用的每日小提醒",
        "📈 连续签到统计，激励坚持",
        "🏆 群内排行榜，增加互动",
        "📊 详细的个人统计数据",
        "🎁 连续签到特殊称号奖励"
    ],
    "usage_tips": [
        "每天只能签到一次",
        "连续签到天数会累计",
        "断签会重置连续天数",
        "签到卡片包含励志语录和运势",
        "可以查看个人统计和群排行"
    ],
    "rewards": [
        "连续签到7天：🥉 签到新星",
        "连续签到30天：🥈 签到能手", 
        "连续签到100天：🥇 签到达人",
        "连续签到365天：🏆 签到大师"
    ],
    "technical_info": {
        "database": "SQLite数据库存储",
        "image_generation": "PIL图像处理",
        "background_sources": "多源高质量背景图片",
        "quote_sources": "本地+网络励志语录库"
    },
    "changelog": {
        "v2.0.0": [
            "全新的签到卡片设计",
            "添加毛玻璃效果和阴影",
            "丰富的励志语录库",
            "完善的统计系统",
            "群排行榜功能",
            "连续签到奖励称号",
            "多源背景图片支持"
        ],
        "v1.0.0": [
            "基础签到功能",
            "简单的签到图片生成"
        ]
    }
}
