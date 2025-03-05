// DOM Elements
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const refreshStatusButton = document.getElementById('refresh-status');
const currentSession = document.getElementById('current-session');
const autoModeStatus = document.getElementById('auto-mode-status');
const cameraSelect = document.getElementById('camera-select');
const refreshCamerasButton = document.getElementById('refresh-cameras');
const intervalInput = document.getElementById('interval-input');
const autoModeCheckbox = document.getElementById('auto-mode-checkbox');
const startButton = document.getElementById('start-button');
const stopButton = document.getElementById('stop-button');
const testButton = document.getElementById('test-button');
const brightnessSlider = document.getElementById('brightness-slider');
const brightnessValue = document.getElementById('brightness-value');
const contrastSlider = document.getElementById('contrast-slider');
const contrastValue = document.getElementById('contrast-value');
const exposureSlider = document.getElementById('exposure-slider');
const exposureValue = document.getElementById('exposure-value');
const applySettingsButton = document.getElementById('apply-settings-button');
const resetSettingsButton = document.getElementById('reset-settings-button');
const previewContainer = document.getElementById('preview-container');
const previewImage = document.getElementById('preview-image');
const sessionsContainer = document.getElementById('sessions-container');
const sessionDetails = document.getElementById('session-details');
const sessionName = document.getElementById('session-name');
const backButton = document.getElementById('back-button');
const fpsInput = document.getElementById('fps-input');
const createVideoButton = document.getElementById('create-video-button');
const framesContainer = document.getElementById('frames-container');
const videoContainer = document.getElementById('video-container');
const videoPlayer = document.getElementById('video-player');

// Current session ID for details view
let currentSessionId = null;

// Variable to store the polling interval ID
let statusPollingInterval = null;

// Application state
let appState = {
    auto_mode: false,
    camera: null,
    interval: 5,
    camera_settings: {
        brightness: 0.5,
        contrast: 1.0,
        exposure: 0.5
    }
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Fetch application state
    fetchState();
    
    // Fetch initial status
    fetchStatus();
    
    // Fetch available cameras
    fetchCameras();
    
    // Fetch timelapse sessions
    fetchSessions();
    
    // Set up event listeners
    setupEventListeners();
    
    // Set up regular status polling for UI updates
    setupStatusPolling();
});

// Fetch application state
async function fetchState() {
    try {
        const response = await fetch('/state');
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const state = await response.json();
        
        // Validate state data
        if (state) {
            // Make sure camera is not "undefined" string
            if (state.camera === "undefined") {
                state.camera = null;
            }
            
            // Update appState with valid values
            appState = {
                auto_mode: state.auto_mode !== undefined ? state.auto_mode : appState.auto_mode,
                camera: state.camera !== undefined ? state.camera : appState.camera,
                interval: state.interval !== undefined ? state.interval : appState.interval,
                camera_settings: state.camera_settings || appState.camera_settings
            };
            
            // Apply state to UI
            applyStateToUI();
        }
    } catch (error) {
        console.error('Error fetching state:', error);
        // Continue with default state
    }
}

// Apply state to UI elements
function applyStateToUI() {
    // Set auto mode checkbox
    autoModeCheckbox.checked = appState.auto_mode;
    // Update the auto mode status text
    autoModeStatus.textContent = `Auto mode: ${appState.auto_mode ? 'Enabled' : 'Disabled'}`;
    // Set interval input
    if (appState.interval) {
        intervalInput.value = appState.interval;
    }
    
    // Set camera settings sliders
    if (appState.camera_settings) {
        if (appState.camera_settings.brightness !== undefined) {
            brightnessSlider.value = appState.camera_settings.brightness;
            brightnessValue.textContent = appState.camera_settings.brightness;
        }
        
        if (appState.camera_settings.contrast !== undefined) {
            contrastSlider.value = appState.camera_settings.contrast;
            contrastValue.textContent = appState.camera_settings.contrast;
        }
        
        if (appState.camera_settings.exposure !== undefined) {
            exposureSlider.value = appState.camera_settings.exposure;
            exposureValue.textContent = appState.camera_settings.exposure;
        }
    }
}

// Save application state
async function saveState() {
    try {
        const response = await fetch('/state', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(appState)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const result = await response.json();
        console.log('State saved:', result);
    } catch (error) {
        console.error('Error saving state:', error);
    }
}

// Set up event listeners
function setupEventListeners() {
    // Camera refresh button
    refreshCamerasButton.addEventListener('click', fetchCameras);
    
    // Status refresh button
    refreshStatusButton.addEventListener('click', fetchStatus);
    
    // Start button
    startButton.addEventListener('click', startTimelapse);
    
    // Stop button
    stopButton.addEventListener('click', stopTimelapse);
    
    // Test button
    testButton.addEventListener('click', testCapture);
    
    // Auto mode checkbox
    autoModeCheckbox.addEventListener('change', () => {
        // Update state for external API polling
        appState.auto_mode = autoModeCheckbox.checked;
        
        // Update the auto mode status text
        autoModeStatus.textContent = `Auto mode: ${appState.auto_mode ? 'Enabled' : 'Disabled'}`;
        saveState();
    });
    
    // Interval input
    intervalInput.addEventListener('change', () => {
        // Update state
        appState.interval = parseInt(intervalInput.value);
        saveState();
    });
    
    // Camera settings sliders
    brightnessSlider.addEventListener('input', updateSliderValue);
    contrastSlider.addEventListener('input', updateSliderValue);
    exposureSlider.addEventListener('input', updateSliderValue);
    
    // Apply settings button
    applySettingsButton.addEventListener('click', applyCameraSettings);
    
    // Reset settings button
    resetSettingsButton.addEventListener('click', resetCameraSettings);
    
    // Back button
    backButton.addEventListener('click', () => {
        sessionDetails.classList.add('hidden');
        fetchSessions();
    });
    
    // Create video button
    createVideoButton.addEventListener('click', createVideo);
    
    // Add change event listener to camera select
    cameraSelect.addEventListener('change', () => {
        appState.camera = cameraSelect.value;
        saveState();
        // Pre-initialize the selected camera
        preInitializeCamera(cameraSelect.value);
    });
}

// Setup regular status polling for UI updates
function setupStatusPolling() {
    // Always poll the status endpoint to keep the UI updated
    // This is separate from the auto_mode feature which controls external API polling
    statusPollingInterval = setInterval(fetchStatus, 5000);
    console.log('UI status polling enabled');
}

// Fetch timelapse status
async function fetchStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        
        // Update status indicator
        if (data.is_capturing) {
            statusIndicator.classList.remove('status-inactive');
            statusIndicator.classList.add('status-active');
            statusText.textContent = 'Capturing';
            stopButton.disabled = false;
            startButton.disabled = true;
        } else {
            statusIndicator.classList.remove('status-active');
            statusIndicator.classList.add('status-inactive');
            statusText.textContent = 'Not capturing';
            stopButton.disabled = true;
            startButton.disabled = false;
        }
        
        // Update current session
        if (data.current_session) {
            currentSession.textContent = `Current session: ${data.current_session}`;
            
            // Add current file information if available
            if (data.current_file) {
                currentSession.textContent += ` (File: ${data.current_file})`;
            }
        } else {
            currentSession.textContent = 'No active session';
        }
        
        // Only update auto_mode if it's different from what we have
        // This prevents overriding user changes with server state
        if (data.auto_mode !== appState.auto_mode) {
            // Directly update UI without saving state again
            // This avoids redundant state saves when the server updates auto_mode
            appState.auto_mode = data.auto_mode;
            autoModeCheckbox.checked = data.auto_mode;
            autoModeStatus.textContent = `Auto mode: ${data.auto_mode ? 'Enabled' : 'Disabled'}`;
            console.log(`External API polling auto mode ${data.auto_mode ? 'enabled' : 'disabled'} (from server)`);
        }
        
        // Update interval if it's different
        if (data.interval && data.interval !== parseInt(intervalInput.value)) {
            intervalInput.value = data.interval;
            appState.interval = data.interval;
            // Don't save state here, as this is just syncing with server
        }
        
        // Update camera selection if not already set
        if (data.selected_camera && (!cameraSelect.value || cameraSelect.value !== data.selected_camera)) {
            // Find the option with this value
            const options = Array.from(cameraSelect.options);
            const option = options.find(opt => opt.value === data.selected_camera);
            
            if (option) {
                cameraSelect.value = data.selected_camera;
                appState.camera = data.selected_camera;
                // Don't save state here, as this is just syncing with server
            }
        }
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

// Fetch available cameras
async function fetchCameras() {
    try {
        const response = await fetch('/cameras');
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Clear existing options
        cameraSelect.innerHTML = '';
        
        // Add camera options
        data.cameras.forEach(camera => {
            const option = document.createElement('option');
            
            // Handle both object format and simple string format
            if (typeof camera === 'object' && camera.id) {
                option.value = camera.id;
                option.textContent = camera.name || camera.id;
            } else {
                option.value = camera;
                option.textContent = camera;
            }
            
            // Select the camera from state if available
            if (appState.camera && appState.camera === option.value) {
                option.selected = true;
            }
            
            cameraSelect.appendChild(option);
        });
        
        // Update state with selected camera
        if (cameraSelect.value) {
            appState.camera = cameraSelect.value;
            saveState();
            // Pre-initialize the initially selected camera
            preInitializeCamera(cameraSelect.value);
        }
        
    } catch (error) {
        console.error('Error fetching cameras:', error);
        alert(`Error fetching cameras: ${error.message}`);
    }
}

// Start timelapse
async function startTimelapse() {
    try {
        // Make sure we have a valid camera selected
        const selectedCamera = cameraSelect.value || appState.camera;
        if (!selectedCamera) {
            alert('Please select a camera first');
            return;
        }
        
        // Get the current auto_mode state
        const autoMode = appState.auto_mode;
        
        const response = await fetch('/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                camera: selectedCamera,
                interval: appState.interval || parseInt(intervalInput.value),
                auto_mode: autoMode
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            // Update UI
            statusIndicator.classList.remove('status-inactive');
            statusIndicator.classList.add('status-active');
            statusText.textContent = 'Capturing';
            startButton.disabled = true;
            stopButton.disabled = false;
            
            // Update current session
            currentSession.textContent = `Current session: ${result.session_id}`;
            
            // Fetch status to update UI
            fetchStatus();
            
            console.log(`Started timelapse with auto_mode: ${autoMode}`);
        } else {
            alert(`Failed to start timelapse: ${result.error}`);
        }
    } catch (error) {
        console.error('Error starting timelapse:', error);
        alert(`Error starting timelapse: ${error.message}`);
    }
}

// Stop timelapse
async function stopTimelapse() {
    try {
        const response = await fetch('/stop', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            fetchStatus();
            fetchSessions();
        } else {
            alert('Failed to stop timelapse: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error stopping timelapse:', error);
        alert('Error stopping timelapse: ' + error.message);
    }
}

// Test capture
async function testCapture() {
    try {
        const response = await fetch('/test_capture', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                camera: cameraSelect.value
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show preview
            previewContainer.style.display = 'block';
            previewImage.src = data.image;
        } else {
            alert('Failed to capture test image: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error capturing test image:', error);
        alert('Error capturing test image: ' + error.message);
    }
}

// Update slider value
function updateSliderValue(event) {
    const slider = event.target;
    const valueElement = document.getElementById(`${slider.id.replace('-slider', '-value')}`);
    valueElement.textContent = slider.value;
    
    // Update state
    const settingName = slider.id.replace('-slider', '');
    appState.camera_settings[settingName] = parseFloat(slider.value);
}

// Apply camera settings
async function applyCameraSettings() {
    try {
        const settings = {
            brightness: parseFloat(brightnessSlider.value),
            contrast: parseFloat(contrastSlider.value),
            exposure: parseFloat(exposureSlider.value)
        };
        
        // Update state
        appState.camera_settings = settings;
        saveState();
        
        const response = await fetch('/update_camera_settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            alert('Camera settings applied successfully');
        } else {
            alert(`Failed to apply camera settings: ${result.error}`);
        }
    } catch (error) {
        console.error('Error applying camera settings:', error);
        alert(`Error applying camera settings: ${error.message}`);
    }
}

// Reset camera settings
function resetCameraSettings() {
    // Reset sliders to default values
    brightnessSlider.value = 0.5;
    brightnessValue.textContent = '0.5';
    
    contrastSlider.value = 1.0;
    contrastValue.textContent = '1.0';
    
    exposureSlider.value = 0.5;
    exposureValue.textContent = '0.5';
    
    // Update state
    appState.camera_settings = {
        brightness: 0.5,
        contrast: 1.0,
        exposure: 0.5
    };
    saveState();
}

// Fetch timelapse sessions
async function fetchSessions() {
    try {
        const response = await fetch('/sessions');
        const data = await response.json();
        
        // Clear existing sessions
        sessionsContainer.innerHTML = '';
        
        // Add session cards
        data.sessions.forEach(session => {
            const sessionCard = document.createElement('div');
            sessionCard.className = 'session-card';
            
            // Add thumbnail if available
            if (session.thumbnail) {
                const thumbnail = document.createElement('img');
                thumbnail.src = '/image/' + session.thumbnail;
                thumbnail.alt = 'Session thumbnail';
                sessionCard.appendChild(thumbnail);
            }
            
            // Add session info
            const sessionInfo = document.createElement('div');
            sessionInfo.innerHTML = `
                <h3>${session.id}</h3>
                <p>Frames: ${session.frame_count}</p>
                <p>Start: ${formatTimestamp(session.start_time)}</p>
                <p>Status: ${session.is_active ? 'Active' : 'Completed'}</p>
            `;
            sessionCard.appendChild(sessionInfo);
            
            // Add buttons
            const buttonContainer = document.createElement('div');
            
            // View button
            const viewButton = document.createElement('button');
            viewButton.textContent = 'View';
            viewButton.addEventListener('click', () => viewSessionDetails(session.id));
            buttonContainer.appendChild(viewButton);
            
            // Delete button (only for inactive sessions)
            if (!session.is_active) {
                const deleteButton = document.createElement('button');
                deleteButton.textContent = 'Delete';
                deleteButton.className = 'secondary';
                deleteButton.style.marginLeft = '5px';
                deleteButton.addEventListener('click', () => deleteSession(session.id));
                buttonContainer.appendChild(deleteButton);
            }
            
            sessionCard.appendChild(buttonContainer);
            sessionsContainer.appendChild(sessionCard);
        });
    } catch (error) {
        console.error('Error fetching sessions:', error);
    }
}

// View session details
async function viewSessionDetails(sessionId) {
    try {
        currentSessionId = sessionId;
        
        // Update session name
        sessionName.textContent = sessionId;
        
        // Fetch frames
        const response = await fetch(`/frames/${sessionId}`);
        const data = await response.json();
        
        // Clear existing frames
        framesContainer.innerHTML = '';
        
        // Add frames
        data.frames.forEach(frame => {
            const frameElement = document.createElement('div');
            frameElement.className = 'frame';
            
            const frameImage = document.createElement('img');
            frameImage.src = '/image/' + frame.path;
            frameImage.alt = 'Frame';
            frameImage.style.width = '100%';
            
            frameElement.appendChild(frameImage);
            framesContainer.appendChild(frameElement);
        });
        
        // Hide video container
        videoContainer.classList.add('hidden');
        
        // Show session details
        sessionDetails.classList.remove('hidden');
    } catch (error) {
        console.error('Error fetching session details:', error);
    }
}

// Create video
async function createVideo() {
    try {
        const response = await fetch('/create_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                fps: parseInt(fpsInput.value)
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Show video
            videoPlayer.src = data.video_url;
            videoContainer.classList.remove('hidden');
        } else {
            alert('Failed to create video: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error creating video:', error);
        alert('Error creating video: ' + error.message);
    }
}

// Delete session
async function deleteSession(sessionId) {
    if (!confirm(`Are you sure you want to delete session ${sessionId}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/delete/${sessionId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            fetchSessions();
        } else {
            alert('Failed to delete session: ' + (data.error || 'Unknown error'));
        }
    } catch (error) {
        console.error('Error deleting session:', error);
        alert('Error deleting session: ' + error.message);
    }
}

// Format timestamp
function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';
    
    // Convert YYYYMMDD_HHMMSS to a more readable format
    const year = timestamp.substring(0, 4);
    const month = timestamp.substring(4, 6);
    const day = timestamp.substring(6, 8);
    const hour = timestamp.substring(9, 11);
    const minute = timestamp.substring(11, 13);
    const second = timestamp.substring(13, 15);
    
    return `${year}-${month}-${day} ${hour}:${minute}:${second}`;
}

// Pre-initialize camera to reduce lag on first capture
async function preInitializeCamera(camera) {
    try {
        console.log(`Pre-initializing camera: ${camera}`);
        const response = await fetch('/pre_initialize_camera', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ camera }),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.success) {
            console.log(`Camera ${camera} pre-initialized successfully`);
        } else {
            console.warn(`Failed to pre-initialize camera ${camera}`);
        }
    } catch (error) {
        console.error('Error pre-initializing camera:', error);
        // Don't show alert to user as this is a background operation
    }
} 

