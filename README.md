# Timelapser

A standalone timelapse capture tool designed to work with any system that provides a status API. This tool can automatically start and stop timelapse recording based on the status of the monitored system.

## Features

- Automatic timelapse recording when activities are running
- Manual timelapse control
- Camera settings adjustment (brightness, contrast, exposure)
- Timelapse video creation
- Web interface for control and monitoring
- Can run as a system service

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
   - Arguments: `.\app.py`
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
   ExecStart=/path/to/timelapser/.venv/bin/python app.py
   Restart=always
   RestartSec=5
   StandardOutput=syslog
   StandardError=syslog
   SyslogIdentifier=timelapser

   [Install]
   WantedBy=multi-user.target
   ```

3. Enable and start the service:
   ```
   sudo systemctl enable timelapser
   sudo systemctl start timelapser
   ```

4. Check the status:
   ```
   sudo systemctl status timelapser
   ```

## License

MIT 