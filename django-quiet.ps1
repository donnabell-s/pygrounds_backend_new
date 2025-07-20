# PowerShell script to run Django commands with TensorFlow warnings suppressed

# Set TensorFlow environment variables to suppress warnings
$env:TF_CPP_MIN_LOG_LEVEL="3"
$env:TF_ENABLE_ONEDNN_OPTS="0"
$env:PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION="python"

# Run the Django command with all passed arguments
python manage.py @args
