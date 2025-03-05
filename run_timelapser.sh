#!/bin/bash
echo "Starting Timelapser..."

# Get the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Check if virtual environment exists
if [ -d ".venv" ]; then
    # Activate virtual environment
    source .venv/bin/activate
    
    # Run the application
    python app.py
else
    echo "Virtual environment not found. Please run setup_unix.sh first."
    exit 1
fi 