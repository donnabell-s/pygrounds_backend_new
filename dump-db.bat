@echo off
setlocal

REM Configure these paths
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

echo Dumping database to db_dump.sql...
"%PG_BIN%\pg_dump.exe" -U %DB_USER% -d %DB_NAME% -f db_dump.sql

echo Done!
pause
