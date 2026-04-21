@echo off
chcp 65001 >nul
setlocal
set PROJECT_DIR=%~dp0
cd /d "%PROJECT_DIR%"

echo ==========================================
echo Avatar: Gercek Zamanli Avatar AI Baslatiliyor...
echo ==========================================
echo.
echo Bu pencereyi kapatmayin.

:: Backend'i ayri pencerede baslat
start "Avatar Backend" cmd /k "chcp 65001 >nul && cd /d "%PROJECT_DIR%backend" && .\venv\Scripts\python.exe main.py"

:: Frontend'i ayri pencerede baslat
start "Avatar Frontend" cmd /k "cd /d "%PROJECT_DIR%frontend" && python -m http.server 3000"

echo.
echo Tum servisler hazir!
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:3000
echo.
echo Tarayici aciliyor...
timeout /t 2 /nobreak >nul
start http://localhost:3000

pause
