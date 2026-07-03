@echo off
chcp 65001 >nul

echo ========================================
echo    Software Detector - Build Script
echo ========================================
echo.

echo [1/3] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

echo [2/3] Installing dependencies...
pip install pyinstaller pyzipper flask flask-cors -q

echo [3/3] Building EXE...
pyinstaller --onefile --windowed --name "SoftwareDetector" --clean installed_software_detector.py

if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build Complete!
echo Output: dist\SoftwareDetector.exe
echo ========================================
pause
