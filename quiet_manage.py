#!/usr/bin/env python
"""
Startup script to suppress all TensorFlow and protobuf warnings before Django loads
"""
import os
import sys

# Set environment variables before any imports
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

# Suppress warnings at the Python level
import warnings
warnings.filterwarnings('ignore')

# Suppress stdout for protobuf warnings
import contextlib
from io import StringIO

class WarningSupressor:
    def __init__(self):
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        
    def __enter__(self):
        # Redirect stderr to suppress protobuf warnings
        sys.stderr = StringIO()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore stderr
        sys.stderr = self.stderr

if __name__ == "__main__":
    # Use the warning suppressor during Django startup
    with WarningSupressor():
        # Import Django after setting environment variables
        import django
        from django.core.management import execute_from_command_line
        
        # Setup Django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
        django.setup()
    
    # Now run the command normally
    if len(sys.argv) > 1:
        execute_from_command_line(sys.argv)
    else:
        print("Usage: python quiet_manage.py <django_command>")
        print("Example: python quiet_manage.py shell")
