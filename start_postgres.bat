@echo off
:: PostgreSQL sunucusunu başlat (bilgisayar açılışında otomatik)
start /B "" "C:\PostgreSQL\bin\pg_ctl.exe" -D "C:\PostgreSQL\data" -l "C:\PostgreSQL\log.txt" start
