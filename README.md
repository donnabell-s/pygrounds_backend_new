# Pygrounds Backend

This document covers backend seeding tasks you may need during development: achievements and reading content.

## Prerequisites
- Run these commands from the backend project root (the folder that contains `manage.py`).
- Ensure your Python environment is active and dependencies from `requirements.txt` are installed.

## Seed Achievements
The achievements seeder is an idempotent Django management command. It will create any missing default achievements by code and can optionally update existing ones.

Common commands (PowerShell):

```powershell
# Initial seed (creates any missing achievements; leaves existing ones unchanged)
python manage.py seed_achievements

# Update existing achievements' title/description/unlocked_zone to match defaults
python manage.py seed_achievements --update

# Preview what would change without writing to the database
python manage.py seed_achievements --update --dry-run

# Destructive reset: delete ALL user achievement unlocks and ALL achievements, then reseed
python manage.py seed_achievements --reset
```

Notes:
- `--update` only modifies title, description, and unlocked_zone for existing codes; it never creates duplicates.
- `--dry-run` prints what would be created/updated and is safe to use in any environment.
- `--reset` is destructive. It removes all `UserAchievement` rows first, then all `Achievement` rows, and reseeds the defaults.
- After running, check the console summary: `Seed complete. Created: X. Updated: Y. Total in DB: Z`.

## Seed Reading Content
Reading content can be seeded via a small script executed inside the Django shell.

Commands (PowerShell):

```powershell
# Open a Django shell from the backend project root
python manage.py shell
```

Then in the interactive shell:

```python
# Execute the seeding script (path relative to manage.py)
exec(open('reading/seed_reading.py').read())
```

Tips:
- The path `reading/seed_reading.py` is relative to the project root containing `manage.py`.
- If your file lives elsewhere, adjust the relative path accordingly.
- The script should be idempotent or handle duplicate data gracefully; rerun as needed during development.

## Verification
- Use Django admin to confirm results:
  - Achievements: titles/descriptions updated and expected entries present.
  - Reading content: new entries visible and linked as expected.

## Troubleshooting
- If you see "Skipped existing achievement (use --update to modify)", rerun with `--update`.
- To safely inspect planned changes before applying, use `--dry-run`.
- Ensure you’re in the correct directory (where `manage.py` is) when running commands.
