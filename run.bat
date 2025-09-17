@echo off
:: 快速启动脚本 - 适用于已配置好环境的用户
title NcatBot 快速启动
chcp 65001 >nul

echo 启动 NcatBot...

:: 激活虚拟环境（如果存在）
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

:: 创建必要目录
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "static" mkdir static

:: 启动机器人
python main.py

pause
