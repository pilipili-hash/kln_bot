@echo off
title NcatBot 启动器
chcp 65001 >nul

echo ====================================
echo         NcatBot 优化版启动器
echo ====================================
echo.

:: 检查 Python 是否安装
echo [信息] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或更高版本
    echo [提示] 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 显示 Python 版本
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [信息] 当前 Python 版本: %PYTHON_VERSION%

:: 检查虚拟环境
if exist "venv\Scripts\activate.bat" (
    echo [信息] 激活虚拟环境...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [信息] 激活虚拟环境...
    call .venv\Scripts\activate.bat
) else (
    echo [信息] 未检测到虚拟环境，使用系统 Python
    echo [提示] 建议创建虚拟环境: python -m venv venv
)

:: 配置 pip 镜像源
echo [信息] 配置 pip 镜像源...
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple >nul 2>&1
pip config set install.trusted-host mirrors.aliyun.com >nul 2>&1

:: 升级 pip
echo [信息] 升级 pip...
python -m pip install --upgrade pip >nul 2>&1

:: 检查依赖
echo [信息] 检查依赖包...
python -c "import ncatbot" 2>nul
if errorlevel 1 (
    echo [警告] 缺少必要依赖，正在安装...
    echo [信息] 安装依赖包，请稍候...

    :: 优先使用 poetry 安装
    poetry --version >nul 2>&1
    if not errorlevel 1 (
        echo [信息] 使用 Poetry 安装依赖...
        poetry install --only=main
    ) else (
        echo [信息] 使用 pip 安装依赖...
        pip install -r requirements.txt
    )

    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接或手动安装
        echo [提示] 手动安装命令: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo [信息] 依赖安装完成
)

:: 检查配置文件
if not exist "config.yaml" (
    echo [信息] 未找到配置文件，将创建默认配置...
    echo [警告] 请在首次运行后修改 config.yaml 中的配置信息
    echo [提示] 主要需要配置: 机器人QQ号、WebSocket地址、管理员QQ号等
)

:: 创建必要目录
if not exist "data" (
    mkdir data
    echo [信息] 创建数据目录: data
)
if not exist "logs" (
    mkdir logs
    echo [信息] 创建日志目录: logs
)
if not exist "static" (
    mkdir static
    echo [信息] 创建静态文件目录: static
)

echo.
echo [信息] 环境检查完成，启动机器人...
echo [提示] 按 Ctrl+C 可以停止机器人
echo ====================================
echo.

:: 启动机器人
python main.py

echo.
echo ====================================
echo [信息] 机器人已退出
echo [提示] 如果遇到问题，请检查日志文件: logs/bot.log
pause
