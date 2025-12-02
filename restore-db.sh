#!/bin/zsh
set -e

DB_NAME="pygrounds_db"
DB_USER="postgres"
DUMP_FILE="db_dump.sql"

echo "==============================================="
echo "      PYGROUNDS DATABASE RESTORE (macOS)"
echo "==============================================="
echo "Source: $DUMP_FILE"
echo "Target: $DB_NAME"
echo
read -k1 "REPLY?Press ENTER to continue or Ctrl+C to cancel..."

echo
echo "[1/6] Checking dump..."
if [ ! -f "$DUMP_FILE" ]; then
    echo "❌ ERROR: db_dump.sql not found!"
    exit 1
fi
echo "✓ Dump file exists"

echo
echo "[2/6] Terminating active connections..."
psql -U $DB_USER -d postgres -c \
"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME';"
echo "✓ Connections terminated"

echo
echo "[3/6] Dropping database..."
dropdb -U $DB_USER --if-exists $DB_NAME
echo "✓ Dropped"

echo
echo "[4/6] Creating new database..."
createdb -U $DB_USER -E UTF8 $DB_NAME
echo "✓ Created"

echo
echo "[5/6] Restoring dump..."
psql -U $DB_USER -d $DB_NAME < "$DUMP_FILE" 2> restore_log.txt
echo "✓ Restore complete (check restore_log.txt for warnings)"

echo
echo "[6/6] Verifying..."
TABLES=$(psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d ' ')
echo "✓ Restored $TABLES tables"


echo
echo "==============================================="
echo "   RESTORE COMPLETE — NOW APPLYING FIXES"
echo "==============================================="

# ---------------------------------------------------------
# FIX 1: Drop old reading tables
# ---------------------------------------------------------
echo "[Fix 1] Dropping old/invalid reading tables..."
psql -U $DB_USER -d $DB_NAME <<EOF
DROP TABLE IF EXISTS reading_topic CASCADE;
DROP TABLE IF EXISTS reading_subtopic CASCADE;
DROP TABLE IF EXISTS reading_readingmaterial CASCADE;
EOF
echo "✓ Old reading tables removed"


# ---------------------------------------------------------
# FIX 2: Re-grant permissions BEFORE running migrations
# ---------------------------------------------------------
echo "[Fix 2] Re-granting permissions to pygrounds_user..."
psql -U $DB_USER -d $DB_NAME <<EOF
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO pygrounds_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pygrounds_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pygrounds_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT ALL ON TABLES TO pygrounds_user;
EOF
echo "✓ Permissions OK — Django can now migrate"


# ---------------------------------------------------------
# FIX 3: Recreate reading schema
# ---------------------------------------------------------
echo "[Fix 3] Running Django migration for reading..."
python manage.py migrate reading --noinput
echo "✓ Reading schema recreated"


# ---------------------------------------------------------
# FIX 4: Run reading seeder
# ---------------------------------------------------------
echo "[Fix 4] Running reading seeder..."
python manage.py shell <<EOF
exec(open('reading/seed_reading.py').read())
EOF
echo "✓ Reading materials inserted"


# ---------------------------------------------------------
# FIX 5: Final safety permissions
# ---------------------------------------------------------
echo "[Fix 5] Finalizing permissions..."
psql -U $DB_USER -d $DB_NAME <<EOF
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pygrounds_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pygrounds_user;
EOF
echo "✓ Permissions finalized"


echo
echo "==============================================="
echo "   RESTORE + READING MATERIAL FIX COMPLETE!"
echo "==============================================="
