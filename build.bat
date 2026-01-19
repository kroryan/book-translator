@echo off
REM ============================================================
REM  Book Translator - Build Script for Windows
REM ============================================================
REM  This script creates the .exe executable with all dependencies
REM ============================================================

echo.
echo ============================================================
echo   Book Translator - Build Script
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
if not exist "venv_build" (
    python -m venv venv_build
)

echo [2/4] Activating environment and installing dependencies...
call venv_build\Scripts\activate.bat

pip install --upgrade pip
pip install pyinstaller
pip install flaskwebgui
pip install flask flask-cors requests psutil werkzeug

echo [3/4] Creating executable with PyInstaller...
pyinstaller book_translator.spec --clean --noconfirm

echo [4/4] Cleaning temporary files...
rmdir /s /q build 2>nul

echo.
echo ============================================================
echo   BUILD COMPLETED!
echo ============================================================
echo.
echo   The executable is at:
echo   dist\BookTranslator\BookTranslator.exe
echo.
echo   To distribute, copy the entire folder:
echo   dist\BookTranslator\
echo.
echo ============================================================
echo.

pause

