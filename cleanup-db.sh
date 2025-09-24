#!/usr/bin/env bash
set -euo pipefail

# Load from .env if present
if [ -f .env ]; then set -a; source .env; set +a; fi

# Default fallback values
: "${DB_NAME:=pygrounds_db}" "${DB_USER:=postgres}" "${DB_PASSWORD:=root}" "${DB_HOST:=localhost}" "${DB_PORT:=5432}"
export PGPASSWORD="$DB_PASSWORD"

echo "==================================="
echo "  PYGROUNDS DATABASE WIPE (Mac)"
echo "==================================="
echo "⚠️  This will DROP *ALL* tables in $DB_NAME!"
read -p "Press Enter to continue or Ctrl+C to cancel..."

echo
echo "[CLEANUP] Generating DROP statements into drop_commands.sql..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -At -c \
  "SELECT 'DROP TABLE IF EXISTS \"' || tablename || '\" CASCADE;' FROM pg_tables WHERE schemaname='public';" > drop_commands.sql

if [ ! -s drop_commands.sql ]; then
  echo "❌ Failed to generate drop_commands.sql or file is empty."
  exit 1
fi

echo
echo "[CLEANUP] Executing DROP statements..."
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q -f drop_commands.sql

echo "✅ All tables dropped successfully!"
rm drop_commands.sql

echo
echo "Next steps (if needed):"
echo "  python manage.py makemigrations"
echo "  python manage.py migrate"
echo "  python scripts/populate_zones.py"
echo "  python manage.py createsuperuser"
