#!/bin/zsh

while true; do
  clear
  echo "==============================================="
  echo "        PYGROUNDS DATABASE MENU (macOS)"
  echo "==============================================="
  echo "[1] COMPLETE RESET (cleanup-db.sh)"
  echo "[2] MIGRATION RESET ONLY (reset-migrations.sh)"
  echo "[3] RESTORE FROM BACKUP (restore-db.sh)"
  echo "[4] EXIT"
  echo
  read "?Choose option (1-4): "

  case $REPLY in
    1) ./cleanup-db.sh; read "?Press ENTER...";;
    2) ./reset-migrations.sh; read "?Press ENTER...";;
    3) ./restore-db.sh; read "?Press ENTER...";;
    4) exit 0;;
    *) echo "Invalid choice"; sleep 1;;
  esac
done
