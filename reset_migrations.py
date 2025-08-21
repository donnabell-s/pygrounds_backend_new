#!/usr/bin/env python
"""
Script to reset all Django migrations by clearing the django_migrations table
and then re-applying all migrations from scratch.
"""
import os
import sys
import django
from django.conf import settings
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

def reset_migrations():
    """Clear all migration records and reset the migration state."""
    
    print("🔄 Resetting Django migrations...")
    
    with connection.cursor() as cursor:
        # Clear all migration records
        print("Clearing django_migrations table...")
        cursor.execute("DELETE FROM django_migrations")
        
        print(f"✅ Cleared {cursor.rowcount} migration records")
    
    print("✅ Migration reset complete!")
    print("Now run: python manage.py migrate --fake-initial")

if __name__ == "__main__":
    reset_migrations()
