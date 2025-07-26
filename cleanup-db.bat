@echo off
setlocal

REM Configure these paths
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

echo ===================================
echo   PYGROUNDS DATABASE CLEANUP
echo ===================================
echo This will DROP ALL TABLES in %DB_NAME%
echo.
echo ⚠️  WARNING: This will permanently delete:
echo    - All uploaded documents
echo    - All TOC entries
echo    - All document chunks
echo    - All game zones, topics, subtopics
echo    - All generated questions
echo    - All user data
echo.
echo Press Ctrl+C to cancel, or any key to continue...
pause

echo.
echo Dropping all tables and recreating schema...
"%PG_BIN%\psql.exe" -U %DB_USER% -d %DB_NAME% -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ Database cleaned successfully!
    echo.
    echo Now run these Django commands:
    echo   python manage.py makemigrations
    echo   python manage.py migrate
    echo   python manage.py createsuperuser
    echo.
) else (
    echo.
    echo ✗ Error cleaning database. Check your database connection.
    echo.
)

pause
