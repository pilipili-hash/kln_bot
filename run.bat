@echo off
:: Quick start script - for users with configured environment
title NcatBot Quick Start
chcp 65001 >nul

echo Starting NcatBot...

:: Activate virtual environment if exists
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat
if exist ".venv\Scripts\activate.bat" call .venv\Scripts\activate.bat

:: Create necessary directories
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "static" mkdir static

:: Start bot
python main.py

pause
