#!/bin/zsh
set -e

DB_NAME="pygrounds_db"
DB_USER="postgres"

echo "==============================================="
echo "      PYGROUNDS DATABASE COMPLETE RESET"
echo "==============================================="
echo "⚠️  WARNING: This will DELETE ALL DATA!"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo
read -k1 "REPLY?Press ENTER to continue or Ctrl+C to cancel..."

echo
echo "[1/6] Deleting migration files..."
for app in achievements analytics content_ingestion minigames question_generation reading user_learning users; do
    if [ -d "$app/migrations" ]; then
        echo "  Cleaning $app/migrations..."
        find "$app/migrations" -type f -name "*.py" ! -name "__init__.py" -delete
        rm -rf "$app/migrations/__pycache__"
    fi
done
echo "✓ Migration files deleted"

echo
echo "[2/6] Dropping and recreating schema..."
psql -U $DB_USER -d $DB_NAME -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO $DB_USER; GRANT ALL ON SCHEMA public TO public;"
echo "✓ Schema recreated"

echo
echo "[3/6] Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
echo "✓ Python cache cleaned"

echo
echo "==============================================="
echo "   CLEANUP COMPLETED SUCCESSFULLY"
echo "==============================================="

echo "Next steps:"
echo "  python manage.py makemigrations"
echo "  python manage.py migrate"
echo "  python scripts/populate_zones.py"
echo "  python reading/seed_reading.py"
echo "  python manage.py createsuperuser"
