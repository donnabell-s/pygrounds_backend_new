@echo off
setlocal

REM === CONFIGURATION ===
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"  REM ← Replace with your actual password

REM === Create the database if it doesn't exist ===
echo.
echo Checking if database "%DB_NAME%" exists...
"%PG_BIN%\psql.exe" -U %DB_USER% -c "SELECT 1 FROM pg_database WHERE datname='%DB_NAME%';" | find "1" >nul
IF %ERRORLEVEL% NEQ 0 (
    echo Database not found. Creating "%DB_NAME%"...
    "%PG_BIN%\createdb.exe" -U %DB_USER% %DB_NAME%
) ELSE (
    echo Database "%DB_NAME%" already exists.
)

REM === Load the dump file ===
echo.
echo Importing db_dump.sql into "%DB_NAME%"...
"%PG_BIN%\psql.exe" -U %DB_USER% -d %DB_NAME% -f db_dump.sql

IF %ERRORLEVEL% EQU 0 (
    echo Database import successful!
) ELSE (
    echo Error during import. Please check credentials or db_dump.sql.
)

pause
endlocal
