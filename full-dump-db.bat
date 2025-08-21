@echo off
setlocal EnableDelayedExpansion

REM ================== CONFIG ==================
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

REM Output to db_dump.sql in project root for git
set "OUT_FILE=db_dump.sql"

REM Delete existing dump file to ensure fresh data
if exist "%OUT_FILE%" (
    echo Deleting existing "%OUT_FILE%" to ensure fresh data...
    del "%OUT_FILE%"
)

echo.
echo [FULL DUMP] Creating fresh database dump with current data
echo Database: "%DB_NAME%"
echo Output: "%OUT_FILE%" (for git push)
echo.

REM ======= RUN FULL DUMP ========
set "PATH=%PG_BIN%;%PATH%"
"%PG_BIN%\pg_dump.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" ^
  --no-owner --no-privileges -v ^
  -f "%OUT_FILE%"

if errorlevel 1 (
  echo.
  echo Dump FAILED. Check connection/creds or pg_dump path.
  exit /b 1
)

echo.
echo ✅ Fresh dump complete: "%OUT_FILE%"
echo Old dump file was deleted and replaced with current database data.
echo This SQL file is ready to be committed to git.
echo.
echo Your teammate can restore using:
echo psql -h localhost -p 5432 -U postgres -d new_database_name -f db_dump.sql
echo.
echo Next steps:
echo 1. git add db_dump.sql
echo 2. git commit -m "Update database dump with latest data"
echo 3. git push
echo.
pause
endlocal
