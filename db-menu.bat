@echo off
echo ================================================
echo   PYGROUNDS DATABASE CLEANUP - CHOOSE METHOD
echo ================================================
echo.
echo Choose what you want to do:
echo.
echo [1] COMPLETE RESET (Database + Migrations)
echo     - Drops database schema
echo     - Deletes all migration files
echo     - Use when: Fresh start needed
echo     - Result: Empty database, clean migrations
echo.
echo [2] MIGRATION RESET ONLY (Keep Database Data)
echo     - Keeps database intact
echo     - Deletes migration files only
echo     - Use when: Migrations messed up
echo     - Result: Keep data, fresh migrations
echo.
echo [3] RESTORE FROM BACKUP
echo     - Restores database from dump file
echo     - Use when: Restoring saved state
echo     - Result: Database with backed-up data
echo.
echo [4] EXIT
echo.
set /p choice="Enter choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo Running COMPLETE RESET...
    call cleanup-db.bat
    goto end
)

if "%choice%"=="2" (
    echo.
    echo Running MIGRATION RESET...
    call reset-migrations.bat
    goto end
)

if "%choice%"=="3" (
    echo.
    echo Running DATABASE RESTORE...
    call restore-db.bat
    goto end
)

if "%choice%"=="4" (
    echo Exiting...
    goto end
)

echo Invalid choice. Please run again and choose 1-4.
pause

:end
