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

echo.
echo [RESTORE] Restoring FULL database from SQL dump
echo Source: "%DUMP_FILE%"
echo Target Database: "%NEW_DB_NAME%"
echo This will restore ALL tables, data, users, progress, and content.
echo.

REM Check if dump file exists
if not exist "%DUMP_FILE%" (
  echo ERROR: SQL dump file not found: "%DUMP_FILE%"
  echo Make sure you have pulled the latest code with: git pull
  pause
  exit /b 1
)

REM Create database first (optional - pg_restore can create it)
echo Creating database "%NEW_DB_NAME%"...
set "PATH=%PG_BIN%;%PATH%"
"%PG_BIN%\createdb.exe" -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" "%NEW_DB_NAME%"

REM Restore the database using psql instead of pg_restore
echo.
echo Restoring ALL data from SQL dump...
"%PG_BIN%\psql.exe" ^
  -h "%DB_HOST%" -p %DB_PORT% -U "%DB_USER%" -d "%NEW_DB_NAME%" ^
  -f "%DUMP_FILE%"

if errorlevel 1 (
  echo.
  echo Restore FAILED. Check connection/creds or file path.
  exit /b 1
)

echo.
echo ✅ Database restore complete!
echo Database "%NEW_DB_NAME%" now contains ALL data including:
echo - All zones, topics, subtopics
echo - All users and their progress
echo - All questions and assessments
echo - All content and embeddings
echo.
echo Your teammate can now run: python manage.py runserver
echo.
pause
endlocal
