#!/usr/bin/env python
"""
Script to check current database tables and schema
"""
import os
import sys
import django
from django.conf import settings
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

def check_database():
    """Check current database tables."""
    
    print("📋 Checking current database tables...")
    
    with connection.cursor() as cursor:
        # Get all table names
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = cursor.fetchall()
        print(f"\n📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check django_content_type structure specifically
        print("\n🔍 Checking django_content_type table structure...")
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'django_content_type'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        if columns:
            print("Columns in django_content_type:")
            for col in columns:
                print(f"  - {col[0]} ({col[1]})")
        else:
            print("django_content_type table not found or has no columns")

if __name__ == "__main__":
    check_database()
