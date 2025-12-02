#!/bin/zsh
set -e

DB_NAME="pygrounds_db"
DB_USER="postgres"
OUT_FILE="db_dump.sql"

echo "==============================================="
echo "       FULL DATABASE DUMP (macOS VERSION)"
echo "==============================================="

echo "Deleting old dump (if exists)..."
rm -f "$OUT_FILE"

echo
echo "[1/3] Checking DB connection..."
psql -U $DB_USER -d $DB_NAME -c "SELECT 1;" >/dev/null
echo "✓ Connection OK"

echo
echo "[2/3] Counting tables..."
TABLES=$(psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d ' ')
echo "✓ Found $TABLES tables"

echo
echo "[3/3] Creating FULL dump..."
pg_dump -U $DB_USER -d $DB_NAME \
  --format=plain \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists \
  --create \
  --column-inserts \
  --encoding=UTF8 \
  -f "$OUT_FILE"

echo
echo "==============================================="
echo "      ✓ FULL DUMP SUCCESSFULLY CREATED"
echo "==============================================="
echo "Output: $OUT_FILE"
echo "This file can now be committed to git."
