#!/bin/bash
echo "Setting up Timelapser..."

# Get the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env file created. Please edit it with your configuration."
else
    echo ".env file already exists."
fi

echo "Setup complete!"
echo "You can now run Timelapser using: source .venv/bin/activate && python app.py"

# Make the script executable
chmod +x "$DIR/run_timelapser.sh"
echo "Or you can use the run_timelapser.sh script." 