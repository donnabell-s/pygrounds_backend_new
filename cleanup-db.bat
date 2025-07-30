@echo off
setlocal

REM === CONFIGURATION ===
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

echo ===================================
echo   PYGROUNDS DATABASE WIPE
echo ===================================
echo ⚠️  This will DROP *ALL* tables in %DB_NAME%!
echo Press Ctrl+C to cancel, or any key to continue...
pause >nul

echo.
echo Generating DROP statements into drop_commands.sql...
"%PG_BIN%\psql.exe" -U %DB_USER% -d %DB_NAME% -At -c ^
  "SELECT 'DROP TABLE IF EXISTS public.' || quote_ident(tablename) || ' CASCADE;' FROM pg_tables WHERE schemaname='public';" > drop_commands.sql

if not exist drop_commands.sql (
    echo ✗ Failed to write drop_commands.sql
    pause
    exit /b 1
)

echo.
echo Executing DROP statements...
"%PG_BIN%\psql.exe" -U %DB_USER% -d %DB_NAME% -q -f drop_commands.sql
if errorlevel 1 (
    echo ✗ Error running drop_commands.sql
    echo See drop_commands.sql for details.
    pause
    exit /b 1
)

echo ✓ All tables dropped successfully!
del drop_commands.sql

echo.
echo Next steps:
echo   python manage.py makemigrations
echo   python manage.py migrate
echo   python scripts\populate_zones.py
echo   python manage.py createsuperuser

pause
