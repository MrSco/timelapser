import os
import logging
import atexit
import signal
import json
from flask import Flask, jsonify, request, send_from_directory, render_template
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
                
                return state
        return {'auto_mode': False}
    except Exception as e:
        logger.error(f"Error loading state: {str(e)}")
        return {'auto_mode': False}

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

# Initialize activity monitor
poll_interval = int(os.getenv('POLL_INTERVAL', '5'))
activity_monitor = ActivityMonitor(webcam_controller, poll_interval=poll_interval)

# Start activity monitor
activity_monitor.start()

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
            return jsonify({"success": True})
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
        return jsonify({"frames": frames})
    except Exception as e:
        logger.error(f"Error getting session frames: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/create_video', methods=['POST'])
def create_timelapse_video():
    """Create a timelapse video from captured frames"""
    try:
        data = request.json
        session_id = data.get('session_id')
        fps = data.get('fps', 10)
        
        # Validate session_id
        if not session_id:
            return jsonify({"success": False, "error": "Session ID is required"}), 400
        
        # Create session directory path
        session_dir = os.path.join(timelapse_dir, session_id)
        
        # Create video
        result = webcam_controller.create_video(session_dir, fps)
        
        if result and isinstance(result, dict) and result.get('success'):
            video_path = result.get('video_path')
            return jsonify({
                "success": True,
                "video_path": os.path.basename(video_path),
                "video_url": f"/video/{session_id}",
                "frame_count": result.get('frame_count', 0)
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
    try:
        # Use the same naming convention as in create_video method
        video_filename = f"timelapse_{session_id}.mp4"
        # Serve the video file from the session directory
        return send_from_directory(os.path.join(timelapse_dir, session_id), video_filename)
    except Exception as e:
        logger.error(f"Error serving video: {str(e)}")
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
    except Exception as e:
        logger.error(f"Error capturing test frame: {str(e)}")
        return jsonify({"error": str(e)}), 500

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
        brightness = data.get('brightness', 0.5)
        contrast = data.get('contrast', 1.0)
        exposure = data.get('exposure', 0.5)
        
        # Update the camera settings in the webcam controller
        webcam_controller.camera_settings = {
            'brightness': float(brightness),
            'contrast': float(contrast),
            'exposure': float(exposure)
        }
        
        logger.info(f"Updated camera settings: {webcam_controller.camera_settings}")
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating camera settings: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

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
                'camera_settings': webcam_controller.camera_settings
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
            
            # Save state to file
            state = {
                'auto_mode': webcam_controller.auto_mode,
                'camera': webcam_controller.selected_camera,
                'interval': webcam_controller.interval,
                'camera_settings': webcam_controller.camera_settings
            }
            save_state(state)
            
            return jsonify({"success": True, "state": state})
    except Exception as e:
        logger.error(f"Error managing state: {str(e)}")
        return jsonify({"error": str(e)}), 500

def on_exit():
    """Function to execute on application shutdown"""
    logger.info("Shutting down Timelapser gracefully")
    
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