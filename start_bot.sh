#!/bin/bash

# NcatBot 启动脚本 (Linux/Mac)
# 使用方法: chmod +x start_bot.sh && ./start_bot.sh

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[信息]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[成功]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[警告]${NC} $1"
}

print_error() {
    echo -e "${RED}[错误]${NC} $1"
}

# 显示标题
echo "===================================="
echo "        NcatBot 优化版启动器"
echo "===================================="
echo

# 检查 Python 是否安装
print_info "检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        print_error "未检测到 Python，请先安装 Python 3.10 或更高版本"
        print_info "Ubuntu/Debian: sudo apt install python3 python3-pip"
        print_info "CentOS/RHEL: sudo yum install python3 python3-pip"
        print_info "macOS: brew install python3"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# 显示 Python 版本
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
print_info "当前 Python 版本: $PYTHON_VERSION"

# 检查 Python 版本是否满足要求
PYTHON_MAJOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.major)")
PYTHON_MINOR=$($PYTHON_CMD -c "import sys; print(sys.version_info.minor)")

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    print_error "Python 版本过低，需要 Python 3.10 或更高版本"
    exit 1
fi

# 检查虚拟环境
if [ -d "venv" ]; then
    print_info "激活虚拟环境..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    print_info "激活虚拟环境..."
    source .venv/bin/activate
else
    print_info "未检测到虚拟环境，使用系统 Python"
    print_warning "建议创建虚拟环境: python3 -m venv venv"
fi

# 配置 pip 镜像源
print_info "配置 pip 镜像源..."
$PYTHON_CMD -m pip config set global.index-url https://mirrors.aliyun.com/pypi/simple > /dev/null 2>&1
$PYTHON_CMD -m pip config set install.trusted-host mirrors.aliyun.com > /dev/null 2>&1

# 升级 pip
print_info "升级 pip..."
$PYTHON_CMD -m pip install --upgrade pip > /dev/null 2>&1

# 检查依赖
print_info "检查依赖包..."
if ! $PYTHON_CMD -c "import ncatbot" 2>/dev/null; then
    print_warning "缺少必要依赖，正在安装..."
    print_info "安装依赖包，请稍候..."
    
    # 优先使用 poetry 安装
    if command -v poetry &> /dev/null; then
        print_info "使用 Poetry 安装依赖..."
        poetry install --only=main
    else
        print_info "使用 pip 安装依赖..."
        $PYTHON_CMD -m pip install -r requirements.txt
    fi
    
    if [ $? -ne 0 ]; then
        print_error "依赖安装失败，请检查网络连接或手动安装"
        print_info "手动安装命令: $PYTHON_CMD -m pip install -r requirements.txt"
        exit 1
    fi
    print_success "依赖安装完成"
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    print_info "未找到配置文件，将创建默认配置..."
    print_warning "请在首次运行后修改 config.yaml 中的配置信息"
    print_info "主要需要配置: 机器人QQ号、WebSocket地址、管理员QQ号等"
fi

# 创建必要目录
for dir in "data" "logs" "static"; do
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        print_info "创建目录: $dir"
    fi
done

echo
print_info "环境检查完成，启动机器人..."
print_info "按 Ctrl+C 可以停止机器人"
echo "===================================="
echo

# 设置信号处理
trap 'echo; print_info "正在停止机器人..."; exit 0' INT TERM

# 启动机器人
$PYTHON_CMD main.py

echo
echo "===================================="
print_info "机器人已退出"
print_info "如果遇到问题，请检查日志文件: logs/bot.log"
