@echo off
setlocal enabledelayedexpansion

REM === CONFIGURATION ===
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

echo ================================================
echo   PYGROUNDS DATABASE COMPLETE RESET
echo ================================================
echo.
echo ⚠️  WARNING: This will:
echo   1. Drop and recreate the database schema
echo   2. Delete ALL migration files (except __init__.py)
echo   3. Reset migration history completely
echo.
echo ⚠️  ALL DATA WILL BE LOST!
echo.
echo Database: %DB_NAME%
echo User: %DB_USER%
echo.
echo Press Ctrl+C to cancel, or
pause

REM === Check if PostgreSQL is running ===
echo.
echo [1/7] Checking PostgreSQL service...
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

REM === Check if psql.exe exists ===
echo.
echo [2/7] Checking PostgreSQL binaries...
if not exist "%PG_BIN%\psql.exe" (
    echo ✗ Error: psql.exe not found at "%PG_BIN%"
    echo   Please update the PG_BIN path in this script
    pause
    exit /b 1
)
echo ✓ PostgreSQL binaries found

REM === Test database connection ===
echo.
echo [3/7] Testing database connection...
"%PG_BIN%\psql.exe" -U %DB_USER% -d %DB_NAME% -c "SELECT 1;" >nul 2>&1
if errorlevel 1 (
    echo ✗ Cannot connect to database %DB_NAME%
    echo   Please check:
    echo   - Database exists
    echo   - Username/password are correct
    echo   - PostgreSQL is running
    pause
    exit /b 1
)
echo ✓ Database connection successful

REM === Delete all migration files except __init__.py ===
echo.
echo [4/7] Deleting migration files...
for /d %%d in (achievements analytics content_ingestion minigames question_generation reading user_learning users) do (
    if exist "%%d\migrations\" (
        echo   Cleaning %%d\migrations\...
        for %%f in ("%%d\migrations\*.py") do (
            if not "%%~nxf"=="__init__.py" (
                del "%%f" >nul 2>&1
            )
        )
        REM Also delete __pycache__ in migrations
        if exist "%%d\migrations\__pycache__\" (
            rd /s /q "%%d\migrations\__pycache__" >nul 2>&1
        )
    )
)
echo ✓ Migration files deleted

REM === Drop all connections to the database ===
echo.
echo [5/7] Terminating active database connections...
"%PG_BIN%\psql.exe" -U %DB_USER% -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '%DB_NAME%' AND pid <> pg_backend_pid();" >nul 2>&1
echo ✓ Active connections terminated

REM === Drop and recreate public schema ===
echo.
echo [6/7] Dropping and recreating public schema...
"%PG_BIN%\psql.exe" -U %DB_USER% -d %DB_NAME% -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO %DB_USER%; GRANT ALL ON SCHEMA public TO public;"

if errorlevel 1 (
    echo ✗ Error dropping/recreating schema!
    echo   Check PostgreSQL logs for details
    pause
    exit /b 1
)
echo ✓ Schema reset successfully

REM === Clean Python cache files ===
echo.
echo [7/7] Cleaning Python cache files...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" >nul 2>&1
for /r %%f in (*.pyc) do @if exist "%%f" del /q "%%f" >nul 2>&1
echo ✓ Python cache cleaned

echo.
echo ================================================
echo   CLEANUP COMPLETED SUCCESSFULLY
echo ================================================
echo.
echo Your database and migrations are now completely reset.
echo.
echo Next steps:
echo   1. python manage.py makemigrations
echo   2. python manage.py migrate
echo   3. python scripts\populate_zones.py
echo   4. python reading\seed_reading.py
echo   5. python manage.py createsuperuser
echo.
echo Alternative: To restore from backup instead:
echo   restore-db.bat
echo.
pause