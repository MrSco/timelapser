import threading
import time
import logging
import requests
import os
import re
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

class ActivityMonitor:
    def __init__(self, webcam_controller, poll_interval=5):
        """
        Initialize the activity monitor
        
        Args:
            webcam_controller: WebcamController instance to control timelapse
            poll_interval: How often to poll the status endpoint (in seconds)
        """
        # Load environment variables
        load_dotenv()
        
        self.webcam_controller = webcam_controller
        self.poll_interval = poll_interval
        self.target_url = os.getenv('TARGET_API_URL', 'http://localhost:8080')
        self.status_endpoint = f"{self.target_url}{os.getenv('STATUS_ENDPOINT', '/status')}"
        self.status_property = os.getenv('STATUS_PROPERTY', 'is_running')
        self.current_file_property = os.getenv('CURRENT_ACTIVITY_PROPERTY', 'current_file')
        self.monitor_thread = None
        self.stop_event = threading.Event()
        self.last_activity_running = False
        self.last_current_file = None  # Track the last current_file value
        self.ignored_patterns = []  # List of patterns to ignore
        
        logger.info(f"Activity monitor initialized with target URL: {self.target_url}")
        logger.info(f"Monitoring property: {self.status_property} and file property: {self.current_file_property}")
    
    def set_ignored_patterns(self, patterns):
        """Set the list of patterns to ignore"""
        self.ignored_patterns = patterns
        logger.info(f"Updated ignored patterns: {patterns}")
    
    def is_ignored_activity(self, current_file):
        """Check if the current file matches any of the ignored patterns"""
        if not current_file or not self.ignored_patterns:
            return False
            
        for pattern in self.ignored_patterns:
            try:
                if re.search(pattern, current_file):
                    logger.info(f"Ignoring activity matching pattern '{pattern}': {current_file}")
                    return True
            except re.error:
                # If the pattern is invalid, treat it as a simple string match
                if pattern in current_file:
                    logger.info(f"Ignoring activity containing '{pattern}': {current_file}")
                    return True
                    
        return False
    
    def start(self):
        """Start the activity monitor thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Activity monitor already running")
            return
        
        logger.info("Starting activity monitor")
        self.stop_event.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop(self):
        """Stop the activity monitor thread"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            logger.warning("Activity monitor not running")
            return
        
        logger.info("Stopping activity monitor")
        self.stop_event.set()
        self.monitor_thread.join(timeout=10)
        if self.monitor_thread.is_alive():
            logger.warning("Activity monitor thread did not stop cleanly")
    
    def _monitor_loop(self):
        """Background thread for monitoring activity status"""
        #logger.info("Activity monitor loop started")
        
        while not self.stop_event.is_set():
            try:
                #logger.info("Checking activity status...")
                # Get activity status from target API
                response = requests.get(self.status_endpoint, timeout=5)
                
                if response.status_code == 200:
                    status = response.json()
                    logger.debug(f"Activity status: {status}")
                    
                    # Check if an activity is running
                    is_running = status.get(self.status_property, False)
                    
                    # Get current file from status
                    current_file = status.get(self.current_file_property)
                    
                    # Log current file if it exists
                    if current_file:
                        logger.info(f"Current file: {current_file}")
                    
                    # Check if this activity should be ignored
                    if is_running and current_file and self.is_ignored_activity(current_file):
                        # If we're already capturing, stop it as this is an ignored activity
                        if self.last_activity_running:
                            logger.info("Stopping capture for ignored activity")
                            self.webcam_controller.activity_stopped()
                            self.last_activity_running = False
                        continue  # Skip the rest of the processing
                    
                    # Handle activity start/stop
                    if is_running and not self.last_activity_running:
                        logger.info("Activity started, notifying webcam controller")
                        self.webcam_controller.activity_started()
                    elif not is_running and self.last_activity_running:
                        logger.info("Activity stopped, notifying webcam controller")
                        self.webcam_controller.activity_stopped()
                    
                    # Handle file changes (new activity while already running)
                    if is_running and current_file:
                        # If this is the first file we've seen, just store it
                        if self.last_current_file is None:
                            logger.info(f"Initial current file detected: {current_file}")
                        # If the file has changed, notify about new activity
                        elif current_file != self.last_current_file:
                            logger.info(f"Current file changed from {self.last_current_file} to {current_file}, notifying about new activity")
                            
                            # First stop the current activity
                            self.webcam_controller.activity_stopped()
                            
                            # Then start a new activity
                            self.webcam_controller.activity_started()
                    
                    # Update last status
                    self.last_activity_running = is_running
                    self.last_current_file = current_file if is_running else None
                else:
                    logger.warning(f"Failed to get activity status: HTTP {response.status_code}")
            
            except requests.RequestException as e:
                logger.error(f"Error connecting to target API: {str(e)}")
            except Exception as e:
                logger.error(f"Error in activity monitor: {str(e)}")
            
            # Wait for next poll
            time.sleep(self.poll_interval)
        
        logger.info("Activity monitor loop stopped") 