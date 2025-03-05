#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define the name of the Conda environment
ENV_NAME="relay_server"

# Check if Conda is installed
if ! command -v conda &> /dev/null; then
    echo "Conda is not installed. Please install Conda and try again."
    exit 1
fi

# Create a new Conda environment with Python 3.10
echo "Creating a new Conda environment named $ENV_NAME with Python 3.10..."
conda create -y -n $ENV_NAME python=3.10

# Activate the Conda environment
echo "Activating the Conda environment..."
source $(conda info --base)/etc/profile.d/conda.sh
conda activate $ENV_NAME

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "requirements.txt not found in the current directory. Please provide it and try again."
    conda deactivate
    exit 1
fi

# Install pip if not already installed in the Conda environment
echo "Ensuring pip is installed in the Conda environment..."
conda install -y pip

# Install dependencies from requirements.txt
echo "Installing dependencies from requirements.txt using pip..."
pip install --upgrade pip
pip install -r requirements.txt

# Deactivate the Conda environment
conda deactivate

echo "Conda environment setup complete. Use 'conda activate $ENV_NAME' to activate it."
