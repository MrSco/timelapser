import os
import logging
import atexit
import signal
import json
import time
from flask import Flask, jsonify, request, send_from_directory, send_file, render_template
from dotenv import load_dotenv
from webcam_controller import WebcamController
from activity_monitor import ActivityMonitor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__, static_folder='static')

# Initialize webcam controller
timelapse_dir = os.getenv('TIMELAPSE_DIR', './timelapses')
webcam_controller = WebcamController(timelapse_dir=timelapse_dir)

# State file path
state_file_path = 'state.json'

# Initialize activity monitor
poll_interval = int(os.getenv('POLL_INTERVAL', '5'))
activity_monitor = ActivityMonitor(webcam_controller, poll_interval=poll_interval)

# Load state from file
def load_state():
    """Load state from state.json file"""
    try:
        if os.path.exists(state_file_path):
            with open(state_file_path, 'r') as f:
                state = json.load(f)
                logger.info(f"Loaded state: {state}")
                
                # Apply state to webcam controller
                if 'auto_mode' in state:
                    webcam_controller.auto_mode = state['auto_mode']
                
                if 'camera' in state:
                    webcam_controller.selected_camera = state['camera']
                
                if 'interval' in state:
                    webcam_controller.interval = state['interval']
                
                if 'camera_settings' in state:
                    webcam_controller.camera_settings.update(state['camera_settings'])
                
                # Apply ignored patterns to activity monitor
                if 'ignored_patterns' in state:
                    activity_monitor.set_ignored_patterns(state['ignored_patterns'])
                    logger.info(f"Loaded ignored patterns from state: {state['ignored_patterns']}")
                
                return state
        return {'auto_mode': False, 'ignored_patterns': []}
    except Exception as e:
        logger.error(f"Error loading state: {str(e)}")
        return {'auto_mode': False, 'ignored_patterns': []}

# Save state to file
def save_state(state):
    """Save state to state.json file"""
    try:
        with open(state_file_path, 'w') as f:
            json.dump(state, f)
        logger.info(f"Saved state: {state}")
        return True
    except Exception as e:
        logger.error(f"Error saving state: {str(e)}")
        return False

# Load initial state
initial_state = load_state()

# Only start activity monitor if auto_mode is enabled in the initial state
if initial_state and initial_state.get('auto_mode', False):
    logger.info("Auto mode enabled in initial state, starting activity monitor")
    activity_monitor.start()
else:
    logger.info("Auto mode disabled in initial state, activity monitor not started")


@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/status', methods=['GET'])
def get_status():
    """Get current timelapse status"""
    try:
        status = webcam_controller.get_status()
        
        # Add current file information from activity monitor if available
        if hasattr(activity_monitor, 'last_current_file') and activity_monitor.last_current_file:
            status['current_file'] = activity_monitor.last_current_file
            
            # Add information about whether this activity is being ignored
            if activity_monitor.is_ignored_activity(activity_monitor.last_current_file):
                status['is_ignored'] = True
            else:
                status['is_ignored'] = False
        
        # Include sessions data to avoid a separate API call
        status['sessions'] = webcam_controller.list_sessions()
        
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting timelapse status: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/cameras', methods=['GET'])
def list_cameras():
    """List available cameras"""
    try:
        cameras = webcam_controller.scan_cameras()
        return jsonify({"cameras": cameras})
    except Exception as e:
        logger.error(f"Error listing cameras: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/pre_initialize_camera', methods=['POST'])
def pre_initialize_camera():
    """Pre-initialize a camera for faster first capture"""
    try:
        data = request.json
        camera = data.get('camera')
        
        # Pre-initialize the camera
        success = webcam_controller.pre_initialize_camera(camera)
        
        return jsonify({"success": success})
    except Exception as e:
        logger.error(f"Error pre-initializing camera: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/start', methods=['POST'])
def start_timelapse():
    """Start timelapse capture"""
    try:
        data = request.json
        camera = data.get('camera')
        interval = data.get('interval')
        auto_mode = data.get('auto_mode')
        
        result = webcam_controller.start_timelapse(camera, interval, auto_mode)
        if result:
            # Get the current session ID from the webcam controller
            current_session = os.path.basename(webcam_controller.current_session_dir) if webcam_controller.current_session_dir else None
            return jsonify({"success": True, "session_id": current_session})
        else:
            return jsonify({"success": False, "error": "Failed to start timelapse"}), 400
    except Exception as e:
        logger.error(f"Error starting timelapse: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop_timelapse():
    """Stop timelapse capture"""
    try:
        result = webcam_controller.stop_timelapse()
        if result:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "No timelapse running"}), 400
    except Exception as e:
        logger.error(f"Error stopping timelapse: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/sessions', methods=['GET'])
def list_timelapse_sessions():
    """List all timelapse sessions"""
    try:
        sessions = webcam_controller.list_sessions()
        return jsonify({"sessions": sessions})
    except Exception as e:
        logger.error(f"Error listing timelapse sessions: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/frames/<session_id>', methods=['GET'])
def get_session_frames(session_id):
    """Get frames for a specific session"""
    try:
        frames = webcam_controller.get_session_frames(session_id)
        return jsonify({"success": True, "frames": frames})
    except Exception as e:
        logger.error(f"Error getting session frames: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/create_video', methods=['POST'])
def create_timelapse_video():
    """Create a timelapse video from captured frames"""
    try:
        data = request.json
        session_id = data.get('session_id')
        fps = data.get('fps', 30)
        
        # Validate session_id
        if not session_id:
            return jsonify({"success": False, "error": "Session ID is required"}), 400
        
        # Check if this is the active session
        current_session = os.path.basename(webcam_controller.current_session_dir) if webcam_controller.current_session_dir else None
        if session_id == current_session and webcam_controller.is_capturing:
            return jsonify({"success": False, "error": "Cannot create video while capture is in progress"}), 400
        
        # Create session directory path
        session_dir = os.path.join(timelapse_dir, session_id)
        
        # Check if video already exists
        video_file = os.path.join(session_dir, f"timelapse_{session_id}.mp4")
        video_existed = os.path.exists(video_file)
        
        # Create video
        result = webcam_controller.create_video(session_dir, fps)
        
        if result and isinstance(result, dict) and result.get('success'):
            video_path = result.get('video_path')
            return jsonify({
                "success": True,
                "video_path": os.path.basename(video_path),
                "video_url": f"/video/{session_id}",
                "frame_count": result.get('frame_count', 0),
                "video_existed": video_existed
            })
        elif result and isinstance(result, dict) and result.get('cancelled'):
            return jsonify({
                "success": False,
                "cancelled": True,
                "message": result.get('message', 'Video creation was cancelled')
            })
        else:
            return jsonify({"success": False, "error": "Failed to create video"}), 400
    except Exception as e:
        logger.error(f"Error creating timelapse video: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/image/<path:filename>', methods=['GET'])
def get_timelapse_image(filename):
    """Serve a timelapse image"""
    try:
        # Split the path into directory and filename
        parts = filename.split('/')
        if len(parts) < 2:
            return jsonify({"error": "Invalid image path"}), 400
        
        session_id = parts[0]
        image_name = parts[-1]
        
        # Serve the file from the timelapse directory
        return send_from_directory(os.path.join(timelapse_dir, session_id), image_name)
    except Exception as e:
        logger.error(f"Error serving image: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/video/<session_id>', methods=['GET'])
def get_timelapse_video(session_id):
    """Serve a timelapse video"""
    video_path = os.path.join(timelapse_dir, session_id, f"timelapse_{session_id}.mp4")
    if os.path.exists(video_path):
        return send_file(video_path, mimetype='video/mp4')
    else:
        return jsonify({"error": "Video not found"}), 404

@app.route('/video_progress/<session_id>', methods=['GET'])
def get_video_progress(session_id):
    """Get the progress of video creation for a session"""
    try:
        progress_file = os.path.join(timelapse_dir, session_id, "video_progress.json")
        if os.path.exists(progress_file):
            try:
                # Read the file content first
                with open(progress_file, 'r') as f:
                    file_content = f.read().strip()
                
                # Try to parse the JSON
                try:
                    progress_data = json.loads(file_content)
                except json.JSONDecodeError as json_err:
                    logger.error(f"JSON decode error in progress file: {str(json_err)}")
                    logger.debug(f"Raw content: {file_content}")
                    
                    # Try to extract valid JSON if possible
                    try:
                        # Look for a complete JSON object by finding matching braces
                        import re
                        match = re.search(r'(\{.*\})', file_content)
                        if match:
                            progress_data = json.loads(match.group(1))
                        else:
                            # Return a default progress object
                            return jsonify({"status": "processing", "progress": 50, "error": "Invalid progress data format"})
                    except Exception as extract_err:
                        logger.error(f"Failed to extract valid JSON: {str(extract_err)}")
                        return jsonify({"status": "processing", "progress": 50, "error": "Invalid progress data"})
                
                # Calculate elapsed time if not already provided
                if 'start_time' in progress_data and 'elapsed_seconds' not in progress_data:
                    # Don't calculate elapsed time for completed videos
                    if progress_data.get('status') != 'completed':
                        current_time = time.time()
                        start_time = progress_data['start_time']
                        progress_data['elapsed_seconds'] = current_time - start_time
                        logger.debug(f"Calculated elapsed time: {progress_data['elapsed_seconds']}s")
                
                return jsonify(progress_data)
            except Exception as file_err:
                logger.error(f"Error reading progress file: {str(file_err)}")
                return jsonify({"status": "unknown", "progress": 0, "error": "Error reading progress data"})
        else:
            return jsonify({"status": "unknown", "progress": 0}), 404
    except Exception as e:
        logger.error(f"Error getting video progress: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/test_capture', methods=['POST'])
def test_timelapse_capture():
    """Capture a test frame and return it as base64"""
    try:
        data = request.json
        if not data:
            logger.error("No JSON data received in test_capture request")
            return jsonify({"success": False, "error": "No JSON data received"}), 400
        
        camera = data.get('camera')
        logger.info(f"Test capture requested for camera: {camera}")
        
        # Get available cameras to help with troubleshooting
        available_cameras = webcam_controller.scan_cameras()
        
        # Capture test frame
        try:
            base64_image = webcam_controller.test_capture(camera)
            
            if base64_image:
                logger.info(f"Successfully captured test frame from camera: {camera}")
                return jsonify({
                    "success": True,
                    "image": base64_image,
                    "available_cameras": available_cameras
                })
            else:
                logger.error(f"Failed to capture test frame from camera: {camera}. Available cameras: {available_cameras}")
                
                return jsonify({
                    "success": False, 
                    "error": f"Failed to capture test frame from camera: {camera}",
                    "available_cameras": available_cameras
                }), 400
        except Exception as capture_error:
            error_str = str(capture_error)
            logger.error(f"Error in test capture: {error_str}")
            
            # Check for common errors and provide helpful messages
            if "Assertion failed" in error_str and "Mat" in error_str:
                # This is likely a resolution issue
                current_resolution = webcam_controller.camera_settings.get('resolution', 'unknown')
                error_message = f"Camera doesn't support the current resolution ({current_resolution}). Try a lower resolution in Camera Settings."
                return jsonify({"success": False, "error": error_message}), 400
            else:
                return jsonify({"success": False, "error": error_str}), 400
    except Exception as e:
        logger.error(f"Error capturing test frame: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/delete/<session_id>', methods=['DELETE'])
def delete_timelapse_session(session_id):
    """Delete a timelapse session"""
    try:
        result = webcam_controller.delete_session(session_id)
        if result:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Failed to delete session"}), 400
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/update_camera_settings', methods=['POST'])
def update_camera_settings():
    """Update camera settings"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['brightness', 'contrast', 'exposure']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'})
        
        # Update camera settings
        webcam_controller.camera_settings = {
            'brightness': float(data['brightness']),
            'contrast': float(data['contrast']),
            'exposure': float(data['exposure'])
        }
        
        # Track if resolution was adjusted
        actual_resolution = None
        
        # Update resolution if provided
        if 'width' in data and 'height' in data:
            try:
                width = int(data['width'])
                height = int(data['height'])
                
                # Set resolution in webcam controller
                webcam_controller.set_resolution(width, height)
                
                # Get the actual resolution that was set (may be different from requested)
                actual_resolution = webcam_controller.camera_settings.get('resolution')
                
                logger.info(f"Updated camera resolution to {actual_resolution}")
            except Exception as e:
                logger.error(f"Error setting resolution: {str(e)}")
                # Continue with other settings even if resolution fails
        
        logger.info(f"Updated camera settings: {webcam_controller.camera_settings}")
        
        response = {'success': True}
        if actual_resolution:
            response['actual_resolution'] = actual_resolution
            
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error updating camera settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/state', methods=['GET', 'POST'])
def manage_state():
    """Get or update application state"""
    try:
        if request.method == 'GET':
            # Return current state
            state = {
                'auto_mode': webcam_controller.auto_mode,
                'camera': webcam_controller.selected_camera,
                'interval': webcam_controller.interval,
                'is_capturing': webcam_controller.is_capturing,
                'current_session': os.path.basename(webcam_controller.current_session_dir) if webcam_controller.current_session_dir else None,
                'camera_settings': webcam_controller.camera_settings,
                'ignored_patterns': activity_monitor.ignored_patterns
            }
            return jsonify(state)
        else:
            # Update state
            data = request.json
            
            # Update webcam controller state
            if 'auto_mode' in data:
                webcam_controller.auto_mode = data['auto_mode']
            
            if 'camera' in data:
                webcam_controller.selected_camera = data['camera']
            
            if 'interval' in data:
                webcam_controller.interval = data['interval']
            
            if 'camera_settings' in data:
                webcam_controller.camera_settings.update(data['camera_settings'])
            
            # Update ignored patterns
            if 'ignored_patterns' in data:
                activity_monitor.set_ignored_patterns(data['ignored_patterns'])
            
            # Save state to file
            state = {
                'auto_mode': webcam_controller.auto_mode,
                'camera': webcam_controller.selected_camera,
                'interval': webcam_controller.interval,
                'is_capturing': webcam_controller.is_capturing,
                'current_session': os.path.basename(webcam_controller.current_session_dir) if webcam_controller.current_session_dir else None,
                'camera_settings': webcam_controller.camera_settings,
                'ignored_patterns': activity_monitor.ignored_patterns
            }
            save_state(state)

            if webcam_controller.auto_mode:
                activity_monitor.start()
            else:
                activity_monitor.stop()
            
            return jsonify({"success": True, "state": state})
    except Exception as e:
        logger.error(f"Error managing state: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/cancel_video/<session_id>', methods=['POST'])
def cancel_video_creation(session_id):
    """Cancel an ongoing video creation process"""
    try:
        if not session_id:
            return jsonify({"success": False, "error": "Session ID is required"}), 400
            
        # Call the cancel method
        result = webcam_controller.cancel_video(session_id)
        
        if result:
            return jsonify({
                "success": True,
                "message": "Video creation cancelled successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "No active video creation process found for this session"
            }), 404
    except Exception as e:
        logger.error(f"Error cancelling video creation: {str(e)}")
        return jsonify({"error": str(e)}), 500

def on_exit():
    """Function to execute on application shutdown"""
    logger.info("Shutting down Timelapser gracefully")
    
    # Save current state
    state = {
        'auto_mode': webcam_controller.auto_mode,
        'camera': webcam_controller.selected_camera,
        'interval': webcam_controller.interval,
        'is_capturing': webcam_controller.is_capturing,
        'current_session': os.path.basename(webcam_controller.current_session_dir) if webcam_controller.current_session_dir else None,
        'camera_settings': webcam_controller.camera_settings,
        'ignored_patterns': activity_monitor.ignored_patterns
    }
    save_state(state)
    logger.info("Final state saved")
    
    # Stop activity monitor
    activity_monitor.stop()
    
    # Clean up webcam controller resources
    webcam_controller.cleanup()
    
    logger.info("Shutdown complete")

def signal_handler(sig, frame):
    """Signal handler for graceful shutdown"""
    logger.info(f"Received signal {sig}, shutting down...")
    on_exit()
    os._exit(0)

def main():
    """Main entry point for the application"""
    logger.info("Starting Timelapser application...")
    
    # Register the on_exit function
    atexit.register(on_exit)
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Get port from environment or use default
    port = int(os.getenv('PORT', '5001'))
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main() 