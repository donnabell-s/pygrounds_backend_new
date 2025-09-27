echo "[RESTORE] Dropping + Migrating + Reseeding..."
python manage.py migrate
python manage.py shell < reading/seed_reading_new.py
echo "eed restore complete (from seed_reading_new.py)"