@echo off
REM ============================================================
REM  Book Translator - Build Script SINGLE EXE
REM ============================================================
REM  Creates a SINGLE .exe file with everything included
REM ============================================================

echo.
echo ============================================================
echo   Book Translator - Build SINGLE EXE
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

echo [3/4] Creating SINGLE executable with PyInstaller...
echo       (This may take several minutes...)
pyinstaller book_translator_onefile.spec --clean --noconfirm

echo [4/4] Cleaning temporary files...
rmdir /s /q build 2>nul

echo.
echo ============================================================
echo   BUILD COMPLETED!
echo ============================================================
echo.
echo   The executable is at:
echo   dist\BookTranslator.exe
echo.
echo   It's a SINGLE file that you can copy anywhere!
echo   (The .exe will create necessary folders when running)
echo.
echo ============================================================
echo.

pause
