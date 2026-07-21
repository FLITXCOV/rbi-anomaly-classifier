@echo off
title RBI Anomaly Classifier - Setup and Launch
echo.
echo ============================================
echo   RBI Anomaly Classifier - Launcher
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo         Please install Python 3.10+ from https://www.python.org
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

:: Check if dependencies are already installed on this PC
echo [STEP 1] Checking system dependencies...
python -c "import pandas, numpy, openpyxl, customtkinter, matplotlib" >nul 2>&1

if errorlevel 1 (
    echo [INFO] Required packages not found on this machine.
    echo        Installing packages now - this only happens once per PC...
    echo.
    pip install -r requirements.txt --quiet
    if errorlevel 1 (
        echo.
        echo [ERROR] Failed to install dependencies.
        echo         Try running: pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo.
    echo [OK] Packages installed successfully.
) else (
    echo [OK] All required packages found on this PC.
)
echo.

:: Launch the application
echo [STEP 2] Launching RBI Anomaly Classifier...
echo.
python app_gui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Application crashed. See error above.
    pause
    exit /b 1
)

pause
