@echo off
setlocal EnableDelayedExpansion

REM ================== CONFIG ==================
set "PG_BIN=C:\ Program Files\PostgreSQL\17\bin"
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

REM Path to the .dump file (custom format) produced by dump-db.bat
REM You can drag/drop the file onto this script or pass as the first arg
set "DUMP_FILE=%~1"
if "%DUMP_FILE%"=="" (
  for %%F in (*.dump) do (
    set "DUMP_FILE=%%~fF"
    goto :havefile
  )
  echo Usage: %~nx0 path\to\backup.dump
  echo Or place a single .dump file in this folder and re-run.
  exit /b 1
)
:havefile

if not exist "%DUMP_FILE%" (
  echo Dump file not found: "%DUMP_FILE%"
  exit /b 1
)

echo.
echo [1/4] Checking if database "%DB_NAME%" exists...
set "PATH=%PG_BIN%;%PATH%"
"%PG_BIN%\psql.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -tAc "SELECT 1 FROM pg_database WHERE datname='%DB_NAME%';" | find "1" >nul
IF errorlevel 1 (
  echo [2/4] Creating database "%DB_NAME%"...
  "%PG_BIN%\createdb.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" "%DB_NAME%"
  if errorlevel 1 (
    echo Failed to create database.
    exit /b 1
  )
) else (
  echo Database exists.
)

echo.
echo [3/4] Restoring "%DUMP_FILE%" into "%DB_NAME%"...
REM --clean drops objects that are in the dump before recreating them.
REM If you kept EXCLUDE_MODE=DATA_ONLY during dump, the excluded tables will
REM exist (empty) after restore, keeping FKs intact.
"%PG_BIN%\pg_restore.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" ^
  --clean --if-exists --no-owner --no-privileges -v "%DUMP_FILE%"

if errorlevel 1 (
  echo.
  echo Restore FAILED. If errors reference missing tables like users_*:
  echo   - Recreate the dump with EXCLUDE_MODE=DATA_ONLY (recommended), or
  echo   - Ensure those apps exist in the target DB before restore.
  exit /b 1
)

echo.
echo [4/4] Restore complete.
echo.
pause
endlocal
