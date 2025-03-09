import threading
import time
import logging
import requests
import os
import re
import json
import asyncio
import websockets
from urllib.parse import urlparse
from dotenv import load_dotenv
import paho.mqtt.client as mqtt

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
        
        # MQTT configuration
        self.mqtt_broker = os.getenv('MQTT_BROKER', 'localhost')
        self.mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_topic_prefix = os.getenv('MQTT_TOPIC_PREFIX', 'dune_weaver_black')
        self.mqtt_username = os.getenv('MQTT_USERNAME')
        self.mqtt_password = os.getenv('MQTT_PASSWORD')
        self.mqtt_client = None
        self.use_mqtt = bool(os.getenv('USE_MQTT', 'true').lower() == 'true')
        
        self.target_url = os.getenv('TARGET_API_URL', 'http://localhost:8080')
        self.ws_url = os.getenv('WS_STATUS_URL', '')  # WebSocket URL if using WS
        self.ws_status_endpoint = os.getenv('WS_STATUS_ENDPOINT', '/ws/status')
        self.ws_data_path = os.getenv('WS_DATA_PATH', 'data')  # Path to data in WS messages
        self.status_endpoint = f"{self.target_url}{os.getenv('STATUS_ENDPOINT', '/status')}"
        self.status_property = os.getenv('STATUS_PROPERTY', 'is_running')
        self.current_file_property = os.getenv('CURRENT_ACTIVITY_PROPERTY', 'current_file')
        self.monitor_thread = None
        self.stop_event = threading.Event()
        self.last_activity_running = False
        self.last_current_file = None  # Track the last current_file value
        self.ignored_patterns = []  # List of patterns to ignore
        self.ws = None  # WebSocket connection
        self.ws_reconnect_delay = 5  # Seconds to wait before reconnecting WS
        
        # Determine if we're using WebSocket based on URL
        self.use_websocket = bool(self.ws_url and (self.ws_url.startswith('ws://') or self.ws_url.startswith('wss://')))
        logger.info(f"Using WebSocket endpoint: {self.ws_url}{self.ws_status_endpoint}")
        logger.info(f"Activity monitor initialized with {'WebSocket' if self.use_websocket else 'HTTP'} connection to {self.ws_url}{self.ws_status_endpoint if self.use_websocket else self.status_endpoint}")
        if self.use_websocket:
            logger.info(f"WebSocket URL: {self.ws_url}")
        else:
            logger.info(f"HTTP URL: {self.target_url}")
        logger.info(f"Monitoring property: {self.status_property} and file property: {self.current_file_property}")
        
        # Determine connection priority
        if self.use_mqtt:
            logger.info("Using MQTT for status monitoring")
        elif self.use_websocket:
            logger.info(f"Using WebSocket endpoint: {self.ws_url}{self.ws_status_endpoint}")
        else:
            logger.info(f"Using HTTP polling: {self.status_endpoint}")
    
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
                    #logger.info(f"Ignoring activity matching pattern '{pattern}': {current_file}")
                    return True
            except re.error:
                # If the pattern is invalid, treat it as a simple string match
                if pattern in current_file:
                    #logger.info(f"Ignoring activity containing '{pattern}': {current_file}")
                    return True
                    
        return False
    
    def _setup_mqtt(self):
        """Setup MQTT client and connections"""
        try:
            self.mqtt_client = mqtt.Client()
            
            # Configure authentication if credentials are provided
            if self.mqtt_username and self.mqtt_password:
                logger.info(f"Configuring MQTT authentication for user: {self.mqtt_username}")
                self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            else:
                logger.warning("No MQTT credentials provided, connecting without authentication")
            
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_message = self._on_mqtt_message
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            logger.info(f"Connecting to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"Failed to setup MQTT: {str(e)}")
            self.use_mqtt = False
            
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when MQTT client connects"""
        logger.info("Connected to MQTT broker")
        # Subscribe to relevant topics
        topics = [
            f"{self.mqtt_topic_prefix}/state/running",
            f"{self.mqtt_topic_prefix}/pattern/set/state"
        ]
        for topic in topics:
            client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")

    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when MQTT client disconnects"""
        logger.warning("Disconnected from MQTT broker")
        if not self.stop_event.is_set():
            logger.info("Attempting to reconnect...")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Failed to reconnect to MQTT: {str(e)}")

    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            
            if topic.endswith('/state/running'):
                # Update running state
                is_running = payload.lower() == 'running'
                if not is_running:
                    # If activity stops, handle it immediately
                    status = {
                        self.status_property: False,
                        self.current_file_property: None
                    }
                    self.last_activity_running = False
                else:
                    # If activity starts/is running, wait for current file before acting
                    self.last_activity_running = True
                    return
                
            elif topic.endswith('/pattern/set/state'):
                # Only process pattern updates if we're in running state
                if not self.last_activity_running:
                    return
                    
                current_file = payload
                status = {
                    self.status_property: True,
                    self.current_file_property: current_file
                }
            else:
                return

            # Use asyncio to handle the status update
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._handle_status_update(status))
            loop.close()
            
        except Exception as e:
            logger.error(f"Error processing MQTT message: {str(e)}")

    def start(self):
        """Start the activity monitor thread"""
        if self.monitor_thread and self.monitor_thread.is_alive():
            logger.warning("Activity monitor already running")
            return
        
        logger.info("Starting activity monitor")
        self.stop_event.clear()
        
        if self.use_mqtt:
            self._setup_mqtt()
            self.monitor_thread = threading.Thread(target=self._mqtt_monitor_loop, daemon=True)
        elif self.use_websocket:
            self.monitor_thread = threading.Thread(target=self._run_websocket_loop, daemon=True)
        else:
            self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            
        self.monitor_thread.start()
    
    def stop(self):
        """Stop the activity monitor thread"""
        if not self.monitor_thread or not self.monitor_thread.is_alive():
            logger.warning("Activity monitor not running")
            return
        
        logger.info("Stopping activity monitor")
        self.stop_event.set()
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        self.monitor_thread.join(timeout=10)
        if self.monitor_thread.is_alive():
            logger.warning("Activity monitor thread did not stop cleanly")
    
    def _run_websocket_loop(self):
        """Run the asyncio event loop for WebSocket connection"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while not self.stop_event.is_set():
            try:
                loop.run_until_complete(self._websocket_monitor())
            except Exception as e:
                logger.error(f"WebSocket loop error: {str(e)}")
                if not self.stop_event.is_set():
                    logger.info(f"Reconnecting in {self.ws_reconnect_delay} seconds...")
                    time.sleep(self.ws_reconnect_delay)
        loop.close()

    async def _websocket_monitor(self):
        """Monitor status via WebSocket connection"""
        logger.info(f"Connecting to WebSocket at {self.ws_url}{self.ws_status_endpoint}")
        try:
            async with websockets.connect(self.ws_url + self.ws_status_endpoint) as websocket:
                logger.info("WebSocket connected successfully")
                self.ws = websocket
                
                while not self.stop_event.is_set():
                    try:
                        message = await websocket.recv()
                        status = json.loads(message)
                        await self._handle_status_update(status)
                    except websockets.ConnectionClosed:
                        logger.warning("WebSocket connection closed")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse WebSocket message: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {str(e)}")
        
        finally:
            self.ws = None

    async def _handle_status_update(self, status):
        """Handle a status update from either WebSocket or HTTP polling"""
        try:
            # If using WebSocket, get the data from the nested structure
            if self.use_websocket and self.ws_data_path in status:
                status = status[self.ws_data_path]

            is_running = status.get(self.status_property, False)
            current_file = status.get(self.current_file_property)
            
            # If no activity is running, clear state and stop capture if needed
            if not is_running:
                if self.last_activity_running:
                    logger.info("Activity stopped, notifying webcam controller")
                    self.webcam_controller.activity_stopped()
                self.last_activity_running = False
                self.last_current_file = None
                return
            
            # At this point, we know is_running is True
            # Check if this activity should be ignored
            is_ignored = current_file and self.is_ignored_activity(current_file)
            
            # Store current file regardless of ignored status
            self.last_current_file = current_file
            
            if is_ignored:
                # If we were capturing a non-ignored activity, stop it
                if self.last_activity_running:
                    logger.info("Stopping capture for ignored activity")
                    self.webcam_controller.activity_stopped()
                    self.last_activity_running = False
            else:
                # Non-ignored activity is running
                if not self.last_activity_running:
                    # Either we weren't capturing, or we were ignoring before
                    logger.info("Activity started or transitioned from ignored, notifying webcam controller")
                    self.webcam_controller.activity_started(activity_file=current_file)
                    self.last_activity_running = True
                elif current_file != self.last_current_file:
                    # File changed while running - restart capture
                    logger.info(f"Current file changed from {self.last_current_file} to {current_file}, notifying about new activity")
                    self.webcam_controller.activity_stopped()
                    self.webcam_controller.activity_started(activity_file=current_file)
        
        except Exception as e:
            logger.error(f"Error handling status update: {str(e)}")

    def _monitor_loop(self):
        """Background thread for monitoring activity status via HTTP polling"""
        last_poll_time = time.time()
        
        while not self.stop_event.is_set():
            try:
                current_time = time.time()
                elapsed = current_time - last_poll_time
                logger.debug(f"Time since last poll: {elapsed:.2f} seconds")
                last_poll_time = current_time
                
                logger.info(f"Polling status from {self.target_url}{self.status_endpoint if not self.use_websocket else self.ws_status_endpoint}")
                # Get activity status from target API
                response = requests.get(self.target_url + self.status_endpoint, timeout=5)
                
                if response.status_code == 200:
                    status = response.json()
                    logger.debug(f"Activity status: {status}")
                    
                    # Use asyncio to handle the status update
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._handle_status_update(status))
                    loop.close()
                else:
                    logger.warning(f"Failed to get activity status: HTTP {response.status_code}")
            
            except requests.RequestException as e:
                logger.error(f"Error connecting to target API: {str(e)}")
            except Exception as e:
                logger.error(f"Error in activity monitor: {str(e)}")
            
            # Wait for next poll
            time.sleep(self.poll_interval)
        
        logger.info("Activity monitor loop stopped")

    def _mqtt_monitor_loop(self):
        """Background thread for monitoring MQTT connection"""
        while not self.stop_event.is_set():
            if not self.mqtt_client.is_connected():
                logger.warning("MQTT client disconnected, attempting to reconnect...")
                try:
                    self.mqtt_client.reconnect()
                except Exception as e:
                    logger.error(f"Failed to reconnect to MQTT: {str(e)}")
                    time.sleep(self.poll_interval)
            time.sleep(1)
        
        # Cleanup MQTT client
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect() 