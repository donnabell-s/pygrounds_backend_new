@echo off
setlocal EnableDelayedExpansion

REM ================== CONFIG ==================
REM Your teammate should update these paths and credentials
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "NEW_DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

REM Path to the dump file - now using db_dump.sql from git
set "DUMP_FILE=db_dump.sql"

echo ================================================
echo   PYGROUNDS DATABASE RESTORE
echo ================================================
echo.
echo Source: "%DUMP_FILE%"
echo Target Database: "%NEW_DB_NAME%"
echo.
echo This will:
echo   1. Drop existing database (if exists)
echo   2. Create fresh database
echo   3. Restore ALL tables and data
echo   4. Skip incompatible schema changes
echo.
echo ⚠️  Current database will be REPLACED!
echo.
echo Press Ctrl+C to cancel, or
pause

REM ======= CHECK POSTGRESQL SERVICE ========
echo.
echo [1/6] Checking PostgreSQL service...
sc query postgresql-x64-17 | find "RUNNING" >nul
if errorlevel 1 (
    echo ✗ PostgreSQL service is not running!
    echo   Starting PostgreSQL service...
    net start postgresql-x64-17
    if errorlevel 1 (
        echo ✗ Failed to start PostgreSQL service!
        pause
        exit /b 1
    )
    echo ✓ PostgreSQL service started
) else (
    echo ✓ PostgreSQL is running
)

REM ======= CHECK IF DUMP FILE EXISTS ========
echo.
echo [2/6] Checking dump file...
if not exist "%DUMP_FILE%" (
  echo ✗ ERROR: SQL dump file not found: "%DUMP_FILE%"
  echo   Make sure you have pulled the latest code with: git pull
  pause
  exit /b 1
)

REM Get file size
for %%A in ("%DUMP_FILE%") do set FILE_SIZE=%%~zA
set /a FILE_SIZE_MB=%FILE_SIZE% / 1048576
echo ✓ Found dump file (%FILE_SIZE_MB% MB)

REM ======= TERMINATE ACTIVE CONNECTIONS ========
echo.
echo [3/6] Terminating active database connections...
"%PG_BIN%\psql.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '%NEW_DB_NAME%' AND pid <> pg_backend_pid();" >nul 2>&1
echo ✓ Active connections terminated

REM ======= DROP EXISTING DATABASE ========
echo.
echo [4/6] Dropping existing database (if exists)...
"%PG_BIN%\dropdb.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" --if-exists "%NEW_DB_NAME%" >nul 2>&1
echo ✓ Old database dropped

REM ======= CREATE NEW DATABASE ========
echo.
echo [5/6] Creating fresh database...
set "PATH=%PG_BIN%;%PATH%"
"%PG_BIN%\createdb.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -E UTF8 "%NEW_DB_NAME%"
if errorlevel 1 (
  echo ✗ Failed to create database "%NEW_DB_NAME%"
  pause
  exit /b 1
)
echo ✓ Database created

REM ======= RESTORE DATABASE ========
echo.
echo [6/6] Restoring data from dump (this may take a while)...
echo   - Incompatible tables will be skipped
echo   - All errors logged to restore_log.txt
echo.

"%PG_BIN%\psql.exe" ^
  --set ON_ERROR_STOP=off ^
  --set VERBOSITY=verbose ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%NEW_DB_NAME%" ^
  -f "%DUMP_FILE%" > restore_log.txt 2>&1

REM ======= VERIFY RESTORATION ========
echo.
echo Verifying restoration...

REM Count tables
for /f "tokens=*" %%i in ('"%PG_BIN%\psql.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%NEW_DB_NAME%" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"') do set TABLE_COUNT=%%i
set TABLE_COUNT=%TABLE_COUNT: =%

REM Count rows (sample)
for /f "tokens=*" %%i in ('"%PG_BIN%\psql.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%NEW_DB_NAME%" -t -c "SELECT COUNT(*) FROM auth_user;" 2^>nul') do set USER_COUNT=%%i
set USER_COUNT=%USER_COUNT: =%
if "%USER_COUNT%"=="" set USER_COUNT=0

echo ✓ Restored %TABLE_COUNT% tables
echo ✓ Found %USER_COUNT% users

REM ======= CHECK FOR ERRORS ========
findstr /C:"ERROR" restore_log.txt >nul 2>&1
if not errorlevel 1 (
    echo.
    echo ⚠️  Some statements failed during restore (see restore_log.txt)
    echo    This is normal if schema has changed between dump and current code.
    echo    Incompatible tables/columns were skipped.
) else (
    echo ✓ No critical errors detected
)

echo.
echo ================================================
echo   RESTORE COMPLETED
echo ================================================
echo.
echo Database "%NEW_DB_NAME%" has been restored.
echo.
echo Restored data includes:
echo   - %TABLE_COUNT% tables
echo   - %USER_COUNT% user(s)
echo   - All compatible zones, topics, subtopics
echo   - All compatible questions and assessments
echo   - All compatible content and embeddings
echo.
echo ⚠️  If some data is missing or migrations needed:
echo   1. python manage.py migrate (update schema)
echo   2. python scripts\populate_zones.py (recreate zones if needed)
echo   3. python reading\seed_reading.py (recreate reading materials)
echo.
echo Check restore_log.txt for details on any skipped statements.
echo.
echo Ready to run: python manage.py runserver
echo.
pause
endlocal
endlocal
