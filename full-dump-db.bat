@echo off
setlocal EnableDelayedExpansion

REM ================== CONFIG ==================
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_HOST=localhost"
set "DB_PORT=5432"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"

REM Output to db_dump.sql in project root for git
set "OUT_FILE=db_dump.sql"

REM Delete existing dump file to ensure fresh data
if exist "%OUT_FILE%" (
    echo Deleting existing "%OUT_FILE%" to ensure fresh data...
    del "%OUT_FILE%"
)

echo.
echo [FULL DUMP] Creating fresh database dump with current data
echo Database: "%DB_NAME%"
echo Output: "%OUT_FILE%" (for git push)
echo.

REM ======= CHECK POSTGRESQL SERVICE ========
echo [1/4] Checking PostgreSQL service...
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

REM ======= CHECK DATABASE CONNECTION ========
echo.
echo [2/4] Testing database connection...
"%PG_BIN%\psql.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" -c "SELECT 1;" >nul 2>&1
if errorlevel 1 (
    echo ✗ Cannot connect to database "%DB_NAME%"
    echo   Please check:
    echo   - Database exists
    echo   - Username/password are correct
    echo   - PostgreSQL is running
    pause
    exit /b 1
)
echo ✓ Database connection successful

REM ======= COUNT TABLES ========
echo.
echo [3/4] Analyzing database...
for /f "tokens=*" %%i in ('"%PG_BIN%\psql.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';"') do set TABLE_COUNT=%%i
set TABLE_COUNT=%TABLE_COUNT: =%
echo ✓ Found %TABLE_COUNT% tables to backup

REM ======= RUN FULL DUMP ========
echo.
echo [4/4] Creating database dump...
set "PATH=%PG_BIN%;%PATH%"
"%PG_BIN%\pg_dump.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%DB_NAME%" ^
  --format=plain ^
  --no-owner ^
  --no-privileges ^
  --clean ^
  --if-exists ^
  --create ^
  --column-inserts ^
  --encoding=UTF8 ^
  -v ^
  -f "%OUT_FILE%"

if errorlevel 1 (
  echo.
  echo ✗ Dump FAILED. Check connection/creds or pg_dump path.
  pause
  exit /b 1
)

echo.
echo ✅ Fresh dump complete: "%OUT_FILE%"
echo Old dump file was deleted and replaced with current database data.
echo This SQL file is ready to be committed to git.
echo.
echo Your teammate can restore using:
echo psql -h localhost -p 5432 -U postgres -d new_database_name -f db_dump.sql
echo.
echo Next steps:
echo 1. git add db_dump.sql
echo 2. git commit -m "Update database dump with latest data"
echo 3. git push
echo.
echo Use the restore-db.bat script to restore from this dump.
pause
endlocal
