@echo off
REM Quick database cleanup script for Windows
REM This resets all processing data while keeping uploaded PDFs

echo ===================================
echo   PYGROUNDS DATABASE CLEANUP
echo ===================================
echo.

echo Current database state:
python manage.py cleanup_database --help
echo.

echo Choose cleanup option:
echo 1. Clean processing data (keep uploaded PDFs)
echo 2. Clean specific document (enter ID)
echo 3. Full reset (DELETE EVERYTHING)
echo 4. Show current counts only
echo 5. Cancel

set /p choice="Enter choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Cleaning processing data while keeping uploaded PDFs...
    python manage.py cleanup_database --keep-documents
    echo.
    echo ✅ Cleanup completed! You can now restart TOC parsing and chunking.
) else if "%choice%"=="2" (
    set /p doc_id="Enter document ID to clean: "
    echo.
    echo Cleaning document %doc_id%...
    python manage.py cleanup_database --document-id %doc_id%
) else if "%choice%"=="3" (
    echo.
    echo ⚠️  WARNING: This will DELETE ALL DATA including uploaded PDFs!
    set /p confirm="Type 'DELETE' to confirm: "
    if "%confirm%"=="DELETE" (
        python manage.py cleanup_database --full-reset
        echo.
        echo ✅ Full reset completed!
    ) else (
        echo Cancelled - full reset not confirmed.
    )
) else if "%choice%"=="4" (
    echo.
    python manage.py shell -c "
from content_ingestion.models import *;
from question_generation.models import *;
print('📊 Current database counts:');
print(f'   - Documents: {UploadedDocument.objects.count()}');
print(f'   - TOC Entries: {TOCEntry.objects.count()}');
print(f'   - Chunks: {DocumentChunk.objects.count()}');
print(f'   - Game Zones: {GameZone.objects.count()}');
print(f'   - Topics: {Topic.objects.count()}');
print(f'   - Subtopics: {Subtopic.objects.count()}');
print(f'   - Generated Questions: {GeneratedQuestion.objects.count()}');
"
) else (
    echo Cancelled.
)

echo.
pause
