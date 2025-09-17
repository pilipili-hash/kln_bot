"""
BiliVideoInfo插件帮助文档
"""

BILIvideoinfo_HELP = {
    "plugin_name": "BiliVideoInfo",
    "version": "2.0.0",
    "description": "B站视频信息获取插件，自动识别并展示视频详细信息",
    "author": "NcatBot",
    "usage": "直接在群聊中发送包含B站视频链接的消息即可",
    
    "commands": [
        {
            "command": "/bili帮助",
            "description": "显示插件帮助信息",
            "usage": "/bili帮助",
            "example": "/bili帮助"
        }
    ],
    
    "auto_triggers": [
        {
            "trigger": "BV号",
            "description": "自动识别BV号并获取视频信息",
            "example": "BV1xx4y1x7xx"
        },
        {
            "trigger": "AV号", 
            "description": "自动识别AV号并获取视频信息",
            "example": "av123456"
        },
        {
            "trigger": "B站链接",
            "description": "自动识别B站视频链接",
            "example": "https://www.bilibili.com/video/BVxxx"
        }
    ],
    
    "features": [
        "🎯 自动识别B站视频链接，无需手动触发",
        "📊 详细的视频信息展示（标题、UP主、数据等）",
        "🖼️ 视频封面图片展示",
        "⚡ 智能缓存系统，避免重复请求",
        "🔄 批量处理多个视频链接",
        "📈 友好的数字格式化显示",
        "🛡️ 请求限流保护，避免频繁调用",
        "🎨 美观的信息排版和emoji装饰"
    ],
    
    "supported_formats": [
        "BV号：BV1xx4y1x7xx",
        "AV号：av123456", 
        "完整链接：https://www.bilibili.com/video/BVxxx",
        "短链接：b23.tv/xxx"
    ],
    
    "display_info": [
        "📺 视频标题和封面",
        "👤 UP主信息",
        "🏷️ 视频分区",
        "⏱️ 视频时长",
        "📅 发布时间",
        "📊 播放、点赞、投币、收藏等数据",
        "📝 视频简介",
        "🔗 视频链接"
    ],
    
    "notes": [
        "插件会自动识别消息中的视频链接",
        "支持一次处理多个视频（最多3个）",
        "使用缓存机制，1小时内重复请求会使用缓存",
        "有请求频率限制，避免过于频繁的调用",
        "如果获取失败，请检查视频ID是否正确或稍后再试"
    ],
    
    "examples": [
        {
            "input": "BV1xx4y1x7xx",
            "output": "自动获取并展示该视频的详细信息"
        },
        {
            "input": "https://www.bilibili.com/video/BV1xx4y1x7xx",
            "output": "自动识别链接中的BV号并获取视频信息"
        },
        {
            "input": "/bili帮助",
            "output": "显示插件的详细帮助信息"
        }
    ]
}
