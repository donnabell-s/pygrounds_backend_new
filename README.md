## 🗃️ Database Setup for Local Development (PostgreSQL)

### 📤 Dump the Local Database (Export)

If you've made changes to the database (schema or data) and want to share it with the team:

1. Open your terminal or double-click the script.
2. Run the script:

```bash
./dump-db.bat
```

This will export the current state of your local `pygrounds_db` into `db_dump.sql`.

> ✅ Commit `db_dump.sql` after running this if you want others to sync to your version:

```bash
git add db_dump.sql
git commit -m "Update DB dump"
git push
```

---

### 📥 Load the Shared Database (Import)

If someone updated `db_dump.sql` and you want to apply those changes:

1. Pull the latest version of the repository:

```bash
git pull
```

2. Run the load script:

```bash
./load-db.bat
```

This will:

* Create the `pygrounds_db` database (if it doesn't exist)
* Import the latest schema and data from `db_dump.sql`

---

### ⚙️ Script Configuration

Both scripts use hardcoded PostgreSQL settings like user, DB name, and installation path.
Before using them, make sure you:

1. Copy the example scripts (if provided) and configure your local settings:

   * `PG_BIN` – your PostgreSQL bin path (e.g., `C:\Program Files\PostgreSQL\17\bin`)
   * `DB_USER` – your local Postgres username (usually `postgres`)
   * `PGPASSWORD` – your password

---

### 🔒 Git Ignore Reminder

These scripts should not be pushed to GitHub. They are ignored in `.gitignore`:

```gitignore
load-db.bat
dump-db.bat
```

