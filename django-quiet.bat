@echo off
REM Script to run Django commands with TensorFlow warnings suppressed

REM Set TensorFlow environment variables to suppress warnings
set TF_CPP_MIN_LOG_LEVEL=3
set TF_ENABLE_ONEDNN_OPTS=0
set PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

REM Run the Django command passed as arguments
python manage.py %*
