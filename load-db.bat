@echo off
setlocal EnableDelayedExpansion

REM ================== CONFIG ==================
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

REM Accept path to .dump as first arg, otherwise auto-pick newest in backups\
set "DUMP_FILE=%~1"
if "%DUMP_FILE%"=="" (
  for /f "delims=" %%F in ('dir /b /a:-d /o:-d "backups\*.dump" 2^>nul') do (
    set "DUMP_FILE=backups\%%F"
    goto :havefile
  )
  for /f "delims=" %%F in ('dir /b /a:-d /o:-d "*.dump" 2^>nul') do (
    set "DUMP_FILE=%%F"
    goto :havefile
  )
  echo Usage: %~nx0 path\to\backup.dump
  echo Or place a .dump in "backups\" (newest will be used automatically).
  exit /b 1
)
:havefile

if not exist "%DUMP_FILE%" (
  echo Dump file not found: "%DUMP_FILE%"
  exit /b 1
)

echo.
echo [1/4] Checking database "%DB_NAME%" existence...
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
"%PG_BIN%\pg_restore.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" ^
  --clean --if-exists --no-owner --no-privileges -v ^
  "%DUMP_FILE%"

if errorlevel 1 (
  echo.
  echo Restore FAILED.
  echo If errors mention missing users_*, user_learning_*, or minigames_* tables:
  echo   - Recreate the dump with EXCLUDE_MODE=DATA_ONLY (recommended), or
  echo   - Ensure those apps/tables exist in target (schemas present).
  exit /b 1
)

echo.
echo [4/4] ✅ Restore complete.
echo.
pause
endlocal
