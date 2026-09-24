@echo off
REM ==============================================================================
REM  vPS Share — One-Click Launcher for Windows
REM  VPS file explorer and file transfer tool by PSTECH
REM ==============================================================================

setlocal enabledelayedexpansion
title vPS Share

cd /d "%~dp0"

REM 1. Check for Python
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Python 3 was not found in your PATH!
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

REM 2. Check minimal dependencies
python -c "import fastapi, uvicorn" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [vPS Share] Installing required packages from requirements.txt...
    python -m pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [Error] Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM 3. Launch application
python run.py %*
if %ERRORLEVEL% NEQ 0 (
    pause
)
