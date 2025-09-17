#!/bin/bash
# 快速启动脚本 - 适用于已配置好环境的用户

echo "启动 NcatBot..."

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 创建必要目录
mkdir -p data logs static

# 确定 Python 命令
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# 启动机器人
$PYTHON_CMD main.py
