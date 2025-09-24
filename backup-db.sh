set -euo pipefail

OUT_FILE="${1:-db_dump.sql}"

if [ -f .env ]; then set -a; source .env; set +a; fi
: "${DB_NAME:=pygrounds_db}"
: "${DB_USER:=pygrounds_user}"
: "${DB_PASSWORD:=root}"
: "${DB_HOST:=localhost}"
: "${DB_PORT:=5432}"

export PGPASSWORD="$DB_PASSWORD"

echo "[BACKUP] Exporting $DB_NAME to $OUT_FILE..."
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
  --no-owner --no-privileges --format=p --verbose \
  "$DB_NAME" > "$OUT_FILE"
echo "✅ Wrote $OUT_FILE"
