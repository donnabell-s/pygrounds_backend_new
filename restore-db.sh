#!/bin/bash

# ================== CONFIG ==================
# Change this only if not using .env file
DB_HOST="localhost"
DB_PORT="5432"
NEW_DB_NAME="pygrounds_db"
DB_USER="postgres"
DB_PASSWORD="root"

# Optional: load from .env if available
if [ -f .env ]; then
  echo "[INFO] Loading environment variables from .env..."
  set -a
  source .env
  set +a
fi

DUMP_FILE="db_dump.sql"

echo
echo "[RESTORE] Restoring FULL database from SQL dump"
echo "Source: $DUMP_FILE"
echo "Target Database: $NEW_DB_NAME"
echo "This will restore ALL tables, data, users, progress, and content."
echo

# Check if dump file exists
if [ ! -f "$DUMP_FILE" ]; then
  echo "❌ ERROR: SQL dump file not found: $DUMP_FILE"
  echo "Make sure you have pulled the latest code with: git pull"
  exit 1
fi

# Confirm
read -p "⚠️  Are you sure you want to DROP and RESTORE '$NEW_DB_NAME'? (y/n): " confirm
if [[ "$confirm" != "y" ]]; then
  echo "Cancelled."
  exit 0
fi

# Create database
echo "Creating database '$NEW_DB_NAME'..."
PGPASSWORD="$DB_PASSWORD" createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$NEW_DB_NAME"

# Restore database
echo
echo "Restoring ALL data from SQL dump..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$NEW_DB_NAME" -f "$DUMP_FILE"

if [ $? -eq 0 ]; then
  echo
  echo "✅ Database restore complete!"
  echo "Database '$NEW_DB_NAME' now contains ALL data including:"
  echo "- All zones, topics, subtopics"
  echo "- All users and their progress"
  echo "- All questions and assessments"
  echo "- All content and embeddings"
  echo
  echo "You can now run: python manage.py runserver"
else
  echo
  echo "❌ Restore FAILED. Check DB credentials, Postgres installed, and file path."
  exit 1
fi
