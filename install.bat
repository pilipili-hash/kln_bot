@echo off
title NcatBot Installer

echo ====================================
echo         NcatBot Installer
echo ====================================
echo.

echo Checking Python...
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    echo Please install Python 3.10+
    pause
    exit /b 1
)

echo.
echo Setting up virtual environment...
if exist "venv" (
    echo Using existing virtual environment...
) else (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Configuring pip mirror...
python -m pip config set global.index-url https://mirrors.aliyun.com/pypi/simple
python -m pip config set install.trusted-host mirrors.aliyun.com

echo Upgrading pip...
python -m pip install --upgrade pip

echo.
echo Installing dependencies (this may take a few minutes)...

REM Try to install from fixed requirements first
if exist "requirements-fixed.txt" (
    echo Using fixed requirements...
    python -m pip install -r requirements-fixed.txt
) else (
    echo Installing core packages...
    python -m pip install "urllib3>=1.26.20,<2.0.0"
    python -m pip install "requests>=2.32.0"
    python -m pip install "ncatbot>=3.8.10"
    python -m pip install aiofiles aiohttp aiosqlite websockets
    python -m pip install beautifulsoup4 fuzzywuzzy httpx
    python -m pip install Pillow "pixivpy3>=3.7.5"
    python -m pip install pyyaml pydantic psutil numpy qrcode
)

echo.
echo Creating directories...
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "static" mkdir static

echo.
echo Installation completed!
echo.
echo Starting NcatBot...
python main.py

pause
