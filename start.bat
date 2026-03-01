@echo off
echo Starting ELA Avatar...
echo.

start "ELA Backend" cmd /k "cd /d C:\Users\pc\Desktop\avatar\backend && .\venv\Scripts\python.exe main.py"

timeout /t 2 /nobreak >nul

start "ELA Frontend" cmd /k "cd /d C:\Users\pc\Desktop\avatar && python -m http.server 3000"

echo.
echo Backend: http://localhost:8001
echo Frontend: http://localhost:3000
echo.
timeout /t 3 /nobreak >nul
start http://localhost:3000
