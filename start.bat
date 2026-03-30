@echo off
chcp 65001 >nul
setlocal
set PROJECT_DIR=%~dp0
cd /d "%PROJECT_DIR%"

echo ==========================================
echo ELA: Gercek Zamanli Avatar AI Baslatiliyor...
echo ==========================================
echo.

echo [1/2] Backend baslatiliyor... (Port: 8001)
start "ELA Backend" cmd /k "chcp 65001 >nul && cd /d "%PROJECT_DIR%backend" && .\venv\Scripts\python.exe main.py"

timeout /t 3 /nobreak >nul

echo [2/2] Frontend baslatiliyor... (Port: 3000)
start "ELA Frontend" cmd /k "cd /d "%PROJECT_DIR%" && python -m http.server 3000"

echo.
echo Tum servisler hazir!
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:3000
echo.
echo Tarayici aciliyor...
timeout /t 2 /nobreak >nul
start http://localhost:3000

pause
