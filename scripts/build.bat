@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."

echo.
echo ============================================
echo  PhotoFlow AI - Production Build
echo ============================================
echo.

echo [0/3] Stopping old processes and cleaning...
taskkill /f /im photoflow-backend.exe >nul 2>&1
if exist "dist\photoflow-backend" (
    rmdir /s /q "dist\photoflow-backend"
)

echo [1/3] Building Python backend...
call pyinstaller photoflow-backend.spec --noconfirm --distpath dist
if %ERRORLEVEL% neq 0 (
    echo ERROR: PyInstaller build failed!
    exit /b 1
)
echo [1/3] Done - dist/photoflow-backend/

echo.
echo [2/3] Building React frontend...
cd /d "%SCRIPT_DIR%..\frontend"
call npm run build:react
if %ERRORLEVEL% neq 0 (
    echo ERROR: Vite build failed!
    exit /b 1
)
echo [2/3] Done - frontend/dist/

echo.
echo [3/3] Packaging Electron app...
call npx electron-builder --win
if %ERRORLEVEL% neq 0 (
    echo ERROR: electron-builder package failed!
    exit /b 1
)
echo [3/3] Done - frontend/release/

echo.
echo ============================================
echo  Build complete!
echo  Installer: frontend\release\PhotoFlow AI Setup *.exe
echo ============================================
