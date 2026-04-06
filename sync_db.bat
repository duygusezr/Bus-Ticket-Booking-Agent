@echo off
echo ===== Railway DB Sync =====
echo.

set BASE_URL=https://bus-ticket-booking-agent-production.up.railway.app
set DB_DIR=backend\database

echo [1/2] Rezervasyonlar indiriliyor...
curl -o "%DB_DIR%\rezervasyonlar.db" "%BASE_URL%/api/db/download/rezervasyonlar"
echo.

echo [2/2] Bilet sistemi indiriliyor...
curl -o "%DB_DIR%\bilet_sistemi.db" "%BASE_URL%/api/db/download/bilet_sistemi"
echo.

echo ===== Sync tamamlandi! =====
echo Dosyalar: %DB_DIR%\
pause
