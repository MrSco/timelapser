#!/bin/bash
echo "Setting up Timelapser..."

# install ffmpeg
sudo apt-get install ffmpeg

# Get the directory of the script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Creating virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements-rpi3.txt
pip install 'numpy<2.0'

# Install OpenCV
sudo apt-get install python3-opencv libopenblas-dev -y

if [ ! -d ".venv/lib/python3.*/site-packages/cv2.cpython-311-arm-linux-gnueabihf.so" ]; then
    # Create a symbolic link to the OpenCV library
    cd .venv/lib/python3.*/site-packages/
    ln -s /usr/lib/python3/dist-packages/cv2.cpython-311-arm-linux-gnueabihf.so cv2.so

    cd ../../../..
fi

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