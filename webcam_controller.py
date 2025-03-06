import os
import time
import threading
import subprocess
import platform
import logging
import json
import re
from datetime import datetime
from pathlib import Path
import numpy as np
import cv2  # Import OpenCV globally
from dotenv import load_dotenv
import requests

# Configure logging
logger = logging.getLogger(__name__)

class WebcamController:
    def __init__(self, timelapse_dir='./timelapses'):
        # Convert relative path to absolute path to avoid issues with changing working directory
        self.timelapse_dir = os.path.abspath(timelapse_dir)
        self.current_session_dir = None
        self.is_capturing = False
        self.capture_thread = None
        self.interval = 5  # Default interval in seconds
        self.auto_mode = False  # Auto start/stop with patterns
        self.selected_camera = '/dev/video0'  # Default camera
        self.available_cameras = []
        self.lock = threading.Lock()
        
        # Default camera settings - using neutral values to enable auto mode by default
        self.camera_settings = {
            'brightness': 0.5,  # Neutral value (was 0.4)
            'contrast': 1.0,    # Neutral value (was 1.2)
            'exposure': 0.5     # Neutral value (was 0.1)
        }
        
        # Camera cache to avoid reopening cameras
        self.camera_cache = {}
        self.camera_cache_lock = threading.Lock()
        self.camera_last_used = {}
        self.camera_cache_timeout = 30  # Seconds to keep a camera open
        
        # Video creation process tracking
        self.ffmpeg_processes = {}
        self.ffmpeg_processes_lock = threading.Lock()
        
        # Create timelapses directory if it doesn't exist
        os.makedirs(self.timelapse_dir, exist_ok=True)
        
        # Detect platform
        self.platform = platform.system()
        logger.info(f"Detected platform: {self.platform}")
        
        # Start camera cache cleanup thread
        self.cache_cleanup_thread = threading.Thread(target=self._cleanup_camera_cache, daemon=True)
        self.cache_cleanup_thread.start()
        
        # Scan for available cameras
        self.scan_cameras()
    
    def scan_cameras(self):
        """Scan for available camera devices based on platform"""
        self.available_cameras = []
        
        try:
            if self.platform == 'Linux':
                # On Linux, look for video devices in /dev
                video_devices = [f"/dev/video{i}" for i in range(10) if os.path.exists(f"/dev/video{i}")]
                self.available_cameras = video_devices
            elif self.platform == 'Windows':
                # On Windows, use more reliable method to detect cameras
                try:
                    # First try using ffmpeg to list devices
                    result = subprocess.run(
                        ['ffmpeg', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'],
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        errors='replace',
                        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                    )
                    
                    lines = result.stderr.split('\n')
                    in_video_devices = False
                    for line in lines:
                        if 'DirectShow video devices' in line:
                            in_video_devices = True
                            continue
                        if in_video_devices and 'DirectShow audio devices' in line:
                            in_video_devices = False
                            break
                        if in_video_devices and '"' in line:
                            try:
                                camera_name = line.split('"')[1]
                                if camera_name and camera_name.strip():
                                    self.available_cameras.append(camera_name)
                            except IndexError:
                                pass
                except Exception as e:
                    logger.warning(f"Error using ffmpeg to list devices: {str(e)}")
                    
                # If no cameras found, try alternative method
                if not self.available_cameras:
                    try:
                        # Try using PowerShell to get camera info
                        ps_command = "Get-CimInstance Win32_PnPEntity | Where-Object {$_.PNPClass -eq 'Camera'} | Select-Object Name | ConvertTo-Json"
                        result = subprocess.run(
                            ['powershell', '-Command', ps_command],
                            capture_output=True,
                            text=True
                        )
                        
                        if result.stdout.strip():
                            try:
                                cameras_data = json.loads(result.stdout)
                                # Handle both single camera and multiple cameras
                                if isinstance(cameras_data, dict):
                                    camera_name = cameras_data.get('Name')
                                    if camera_name:
                                        self.available_cameras.append(camera_name)
                                elif isinstance(cameras_data, list):
                                    for camera in cameras_data:
                                        camera_name = camera.get('Name')
                                        if camera_name:
                                            self.available_cameras.append(camera_name)
                            except json.JSONDecodeError:
                                pass
                    except Exception as e:
                        logger.warning(f"Error using PowerShell to list cameras: {str(e)}")
            elif self.platform == 'Darwin':  # macOS
                # On macOS, use ffmpeg with AVFoundation
                result = subprocess.run(
                    ['ffmpeg', '-f', 'avfoundation', '-list_devices', 'true', '-i', ''],
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                lines = result.stderr.split('\n')
                for line in lines:
                    if '[AVFoundation input device]' in line and 'video' in line.lower():
                        parts = line.split(']')
                        if len(parts) > 1:
                            camera_name = parts[1].strip()
                            self.available_cameras.append(camera_name)
        except Exception as e:
            logger.error(f"Error scanning for cameras: {str(e)}")
        
        # If no cameras found, add a default one
        if not self.available_cameras:
            if self.platform == 'Linux':
                self.available_cameras = ['/dev/video0']
            elif self.platform == 'Windows':
                self.available_cameras = ['0']  # Use index instead of name for Windows
            elif self.platform == 'Darwin':
                self.available_cameras = ['0']  # Use index for macOS too
        
        logger.info(f"Available cameras: {self.available_cameras}")
        return self.available_cameras
    
    def start_timelapse(self, camera=None, interval=None, auto_mode=None, activity_file=None):
        """Start timelapse capture"""
        with self.lock:
            if self.is_capturing:
                logger.warning("Timelapse already running")
                return False
            
            # Update settings if provided
            if camera is not None:
                self.selected_camera = camera
            if interval is not None:
                self.interval = float(interval)
            if auto_mode is not None:
                self.auto_mode = bool(auto_mode)
            
            # Create a new session directory with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.current_session_dir = os.path.join(self.timelapse_dir, f"timelapse_{timestamp}")
            os.makedirs(self.current_session_dir, exist_ok=True)
            
            # Save session info
            session_info = {
                'start_time': timestamp,
                'camera': self.selected_camera,
                'interval': self.interval,
                'auto_mode': self.auto_mode,
                'platform': self.platform
            }
            
            # Add activity file if provided
            if activity_file:
                session_info['activity_file'] = activity_file
            
            with open(os.path.join(self.current_session_dir, 'session_info.json'), 'w') as f:
                json.dump(session_info, f)
            
            # Start capture thread
            self.is_capturing = True
            self.capture_thread = threading.Thread(target=self._capture_loop)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            logger.info(f"Started timelapse capture with camera {self.selected_camera}, interval {self.interval}s")
            return True
    
    def stop_timelapse(self):
        """Stop timelapse capture"""
        with self.lock:
            if not self.is_capturing:
                logger.warning("No timelapse running")
                return False
            
            self.is_capturing = False
            if self.capture_thread:
                self.capture_thread.join(timeout=2.0)
            
            logger.info("Stopped timelapse capture")
            return True
    
    def _capture_loop(self):
        """Background thread for capturing images at intervals"""
        frame_count = 0
        last_capture_time = 0
        
        while self.is_capturing:
            try:
                # Get current time
                current_time = time.time()
                
                # Check if it's time for the next capture
                # This prevents double captures if the previous capture took longer than expected
                if current_time - last_capture_time < self.interval:
                    # Not time yet, sleep a bit and continue
                    time.sleep(0.1)
                    continue
                
                # Update last capture time
                last_capture_time = current_time
                
                # Increment frame count
                frame_count += 1
                
                # Generate timestamp and output filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(self.current_session_dir, f"frame_{frame_count:06d}_{timestamp}.jpg")
                
                # Capture frame with fast_mode=True for better performance in timelapses
                # We prioritize speed over image quality for timelapse captures
                self.capture_single_frame(output_file=output_file, fast_mode=True)
                
                logger.debug(f"Captured frame {frame_count} to {output_file}")
                
            except Exception as e:
                logger.error(f"Error in capture loop: {str(e)}")
                # Sleep a bit to avoid tight loop in case of persistent errors
                time.sleep(max(1, self.interval / 2))  # Sleep at least 1 second, or half the interval
    
    def _get_camera_index(self, camera=None):
        """Helper method to convert camera identifier to an index
        
        Args:
            camera: Camera identifier (index, string, or device path)
            
        Returns:
            Integer camera index for OpenCV
        """
        camera_to_use = camera if camera is not None else self.selected_camera
        camera_index = 0  # Default to first camera
        
        if camera_to_use is None:
            return camera_index
            
        # Handle integer camera index
        if isinstance(camera_to_use, int):
            return camera_to_use
            
        # Handle string camera identifier
        if isinstance(camera_to_use, str):
            # Case 1: Camera is a digit string (e.g., "0", "1")
            if camera_to_use.isdigit():
                return int(camera_to_use)
                
            # Case 2: Camera has format "index:name" (e.g., "0:Camera")
            if ':' in camera_to_use and camera_to_use.split(':')[0].isdigit():
                return int(camera_to_use.split(':')[0])
                
            # Case 3: Linux /dev/videoX format
            if self.platform == 'Linux' and camera_to_use.startswith('/dev/video'):
                try:
                    return int(camera_to_use.replace('/dev/video', ''))
                except ValueError:
                    pass
                    
            # Case 4: Camera name is in available_cameras list
            if camera_to_use in self.available_cameras:
                return self.available_cameras.index(camera_to_use)
                
            # Case 5: Try to use camera name directly with OpenCV
            # This works on some systems where OpenCV can use camera names
            if self.platform == 'Windows':
                # On Windows, try to find the camera in available_cameras by partial match
                for i, cam_name in enumerate(self.available_cameras):
                    if camera_to_use.lower() in cam_name.lower():
                        return i
        
        # If all else fails, return the default camera index
        logger.warning(f"Could not determine camera index for '{camera_to_use}', using default (0)")
        return camera_index

    def _cleanup_camera_cache(self):
        """Background thread to clean up unused camera objects"""
        while True:
            try:
                current_time = time.time()
                cameras_to_release = []
                
                with self.camera_cache_lock:
                    for camera_id, last_used in list(self.camera_last_used.items()):
                        # If camera hasn't been used in the timeout period, release it
                        if current_time - last_used > self.camera_cache_timeout:
                            cameras_to_release.append(camera_id)
                    
                    # Release cameras outside the loop to avoid modifying dict during iteration
                    for camera_id in cameras_to_release:
                        if camera_id in self.camera_cache:
                            logger.debug(f"Releasing cached camera {camera_id} due to inactivity")
                            self.camera_cache[camera_id].release()
                            del self.camera_cache[camera_id]
                            del self.camera_last_used[camera_id]
            except Exception as e:
                logger.error(f"Error in camera cache cleanup: {str(e)}")
            
            # Sleep for a while before checking again
            time.sleep(5)

    def _get_camera(self, camera_index):
        """Get a camera object from cache or create a new one
        
        Args:
            camera_index: Integer camera index for OpenCV
            
        Returns:
            OpenCV VideoCapture object
        """
        cache_key = str(camera_index)
        
        with self.camera_cache_lock:
            # Update last used time if camera is in cache
            if cache_key in self.camera_cache:
                self.camera_last_used[cache_key] = time.time()
                
                # Check if camera is still valid
                if not self.camera_cache[cache_key].isOpened():
                    logger.debug(f"Cached camera {cache_key} is no longer valid, recreating")
                    self.camera_cache[cache_key].release()
                    del self.camera_cache[cache_key]
                else:
                    return self.camera_cache[cache_key]
            
            # Create new camera if not in cache or no longer valid
            logger.debug(f"Creating new camera for index {camera_index}")
            cam = cv2.VideoCapture(camera_index)
            
            if not cam.isOpened():
                raise Exception(f"Failed to open camera {camera_index}")
            
            # Set camera properties for better image quality
            # Use resolution from settings if available
            resolution = self.camera_settings.get('resolution', '1280x720')
            self._set_camera_resolution(cam, resolution)
            
            # Check if we have manual settings enabled
            has_manual_settings = False
            
            # If brightness, contrast or exposure are not at default values, use manual mode
            default_settings = {
                'brightness': 0.5,  # Changed from 0.4 to 0.5 as neutral value
                'contrast': 1.0,    # Changed from 1.2 to 1.0 as neutral value
                'exposure': 0.5     # Changed from 0.1 to 0.5 as neutral value
            }
            
            for setting, default_value in default_settings.items():
                if abs(self.camera_settings.get(setting, default_value) - default_value) > 0.01:
                    has_manual_settings = True
                    break
            
            if has_manual_settings:
                # Manual mode - first set auto exposure to manual mode
                cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure (0.25 or 1)
                
                # Apply user-defined camera settings to hardware
                cam.set(cv2.CAP_PROP_BRIGHTNESS, self.camera_settings['brightness'])
                cam.set(cv2.CAP_PROP_CONTRAST, self.camera_settings['contrast'])
                cam.set(cv2.CAP_PROP_EXPOSURE, self.camera_settings['exposure'])
                
                logger.debug(f"Applied manual camera settings: {self.camera_settings}")
            else:
                # Auto mode - enable auto exposure
                cam.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)  # Auto exposure (0.75 or 3)
                logger.debug("Using auto exposure and default camera settings")
            
            # Add to cache
            self.camera_cache[cache_key] = cam
            self.camera_last_used[cache_key] = time.time()
            
            return cam

    def _set_camera_resolution(self, camera, resolution_str):
        """Set camera resolution with fallback to lower resolutions if needed
        
        Args:
            camera: OpenCV VideoCapture object
            resolution_str: Resolution string in format "WIDTHxHEIGHT"
            
        Returns:
            Tuple of (width, height) that was successfully set
        """
        # Define fallback resolutions in descending order
        fallback_resolutions = ['1920x1080', '1280x720', '800x600', '640x480']
        
        # If the requested resolution is not in our fallback list, add it at the beginning
        if resolution_str not in fallback_resolutions:
            fallback_resolutions.insert(0, resolution_str)
        else:
            # Move the requested resolution to the beginning
            fallback_resolutions.remove(resolution_str)
            fallback_resolutions.insert(0, resolution_str)
        
        # Try each resolution until one works
        for res in fallback_resolutions:
            try:
                width, height = map(int, res.split('x'))
                logger.debug(f"Trying to set camera resolution to {width}x{height}")
                
                # Set resolution
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                
                # Read a test frame to verify the resolution works
                success, frame = camera.read()
                if success and frame is not None and frame.size > 0:
                    actual_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
                    actual_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    logger.info(f"Camera resolution set to {actual_width}x{actual_height}")
                    
                    # Update the camera settings with the actual resolution
                    if actual_width != width or actual_height != height:
                        self.camera_settings['resolution'] = f"{actual_width}x{actual_height}"
                        logger.info(f"Camera reported different resolution than requested. Using {actual_width}x{actual_height}")
                    
                    return (actual_width, actual_height)
            except Exception as e:
                logger.warning(f"Failed to set resolution {res}: {str(e)}")
        
        # If all resolutions failed, log an error and use whatever the camera defaults to
        logger.error("All resolution settings failed, using camera defaults")
        return (int(camera.get(cv2.CAP_PROP_FRAME_WIDTH)), int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT)))

    def capture_single_frame(self, output_file=None, camera=None, return_base64=False, fast_mode=False):
        """Capture a single frame using OpenCV - can be used for both test captures and timelapse captures
        
        Args:
            output_file: Path to save the captured frame (optional if return_base64=True)
            camera: Camera identifier (index, string, or device path)
            return_base64: If True, return the frame as a base64 encoded string instead of saving to disk
            fast_mode: If True, skip image processing for faster capture
            
        Returns:
            True if saved to disk successfully, or base64 encoded string if return_base64=True
        """
        try:
            # Get camera index using the helper method
            camera_index = self._get_camera_index(camera)
            
            logger.debug(f"Capturing with camera index: {camera_index} and settings: {self.camera_settings}")
            
            # Get camera from cache or create new one
            cam = self._get_camera(camera_index)
            
            # Reduced wait time - only wait if not in fast mode
            if not fast_mode:
                time.sleep(0.1)  # Reduced from 0.5 to 0.1 seconds
            
            # Capture frame
            ret, frame = cam.read()
            
            # Don't release the camera - it's now cached
            # cam.release()
            
            if not ret or frame is None:
                raise Exception("Failed to capture frame from camera")
            
            # Apply post-processing adjustments in software only if not in fast mode
            if not fast_mode:
                # Convert brightness from 0-1 to -1 to 1 range (0.5 is neutral)
                brightness_adjust = (self.camera_settings['brightness'] - 0.5) * 2.0
                
                # Apply brightness adjustment
                if brightness_adjust > 0:
                    # Increase brightness
                    frame = cv2.addWeighted(frame, 1, np.zeros(frame.shape, frame.dtype), 0, brightness_adjust * 100)
                else:
                    # Decrease brightness
                    frame = cv2.addWeighted(frame, 1, np.zeros(frame.shape, frame.dtype), 0, brightness_adjust * 100)
                
                # Apply contrast adjustment
                # Convert to float and normalize to 0-1
                f = frame.astype(np.float32) / 255.0
                # Apply contrast adjustment (contrast_factor of 1.0 is neutral)
                contrast_factor = self.camera_settings['contrast']
                f = (f - 0.5) * contrast_factor + 0.5
                # Clip to 0-1 range
                f = np.clip(f, 0, 1)
                # Convert back to 8-bit
                frame = (f * 255).astype(np.uint8)
            
            # If return_base64 is True, return the frame as a base64 encoded string
            if return_base64:
                # Encode the frame as JPEG
                success, buffer = cv2.imencode('.jpg', frame)
                if not success:
                    raise Exception("Failed to encode image")
                
                # Convert to base64
                import base64
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                # Return the base64 encoded image with MIME type
                return f"data:image/jpeg;base64,{jpg_as_text}"
            
            # Otherwise save the processed frame to disk
            else:
                if output_file is None:
                    raise ValueError("output_file must be provided when return_base64 is False")
                
                # Save the processed frame
                cv2.imwrite(output_file, frame)
                
                # Verify the file was created successfully
                if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                    raise Exception(f"Failed to save frame - output file is empty or missing: {output_file}")
                    
                logger.debug(f"Captured and processed frame to {output_file}")
                return True
                
        except Exception as e:
            logger.error(f"Error capturing frame: {str(e)}")
            raise

    def test_capture(self, camera=None, output_dir=None, return_base64=True):
        """Take a test capture with the specified camera
        
        Args:
            camera: Camera identifier (index, string, or device path)
            output_dir: Directory to save the captured frame (only used if return_base64=False)
            return_base64: If True, return the frame as a base64 encoded string instead of saving to disk
            
        Returns:
            Base64 encoded image string if return_base64=True, otherwise path to saved image
        """
        try:
            # Use fast mode for test captures to improve responsiveness
            if return_base64:
                # For preview/test captures, use fast mode to improve responsiveness
                return self.capture_single_frame(camera=camera, return_base64=True, fast_mode=True)
            else:
                # For saving test captures, use normal mode with image processing
                # Create output directory if it doesn't exist
                if output_dir is None:
                    output_dir = os.path.join(self.timelapse_dir, 'test_captures')
                
                os.makedirs(output_dir, exist_ok=True)
                
                # Generate timestamp and output filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file = os.path.join(output_dir, f"test_capture_{timestamp}.jpg")
                
                # Capture frame
                self.capture_single_frame(output_file=output_file, camera=camera, return_base64=False, fast_mode=False)
                
                # Return relative path to the saved image
                return os.path.join('test_captures', f"test_capture_{timestamp}.jpg")
        except Exception as e:
            logger.error(f"Error taking test capture: {str(e)}")
            raise
    
    def create_video(self, session_dir=None, fps=10):
        """Create a video from the captured frames"""
        if session_dir is None:
            session_dir = self.current_session_dir
        
        if not session_dir or not os.path.exists(session_dir):
            logger.error(f"Session directory does not exist: {session_dir}")
            return False
        
        try:
            # Get all jpg files in the directory
            frames = sorted([f for f in os.listdir(session_dir) if f.endswith('.jpg')])
            
            if not frames:
                logger.error(f"No frames found in {session_dir}")
                return False
            
            # Create output video filename
            output_video = os.path.join(session_dir, f"timelapse_{Path(session_dir).name}.mp4")
            
            # Create a temporary file list for ffmpeg with absolute paths
            temp_list_file = os.path.join(session_dir, "frames_list.txt")
            with open(temp_list_file, 'w') as f:
                for frame in frames:
                    # Write the full absolute path to each frame
                    f.write(f"file '{os.path.abspath(os.path.join(session_dir, frame))}'\n")
            
            # Store progress information in a status file
            status_file = os.path.join(session_dir, "video_progress.json")
            
            # Create a lock file for this status file to prevent concurrent writes
            status_lock = threading.Lock()
            
            # Store the initial start time
            start_time = time.time()
            
            # Helper function to safely write progress data
            def write_progress_data(data):
                with status_lock:
                    try:
                        # If we're updating an existing file, try to preserve the original start_time
                        original_start_time = None
                        if os.path.exists(status_file):
                            try:
                                with open(status_file, 'r') as f:
                                    existing_data = json.load(f)
                                    if 'start_time' in existing_data:
                                        original_start_time = existing_data['start_time']
                            except:
                                pass
                        
                        # Use the original start time if available, otherwise use the one provided in data
                        if original_start_time is not None and 'start_time' in data:
                            data['start_time'] = original_start_time
                        
                        with open(status_file, 'w') as f:
                            json.dump(data, f, ensure_ascii=True)
                            f.flush()
                            os.fsync(f.fileno())  # Ensure data is written to disk
                    except Exception as e:
                        logger.error(f"Error writing progress data: {str(e)}")
            
            # Initial progress data
            write_progress_data({
                'status': 'starting',
                'progress': 0,
                'total_frames': len(frames),
                'start_time': start_time
            })
            
            # Use ffmpeg with absolute paths instead of changing directory
            try:
                # Use a longer timeout for larger sessions (10 minutes)
                # Use Popen instead of run to capture output in real-time
                process = subprocess.Popen([
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', temp_list_file,
                    '-r', str(fps),
                    '-c:v', 'libx264',
                    '-pix_fmt', 'yuv420p',
                    '-progress', 'pipe:1',  # Output progress information to stdout
                    '-y',
                    output_video
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                
                # Store the process in our tracking dictionary
                session_id = Path(session_dir).name
                with self.ffmpeg_processes_lock:
                    self.ffmpeg_processes[session_id] = {
                        'process': process,
                        'start_time': start_time,
                        'status_file': status_file,
                        'write_progress': write_progress_data
                    }
                
                # Track progress
                frame_count = 0
                total_frames = len(frames)
                
                # Start a thread to read stderr for progress updates
                def read_stderr():
                    nonlocal frame_count
                    for line in process.stderr:
                        if 'frame=' in line:
                            try:
                                # Extract frame number
                                frame_match = re.search(r'frame=\s*(\d+)', line)
                                if frame_match:
                                    frame_count = int(frame_match.group(1))
                                    progress = min(95, (frame_count / total_frames) * 100)
                                    
                                    # Update progress file
                                    write_progress_data({
                                        'status': 'processing',
                                        'progress': progress,
                                        'frame': frame_count,
                                        'total_frames': total_frames,
                                        'start_time': start_time,
                                        'elapsed_seconds': time.time() - start_time
                                    })
                            except Exception as e:
                                logger.error(f"Error parsing FFmpeg output: {str(e)}")
                
                # Start a thread to read stdout for progress updates
                def read_stdout():
                    nonlocal frame_count
                    for line in process.stdout:
                        if 'frame=' in line:
                            try:
                                # Extract frame number
                                frame_match = re.search(r'frame=\s*(\d+)', line)
                                if frame_match:
                                    frame_count = int(frame_match.group(1))
                                    progress = min(95, (frame_count / total_frames) * 100)
                                    
                                    # Update progress file
                                    write_progress_data({
                                        'status': 'processing',
                                        'progress': progress,
                                        'frame': frame_count,
                                        'total_frames': total_frames,
                                        'start_time': start_time,
                                        'elapsed_seconds': time.time() - start_time
                                    })
                            except Exception as e:
                                logger.error(f"Error parsing FFmpeg output: {str(e)}")
                
                # Start the threads
                stdout_thread = threading.Thread(target=read_stdout)
                stderr_thread = threading.Thread(target=read_stderr)
                stdout_thread.daemon = True
                stderr_thread.daemon = True
                stdout_thread.start()
                stderr_thread.start()
                
                # Wait for the process to complete with timeout
                try:
                    process.wait(timeout=600)
                    
                    # Check if process was terminated by cancel
                    with self.ffmpeg_processes_lock:
                        if session_id in self.ffmpeg_processes and self.ffmpeg_processes[session_id].get('cancelled', False):
                            write_progress_data({
                                'status': 'cancelled',
                                'progress': 0,
                                'total_frames': len(frames),
                                'start_time': start_time,
                                'end_time': time.time(),
                                'elapsed_seconds': time.time() - start_time
                            })
                            
                            # Clean up the process entry
                            if session_id in self.ffmpeg_processes:
                                del self.ffmpeg_processes[session_id]
                                
                            return {
                                'success': False,
                                'cancelled': True,
                                'message': 'Video creation was cancelled'
                            }
                except subprocess.TimeoutExpired:
                    # Process timed out, kill it
                    process.kill()
                    write_progress_data({
                        'status': 'failed',
                        'error': 'Process timed out after 10 minutes',
                        'start_time': start_time,
                        'end_time': time.time(),
                        'elapsed_seconds': time.time() - start_time
                    })
                    
                    # Clean up the process entry
                    with self.ffmpeg_processes_lock:
                        if session_id in self.ffmpeg_processes:
                            del self.ffmpeg_processes[session_id]
                            
                    return False
                
                # Clean up the process entry
                with self.ffmpeg_processes_lock:
                    if session_id in self.ffmpeg_processes:
                        del self.ffmpeg_processes[session_id]
                
                # Update status to completed
                write_progress_data({
                    'status': 'completed',
                    'progress': 100,
                    'total_frames': len(frames),
                    'start_time': start_time,
                    'end_time': time.time(),
                    'elapsed_seconds': time.time() - start_time
                })
                    
            except subprocess.SubprocessError as e:
                logger.error(f"FFmpeg error: {str(e)}")
                # Update status to failed
                write_progress_data({
                    'status': 'failed',
                    'error': str(e),
                    'start_time': start_time,
                    'end_time': time.time(),
                    'elapsed_seconds': time.time() - start_time
                })
                
                # Clean up the process entry
                session_id = Path(session_dir).name
                with self.ffmpeg_processes_lock:
                    if session_id in self.ffmpeg_processes:
                        del self.ffmpeg_processes[session_id]
                        
                return False
            
            # Clean up the temporary file
            try:
                os.remove(temp_list_file)
            except:
                pass
            
            logger.info(f"Created timelapse video: {output_video}")
            return {
                'success': True,
                'video_path': output_video,
                'frame_count': len(frames)
            }
        except Exception as e:
            logger.error(f"Error creating video: {str(e)}")
            return False
            
    def cancel_video(self, session_id):
        """Cancel an ongoing video creation process"""
        with self.ffmpeg_processes_lock:
            if session_id in self.ffmpeg_processes:
                process_info = self.ffmpeg_processes[session_id]
                process = process_info.get('process')
                
                if process and process.poll() is None:  # Process is still running
                    try:
                        # Mark as cancelled
                        self.ffmpeg_processes[session_id]['cancelled'] = True
                        
                        # Terminate the process
                        process.terminate()
                        
                        # Wait a bit for graceful termination
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            # Force kill if it doesn't terminate gracefully
                            process.kill()
                        
                        # Update the status file
                        write_progress = process_info.get('write_progress')
                        if write_progress:
                            write_progress({
                                'status': 'cancelled',
                                'progress': 0,
                                'start_time': process_info.get('start_time', time.time()),
                                'end_time': time.time(),
                                'elapsed_seconds': time.time() - process_info.get('start_time', time.time()),
                                'error': 'Video creation was cancelled by user'
                            })
                        
                        logger.info(f"Cancelled video creation for session {session_id}")
                        return True
                    except Exception as e:
                        logger.error(f"Error cancelling video creation: {str(e)}")
                        return False
                else:
                    # Process already completed or not found
                    logger.warning(f"No active video creation process found for session {session_id}")
                    return False
            else:
                logger.warning(f"No video creation process found for session {session_id}")
                return False
    
    def list_sessions(self):
        """List all timelapse sessions"""
        sessions = []
        
        try:
            for item in os.listdir(self.timelapse_dir):
                session_path = os.path.join(self.timelapse_dir, item)
                if os.path.isdir(session_path) and item.startswith('timelapse_'):
                    # Get session info
                    info_file = os.path.join(session_path, 'session_info.json')
                    info = {}
                    if os.path.exists(info_file):
                        with open(info_file, 'r') as f:
                            info = json.load(f)
                    
                    # Count frames
                    frames = [f for f in os.listdir(session_path) if f.endswith('.jpg')]
                    frame_count = len(frames)
                    
                    # Check if video exists
                    video_file = os.path.join(session_path, f"timelapse_{item}.mp4")
                    has_video = os.path.exists(video_file)
                    
                    # Get thumbnail (first frame)
                    thumbnail = None
                    if frames:
                        thumbnail = os.path.join(item, sorted(frames)[0])
                    
                    sessions.append({
                        'id': item,
                        'path': session_path,
                        'info': info,
                        'frame_count': frame_count,
                        'has_video': has_video,
                        'thumbnail': thumbnail
                    })
        except Exception as e:
            logger.error(f"Error listing sessions: {str(e)}")
        
        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x['id'], reverse=True)
        return sessions
    
    def get_session_frames(self, session_id):
        """Get all frames for a session"""
        session_path = os.path.join(self.timelapse_dir, session_id)
        if not os.path.exists(session_path):
            return []
        
        frames = []
        try:
            for item in os.listdir(session_path):
                if item.endswith('.jpg') and item.startswith('frame_'):
                    frames.append({
                        'path': os.path.join(session_id, item),
                        'filename': item
                    })
        except Exception as e:
            logger.error(f"Error getting session frames: {str(e)}")
        
        # Sort by frame number
        frames.sort(key=lambda x: x['filename'])
        return frames
    
    def get_status(self):
        """Get current timelapse status"""
        with self.lock:
            status = {
                'is_capturing': self.is_capturing,
                'current_session': os.path.basename(self.current_session_dir) if self.current_session_dir else None,
                'interval': self.interval,
                'auto_mode': self.auto_mode,
                'selected_camera': self.selected_camera,
                'available_cameras': self.available_cameras
            }
            
            # Add latest frame if we have an active session
            if self.is_capturing and self.current_session_dir:
                try:
                    # Get the session ID
                    session_id = os.path.basename(self.current_session_dir)
                    
                    # Get frames for this session
                    frames = self.get_session_frames(session_id)
                    
                    # If we have frames, get the latest one
                    if frames and len(frames) > 0:
                        latest_frame = frames[-1]
                        status['latest_frame'] = latest_frame['path']
                except Exception as e:
                    logger.error(f"Error getting latest frame: {str(e)}")
            
            return status
    
    def activity_started(self, activity_file=None):
        """Notify that a activity has started (for auto mode)"""
        if self.auto_mode and not self.is_capturing:
            logger.info("Auto-starting timelapse due to activity start")
            self.start_timelapse(activity_file=activity_file)
    
    def activity_stopped(self):
        """Notify that a activity has stopped (for auto mode)"""
        if self.auto_mode and self.is_capturing:
            logger.info("Auto-stopping timelapse due to activity stop")
            self.stop_timelapse()
            
    def delete_session(self, session_id):
        """Delete a timelapse session"""
        try:
            # Validate session_id to prevent directory traversal
            if not session_id or '..' in session_id or not session_id.startswith('timelapse_'):
                logger.error(f"Invalid session ID: {session_id}")
                return False
            
            session_dir = os.path.join(self.timelapse_dir, session_id)
            
            # Check if directory exists
            if not os.path.exists(session_dir) or not os.path.isdir(session_dir):
                logger.error(f"Session not found: {session_id}")
                return False
            
            # Delete all files in the directory
            for file in os.listdir(session_dir):
                file_path = os.path.join(session_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {str(e)}")
            
            # Delete the directory
            os.rmdir(session_dir)
            
            return True
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {str(e)}")
            return False

    def capture_frame_to_base64(self, camera=None, fast_mode=True):
        """Capture a single frame and return it as a base64 encoded string without saving to disk
        
        Args:
            camera: Camera identifier (index, string, or device path)
            fast_mode: If True, skip image processing for faster capture
        
        Returns:
            Base64 encoded image string
        """
        return self.capture_single_frame(camera=camera, return_base64=True, fast_mode=fast_mode)
        
    def pre_initialize_camera(self, camera=None):
        """Pre-initialize a camera without capturing a frame
        
        This method initializes the camera and adds it to the cache
        so that subsequent capture operations will be faster.
        
        Args:
            camera: Camera identifier (index, string, or device path)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get camera index using the helper method
            camera_index = self._get_camera_index(camera)
            
            logger.debug(f"Pre-initializing camera with index: {camera_index}")
            
            # Get camera from cache or create new one - this will initialize and cache it
            self._get_camera(camera_index)
            
            return True
        except Exception as e:
            logger.error(f"Error pre-initializing camera: {str(e)}")
            return False
        
    def cleanup(self):
        """Release all resources when application is shutting down"""
        logger.info("Cleaning up WebcamController resources")
        
        # Stop any active timelapse
        if self.is_capturing:
            self.stop_timelapse()
            
        # Release all cached cameras
        with self.camera_cache_lock:
            for camera_id, cam in list(self.camera_cache.items()):
                logger.debug(f"Releasing camera {camera_id}")
                try:
                    cam.release()
                except Exception as e:
                    logger.error(f"Error releasing camera {camera_id}: {str(e)}")
            
            # Clear the cache
            self.camera_cache.clear()
            self.camera_last_used.clear()
        
        logger.info("WebcamController cleanup complete")

    def set_resolution(self, width, height):
        """Set camera resolution
        
        Args:
            width: Width in pixels
            height: Height in pixels
            
        Returns:
            Boolean indicating success
        """
        try:
            # Store resolution in settings
            resolution_str = f"{width}x{height}"
            self.camera_settings['resolution'] = resolution_str
            
            # Apply to any cached cameras
            with self.camera_cache_lock:
                for camera_key, camera in self.camera_cache.items():
                    if camera.isOpened():
                        actual_width, actual_height = self._set_camera_resolution(camera, resolution_str)
                        
                        # Update the resolution in settings if it's different from requested
                        if actual_width != width or actual_height != height:
                            self.camera_settings['resolution'] = f"{actual_width}x{actual_height}"
            
            return True
        except Exception as e:
            logger.error(f"Error setting resolution: {str(e)}")
            return False

# Create a singleton instance
webcam_controller = WebcamController() 