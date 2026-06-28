@echo off
chcp 65001 >nul
title Concrete Floor Design - Install

echo ========================================
echo Concrete Floor Design
echo Windows install script
echo ========================================
echo.

cd /d "%~dp0"

echo Project folder: %cd%
echo.

if not exist "requirements.txt" (
    echo ERROR: requirements.txt was not found.
    echo Please put this script in the project root folder.
    echo.
    pause
    exit /b 1
)

python --version >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python was not found.
    echo Please install Python 3 and add it to PATH.
    echo.
    pause
    exit /b 1
)

echo Python:
python --version
echo.
echo Installing dependencies...
echo.

python -m pip install -r requirements.txt
set INSTALL_STATUS=%errorlevel%

echo.
if %INSTALL_STATUS%==0 (
    echo Install finished.
    echo You can now run run_win.bat.
) else (
    echo ERROR: Install failed with code %INSTALL_STATUS%.
    echo Check the messages above.
)
echo.

pause
exit /b %INSTALL_STATUS%
