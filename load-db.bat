@echo off
setlocal EnableDelayedExpansion

REM ================== CONFIG ==================
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

REM ====== PICK DUMP FILE (arg or newest in backups\ then current folder) ======
set "DUMP_FILE=%~1"
if "%DUMP_FILE%"=="" (
  if exist "backups\" (
    for /f "delims=" %%F in ('dir /b /a:-d /o:-d "backups\*.dump" 2^>nul') do (
      set "DUMP_FILE=backups\%%F"
      goto :havefile
    )
  )
  for /f "delims=" %%F in ('dir /b /a:-d /o:-d "*.dump" 2^>nul') do (
    set "DUMP_FILE=%%F"
    goto :havefile
  )
  echo No dump file specified and none found in "backups\" or current folder.
  echo Usage: %~nx0 path\to\backup.dump
  exit /b 1
)
:havefile

if not exist "%DUMP_FILE%" (
  echo Dump file not found: "%DUMP_FILE%"
  exit /b 1
)

echo.
echo Using dump: "%DUMP_FILE%"
set "PATH=%PG_BIN%;%PATH%"

REM ====== VERIFY TOOLS EXIST ======
where pg_restore.exe >nul 2>&1
if errorlevel 1 (
  echo pg_restore.exe not found on PATH. Check PG_BIN: "%PG_BIN%"
  exit /b 1
)
where psql.exe >nul 2>&1
if errorlevel 1 (
  echo psql.exe not found on PATH. Check PG_BIN: "%PG_BIN%"
  exit /b 1
)

REM ====== ENSURE DB EXISTS ======
echo.
echo [1/3] Checking database "%DB_NAME%"...
"%PG_BIN%\psql.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -tAc "SELECT 1 FROM pg_database WHERE datname='%DB_NAME%';" | find "1" >nul
if errorlevel 1 (
  echo [2/3] Creating database "%DB_NAME%"...
  "%PG_BIN%\createdb.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" "%DB_NAME%"
  if errorlevel 1 (
    echo Failed to create database. Check credentials and server status.
    exit /b 1
  )
) else (
  echo Database exists.
)

REM ====== RESTORE ======
echo.
echo [3/3] Restoring into "%DB_NAME%"...
"%PG_BIN%\pg_restore.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" ^
  --clean --if-exists --no-owner --no-privileges -v ^
  "%DUMP_FILE%"
if errorlevel 1 (
  echo.
  echo Restore FAILED. Common causes:
  echo  - Wrong credentials (DB_USER/PGPASSWORD)
  echo  - Dump created with different major Postgres version
  echo  - Excluded tables referenced by FKs (switch dump to DATA_ONLY mode)
  exit /b 1
)

echo.
echo ✅ Restore complete.
endlocal
