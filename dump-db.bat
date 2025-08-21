@echo off
setlocal EnableDelayedExpansion

REM ================== CONFIG ==================
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

REM Output folder + timestamped filename
set "OUT_DIR=backups"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

REM Timestamp (YYYYMMDD-HHMMSS)
for /f "tokens=2 delims==." %%I in ('wmic os get localdatetime /value ^| find "="') do set DTS=%%I
set "STAMP=!DTS:~0,8!-!DTS:~8,6!"
set "OUT_FILE=%OUT_DIR%\%DB_NAME%_!STAMP!.dump"

REM ======= EXCLUSIONS ========
REM Default excludes ONLY DATA for these apps so schemas exist (empty) to keep FKs valid.
REM Change to SCHEMA_AND_DATA if you want them entirely omitted.
set "EXCLUDE_MODE=DATA_ONLY"  REM DATA_ONLY | SCHEMA_AND_DATA

set "EXCL_SWITCH=--exclude-table-data"
if /I "%EXCLUDE_MODE%"=="SCHEMA_AND_DATA" set "EXCL_SWITCH=--exclude-table"

REM Exclude users, user_learning, and minigames apps
set "EXCLUDES=%EXCL_SWITCH%=public.users_* %EXCL_SWITCH%=public.user_learning_* %EXCL_SWITCH%=public.minigames_*"

echo.
echo [1/2] Dumping "%DB_NAME%" to "%OUT_FILE%"
echo       Exclusion mode: %EXCLUDE_MODE% (users_*, user_learning_*, minigames_*)
echo.

REM ======= RUN DUMP ========
set "PATH=%PG_BIN%;%PATH%"
"%PG_BIN%\pg_dump.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" ^
  -Fc -Z 9 --no-owner --no-privileges -v ^
  %EXCLUDES% ^
  -f "%OUT_FILE%"

if errorlevel 1 (
  echo.
  echo Dump FAILED. Check connection/creds or pg_dump path.
  exit /b 1
)

echo.
echo ✅ Dump complete: "%OUT_FILE%"
echo (Excluded data/schemas per EXCLUDE_MODE for users_*, user_learning_*, minigames_*)
echo.
pause
endlocal
