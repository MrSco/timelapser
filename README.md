# Timelapser

A standalone timelapse capture tool designed to work with any system that provides a status API. This tool can automatically start and stop timelapse recording based on the status of the monitored system.

## Features

- Automatic timelapse recording when activities are running
- Manual timelapse control
- Camera settings adjustment (brightness, contrast, exposure)
- Timelapse video creation
- Web interface for control and monitoring
- Can run as a system service
- Cross-platform support (Windows, macOS, Linux)
- Pattern-based activity filtering
- Multiple camera support with automatic detection
- Camera preview and test capture functionality
- Session-based recording with automatic file organization
- State persistence between restarts

## Requirements

- Python 3.7+
- OpenCV
- A compatible webcam

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/mrsco/timelapser.git
   cd timelapser
   ```

2. Create a virtual environment (recommended):
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows:
     ```
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```
     source venv/bin/activate
     ```

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Configure the application by creating a `.env` file:
   ```
   TARGET_API_URL=http://localhost:8080
   STATUS_ENDPOINT=/status
   STATUS_PROPERTY=is_running
   CURRENT_ACTIVITY_PROPERTY=current_file
   TIMELAPSE_DIR=./timelapses
   PORT=5001
   POLL_INTERVAL=5 
   ```

## Usage

### Running the application

```
python -m timelapser
```

Or use the provided scripts:
- Windows: `run_timelapser.bat`
- Linux/Mac: `run_timelapser.sh`

The web interface will be available at `http://localhost:5001` (or the port you configured).

### Configuration Options

Edit the `.env` file to customize:

- `TARGET_API_URL`: URL of the target system's API that provides status information
- `STATUS_ENDPOINT`: Endpoint to check the status of the target system
- `STATUS_PROPERTY`: Property name in the status response that indicates if the target system is running
- `CURRENT_ACTIVITY_PROPERTY`: Property name in the status response that indicates the current activity of the target system
- `TIMELAPSE_DIR`: Directory to store timelapse images and videos
- `PORT`: Port for the web interface
- `POLL_INTERVAL`: How often to check the activity status (in seconds)

### Target API Requirements

The target system must provide a status endpoint (e.g., `/status`) that returns JSON with at least the following field:

```json
{
   "current_file": "pattern.thr",
   "is_running": true|false
}
```

When `is_running` is `true`, the timelapser will start capturing frames (if auto mode is enabled).
When `is_running` is `false`, the timelapser will stop capturing frames (if auto mode is enabled).

It will also check for the `current_file` property to detect when a new activity starts. 
When a new activity is detected, the timelapser will stop the current activity and start a new one.

### Pattern Filtering

You can configure patterns to ignore certain activities. When an activity matches one of these patterns, the timelapser will not record it, even if auto mode is enabled. This is useful for ignoring test runs or specific file types.

Patterns can be:
- Regular expressions (for advanced matching)
- Simple text strings (for basic matching)

### Camera Settings

The web interface allows you to:
- Select from available cameras on your system
- Adjust brightness, contrast, and exposure
- Test camera settings with a preview capture
- View the most recent capture from the active session

### Session Management

Each timelapse recording is organized into a session with:
- Timestamp-based directory naming
- Session metadata stored in JSON format
- Automatic frame numbering
- Video creation from captured frames

## Running as a Service

### Windows (using NSSM)

1. Download and install [NSSM](https://nssm.cc/)
2. Open Command Prompt as Administrator
3. Run:
   ```
   nssm install Timelapser
   ```
4. In the dialog that appears:
   - Application Path: Path to your Python executable (e.g., `C:\path\to\venv\Scripts\python.exe`)
   - Startup Directory: Path to your project directory
   - Arguments: `-m timelapser`
5. Configure other settings as needed and click "Install service"
6. Start the service:
   ```
   nssm start Timelapser
   ```

### Linux (systemd)

1. Create a service file:
   ```
   sudo nano /etc/systemd/system/timelapser.service
   ```

2. Add the following content:
   ```
   [Unit]
   Description=Timelapser Service
   After=network.target

   [Service]
   User=yourusername
   WorkingDirectory=/path/to/timelapser
   ExecStart=/path/to/timelapser/venv/bin/python -m timelapser
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

3. Save the file and reload systemd:
   ```
   sudo systemctl daemon-reload
   ```

4. Enable and start the service:
   ```
   sudo systemctl enable timelapser
   sudo systemctl start timelapser
   ```

5. Check the status:
   ```
   sudo systemctl status timelapser
   ```

## License

MIT 