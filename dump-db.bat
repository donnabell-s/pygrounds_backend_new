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
for /f "tokens=2 delims==." %%I in ('wmic os get localdatetime /value ^| find "="') do set DTS=%%I
set "STAMP=!DTS:~0,8!-!DTS:~8,6!"
set "OUT_FILE=%OUT_DIR%\%DB_NAME%_!STAMP!.dump"

REM ======= EXCLUSIONS ========
REM By default we exclude ONLY DATA for the users and user_learning apps,
REM so their tables are created (empty) to keep FK references valid.
set "EXCLUDE_MODE=DATA_ONLY"  REM change to SCHEMA_AND_DATA if you truly want nothing from these apps

set "EXCL_SWITCH=--exclude-table-data"
if /I "%EXCLUDE_MODE%"=="SCHEMA_AND_DATA" set "EXCL_SWITCH=--exclude-table"

echo.
echo [1/2] Preparing to dump database "%DB_NAME%" -> "%OUT_FILE%"
echo         Exclusion mode: %EXCLUDE_MODE% (users_*, user_learning_*)
echo.

REM Build exclusion args
set "EXCLUDES=%EXCL_SWITCH%=public.users_* %EXCL_SWITCH%=public.user_learning_*"

REM ======= RUN DUMP ========
echo [2/2] Running pg_dump...
set "PATH=%PG_BIN%;%PATH%"
"%PG_BIN%\pg_dump.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" ^
  -Fc -Z 9 --no-owner --no-privileges -v ^
  %EXCLUDES% ^
  -f "%OUT_FILE%"

if errorlevel 1 (
  echo.
  echo Dump FAILED. Please check connection details and permissions.
  exit /b 1
)

echo.
echo Dump complete: "%OUT_FILE%"
echo.
echo HINT: To include schemas for the excluded apps but no data, keep EXCLUDE_MODE=DATA_ONLY.
echo       To remove them entirely, set EXCLUDE_MODE=SCHEMA_AND_DATA (may break FK constraints).
echo.
pause
endlocal
