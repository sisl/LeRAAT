#!/bin/bash

# change the path to your X-Plane XPPython directory, it will look slightly different based on what operating system you are using
PYTHON_EXEC="$HOME/X-Plane 12/Resources/plugins/XPPython3/lin_x64/python3.12/bin/python3.12"

# Ensure the path is treated as a single argument
"$PYTHON_EXEC" -m pip install -r requirements.txt

PYTHON_EXEC_DIR=$(dirname "$PYTHON_EXEC")

# Define TARGET_DIR relative to PYTHON_EXEC_DIR
TARGET_DIR="$PYTHON_EXEC_DIR/../../../../PythonPlugins"

# Copy the PI_AI_Assistant file into the appropriate directory
cp ./PI_AI_Assistant.py "$TARGET_DIR/PI_AI_Assistant.py"
