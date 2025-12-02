#!/bin/zsh
set -e

echo "==============================================="
echo "      DJANGO MIGRATIONS RESET (FILES ONLY)"
echo "==============================================="
echo "This will DELETE migration files but KEEP data."
echo
read -k1 "REPLY?Press ENTER to continue or Ctrl+C to cancel..."

echo
echo "[1/3] Deleting migration files..."
for app in achievements analytics content_ingestion minigames question_generation reading user_learning users; do
    if [ -d "$app/migrations" ]; then
        echo "  Cleaning $app/migrations..."
        find "$app/migrations" -type f -name "*.py" ! -name "__init__.py" -delete
        rm -rf "$app/migrations/__pycache__"
    fi
done
echo "✓ Migration files deleted"

echo
echo "[2/3] Cleaning Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
echo "✓ Cache cleaned"

echo
echo "[3/3] Ensuring __init__.py exists..."
for app in achievements analytics content_ingestion minigames question_generation reading user_learning users; do
    mkdir -p "$app/migrations"
    touch "$app/migrations/__init__.py"
done
echo "✓ __init__.py files verified"

echo
echo "Migration reset complete!"
echo "Next:"
echo "  python manage.py makemigrations"
echo "  python manage.py migrate --fake-initial"
