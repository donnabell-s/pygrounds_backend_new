# Database Cleanup Scripts Guide

## Scripts Overview

### 1. `cleanup-db.bat` - **COMPLETE RESET** 🔥
**Use when:** You need a completely fresh start

**What it does:**
- ✓ Drops and recreates database schema
- ✓ Deletes ALL migration files (except `__init__.py`)
- ✓ Cleans Python cache files
- ✓ Terminates active database connections
- ✓ Resets migration history completely

**After running:**
```bash
python manage.py makemigrations
python manage.py migrate
python scripts\populate_zones.py
python reading\seed_reading.py
python manage.py createsuperuser
```

**⚠️ WARNING:** All data will be lost!

---

### 2. `reset-migrations.bat` - **MIGRATION RESET ONLY** 🔧
**Use when:** Your migrations are messed up but you want to keep database data

**What it does:**
- ✓ Deletes migration files (keeps `__init__.py`)
- ✓ Cleans Python cache
- ✓ Keeps database data intact

**After running:**
```bash
python manage.py makemigrations
python manage.py migrate --fake-initial
```

**Note:** Database data is preserved!

---

### 3. `restore-db.bat` - **RESTORE FROM BACKUP** 💾
**Use when:** Restoring from a previous database dump

**What it does:**
- ✓ Checks PostgreSQL service
- ✓ Terminates active connections
- ✓ Drops existing database completely
- ✓ Creates fresh database
- ✓ Restores all data and schema from dump
- ✓ **Skips incompatible tables/fields** (error tolerance)
- ✓ Logs all errors to `restore_log.txt`
- ✓ Verifies restoration success

**After running:**
```bash
python manage.py migrate  # If schema changed
python manage.py runserver
```

**Note:** Incompatible schema changes are automatically skipped!

---

### 3b. `full-dump-db.bat` - **CREATE BACKUP** 💾
**Use when:** Creating a database backup before changes

**What it does:**
- ✓ Checks PostgreSQL service and connection
- ✓ Counts tables to backup
- ✓ Creates complete SQL dump with all data
- ✓ Uses `--column-inserts` for maximum compatibility
- ✓ Uses `--clean --if-exists` for safe restoration
- ✓ Deletes old dump file first (ensures fresh data)

**Backup options:**
```bash
full-dump-db.bat
```

**Dump file contents:**
- ✓ All table structures (CREATE TABLE statements)
- ✓ All data (INSERT statements with column names)
- ✓ All sequences and indexes
- ✓ DROP IF EXISTS statements (safe restoration)

**Note:** Dump is saved to `db_dump.sql` for git commits

---

### 4. `db-menu.bat` - **INTERACTIVE MENU** 📋
**Use when:** You want to choose interactively

**What it does:**
- Shows all options
- Runs the selected script

---

## Common Scenarios

### Scenario 1: "My migrations won't run / keep failing"
**Solution:** Use `cleanup-db.bat` for complete reset
```bash
cleanup-db.bat
python manage.py makemigrations
python manage.py migrate
```

### Scenario 2: "I have conflicting migration files"
**Solution:** Use `reset-migrations.bat` to clean migrations only
```bash
reset-migrations.bat
python manage.py makemigrations
python manage.py migrate --fake-initial
```

### Scenario 3: "I want to start with backed-up data"
**Solution:** Use `restore-db.bat`
```bash
restore-db.bat
```

### Scenario 4: "I added a new model and migrations are messy"
**Solution:** Use `cleanup-db.bat` for fresh migrations
```bash
cleanup-db.bat
python manage.py makemigrations
python manage.py migrate
python scripts\populate_zones.py
```

### Scenario 5: "Database is fine, just migrations are broken"
**Solution:** Use `reset-migrations.bat`
```bash
reset-migrations.bat
python manage.py makemigrations
python manage.py migrate --fake-initial
```

---

## Migration Best Practices

### Before Running Migrations
1. **Backup your database:**
   ```bash
   full-dump-db.bat
   ```

2. **Delete Python cache:**
   ```bash
   for /d /r %d in (__pycache__) do @if exist "%d" rd /s /q "%d"
   ```

### After Adding New Models
1. Run `cleanup-db.bat` for cleanest state
2. Or use `reset-migrations.bat` if keeping data
3. Always run `makemigrations` before `migrate`

### If Migrations Fail
1. Check error message for circular dependencies
2. Use `cleanup-db.bat` to reset completely
3. Ensure all apps are in `INSTALLED_APPS`

---

## Quick Reference

| Task | Script | Data Loss | Migration Reset |
|------|--------|-----------|-----------------|
| Fresh start | `cleanup-db.bat` | ✓ Yes | ✓ Yes |
| Fix migrations only | `reset-migrations.bat` | ✗ No | ✓ Yes |
| Restore backup | `restore-db.bat` | ✓ Yes | ✗ No |
| Choose interactively | `db-menu.bat` | Depends | Depends |

---

## Backup & Restore Workflow

### Creating a Backup
```bash
# Before making schema changes
full-dump-db.bat

# Commit to git
git add db_dump.sql
git commit -m "Backup database before schema changes"
git push
```

### Restoring a Backup
```bash
# Pull latest backup
git pull

# Restore database
restore-db.bat

# Run migrations if schema changed
python manage.py migrate
```

### Handling Schema Mismatches

When restoring a backup with different schema:

1. **Restore will skip incompatible statements** automatically
2. Check `restore_log.txt` for details on skipped items
3. Run migrations to update schema: `python manage.py migrate`
4. Recreate missing data if needed:
   - `python scripts\populate_zones.py`
   - `python reading\seed_reading.py`

---

## Troubleshooting

### "Migration files keep coming back"
- Run `cleanup-db.bat` to delete them properly
- Check if you have multiple Django installations

### "Migrations say 'conflicts detected'"
- Use `cleanup-db.bat` for complete reset
- Or manually delete conflicting migration files

### "Table already exists" error
- Use `python manage.py migrate --fake-initial`
- Or run `cleanup-db.bat` for fresh start

### "Column does not exist" during restore
- **This is normal!** Schema has changed since backup
- Check `restore_log.txt` to see what was skipped
- Run `python manage.py migrate` to update schema
- Data in matching columns will be restored

### "Dump file too large for git"
- Database dumps can be very large
- Consider using `.gitignore` for `db_dump.sql`
- Or use compressed backups with `pg_dump -Fc`

### "Restore takes too long"
- Large databases can take 5-15 minutes
- This is normal - wait for it to complete
- Progress is shown in terminal

### "Some tables are missing after restore"
- Check if tables were added after backup was created
- Run `python manage.py migrate` to create new tables
- Or use `scripts\populate_zones.py` to recreate data

---

## Configuration

All scripts use these settings (edit in each `.bat` file):

```batch
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "DB_NAME=pygrounds_db"
set "DB_USER=postgres"
set "PGPASSWORD=root"
```

Update these if your PostgreSQL installation differs.
