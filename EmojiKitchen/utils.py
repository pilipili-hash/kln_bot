import os
import json
import logging

logger = logging.getLogger(__name__)

# 设置路径
current_directory = os.path.dirname(os.path.realpath(__file__))

# 加载 JSON 数据
with open(os.path.join(current_directory, 'metadata.json'), 'r', encoding='utf-8') as i:
    data = json.load(i)

with open(os.path.join(current_directory, 'known.json'), 'r', encoding='utf-8') as i:
    emoji_list = json.load(i)

async def mix_emoji(a: str, b: str) -> str:
    """
    根据本地 JSON 数据返回 Emoji 图片地址。
    """
    a = str(hex(ord(a))).lstrip('0x')
    b = str(hex(ord(b))).lstrip('0x')

    logger.info(f"Emoji1: {a}, Emoji2: {b}")

    if a in emoji_list and b in emoji_list:
        # 遍历 JSON 数据查找匹配
        for i in range(len(data[a])):
            if b == data[a][i]['rightEmojiCodepoint'] and a == data[a][i]['leftEmojiCodepoint']:
                url = data[a][i]['gStaticUrl']
                logger.info(f"Returning URL: {url}")
                return url

            elif b == data[a][i]['leftEmojiCodepoint'] and a == data[a][i]['rightEmojiCodepoint']:
                url = data[a][i]['gStaticUrl']
                logger.info(f"Returning URL: {url}")
                return url

        for i in range(len(data[b])):
            if a == data[b][i]['rightEmojiCodepoint'] and b == data[b][i]['leftEmojiCodepoint']:
                url = data[b][i]['gStaticUrl']
                logger.info(f"Returning URL: {url}")
                return url

            elif a == data[b][i]['leftEmojiCodepoint'] and b == data[b][i]['rightEmojiCodepoint']:
                url = data[b][i]['gStaticUrl']
                logger.info(f"Returning URL: {url}")
                return url

        return "不支持的 Emoji 组合"
    else:
        if a not in emoji_list:
            return f"不支持的 Emoji：{chr(int(a, 16))}"
        else:
            return f"不支持的 Emoji：{chr(int(b, 16))}"