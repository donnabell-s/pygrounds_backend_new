@echo off
setlocal enabledelayedexpansion

echo ================================================
echo   DJANGO MIGRATIONS RESET (FILES ONLY)
echo ================================================
echo.
echo This will delete all migration files (except __init__.py)
echo without touching the database.
echo.
echo ⚠️  Use this when migrations are messed up but you want
echo    to keep your database data intact.
echo.
echo Press Ctrl+C to cancel, or
pause

echo.
echo [1/3] Deleting migration files...
set "DELETED_COUNT=0"

for /d %%d in (achievements analytics content_ingestion minigames question_generation reading user_learning users) do (
    if exist "%%d\migrations\" (
        echo   Cleaning %%d\migrations\...
        for %%f in ("%%d\migrations\*.py") do (
            if not "%%~nxf"=="__init__.py" (
                echo     Deleting %%~nxf...
                del "%%f" >nul 2>&1
                set /a DELETED_COUNT+=1
            )
        )
        REM Delete migration __pycache__
        if exist "%%d\migrations\__pycache__\" (
            rd /s /q "%%d\migrations\__pycache__" >nul 2>&1
        )
    )
)
echo ✓ Deleted %DELETED_COUNT% migration files

echo.
echo [2/3] Cleaning Python cache files...
for /d /r %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" >nul 2>&1
for /r %%f in (*.pyc) do @if exist "%%f" del /q "%%f" >nul 2>&1
echo ✓ Python cache cleaned

echo.
echo [3/3] Verifying __init__.py files exist...
for /d %%d in (achievements analytics content_ingestion minigames question_generation reading user_learning users) do (
    if exist "%%d\migrations\" (
        if not exist "%%d\migrations\__init__.py" (
            echo   Creating %%d\migrations\__init__.py
            type nul > "%%d\migrations\__init__.py"
        )
    )
)
echo ✓ All __init__.py files verified

echo.
echo ================================================
echo   MIGRATION RESET COMPLETED
echo ================================================
echo.
echo Migration files have been deleted.
echo.
echo Next steps:
echo   1. python manage.py makemigrations
echo   2. python manage.py migrate --fake-initial (if keeping database data)
echo.
echo OR if you want a completely fresh start:
echo   1. Run cleanup-db.bat (wipes database + migrations)
echo   2. python manage.py makemigrations
echo   3. python manage.py migrate
echo.
pause
