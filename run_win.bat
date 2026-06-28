@echo off
chcp 65001 >nul
title Concrete Floor Design - Run

echo ========================================
echo Concrete Floor Design
echo Windows run script
echo ========================================
echo.

cd /d "%~dp0"

echo Project folder: %cd%
echo.

if not exist "app.py" (
    echo ERROR: app.py was not found.
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
echo Starting Streamlit...
echo If the browser does not open, visit http://localhost:8501
echo.

python -m streamlit run app.py
set RUN_STATUS=%errorlevel%

echo.
if %RUN_STATUS%==0 (
    echo Program closed.
) else (
    echo ERROR: Program exited with code %RUN_STATUS%.
    echo Check the messages above.
)
echo.

pause
exit /b %RUN_STATUS%
