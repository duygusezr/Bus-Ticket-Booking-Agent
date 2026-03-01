@echo off
setlocal
set PROJECT_DIR=%~dp0
cd /d "%PROJECT_DIR%"

echo ==========================================
echo 🎭 ELA: Gerçek Zamanlı Avatar AI Başlatılıyor...
echo ==========================================
echo.

echo [1/2] Backend Başlatılıyor... (Port: 8001)
start "ELA Backend" cmd /k "cd /d "%PROJECT_DIR%backend" && .\venv\Scripts\python.exe main.py"

timeout /t 3 /nobreak >nul

echo [2/2] Frontend Başlatılıyor... (Port: 3000)
start "ELA Frontend" cmd /k "cd /d "%PROJECT_DIR%" && python -m http.server 3000"

echo.
echo 🚀 Tüm servisler hazır!
echo Backend:  http://localhost:8001
echo Frontend: http://localhost:3000
echo.
echo Tarayıcı açılıyor...
timeout /t 2 /nobreak >nul
start http://localhost:3000

pause
