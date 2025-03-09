// DOM Elements
const statusIndicator = document.getElementById('status-indicator');
const statusText = document.getElementById('status-text');
const refreshStatusButton = document.getElementById('refresh-status');
const currentSession = document.getElementById('current-session');
const activityInfoDiv = document.getElementById('activity-info');
const activityFileSpan = document.getElementById('activity-file');
const activityIgnoredP = document.getElementById('activity-ignored');
const autoModeStatus = document.getElementById('auto-mode-status');
const cameraSelect = document.getElementById('camera-select');
const refreshCamerasButton = document.getElementById('refresh-cameras');
const intervalInput = document.getElementById('interval-input');
const intervalValue = document.getElementById('interval-value');
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
const sessionOverlay = document.getElementById('session-overlay');
const sessionDetails = document.getElementById('session-details');
const sessionName = document.getElementById('session-name');
const backButton = document.getElementById('back-button');
const fpsInput = document.getElementById('fps-input');
const createVideoButton = document.getElementById('create-video-button');
const framesContainer = document.getElementById('frames-container');
const videoContainer = document.getElementById('video-container');
const videoPlayer = document.getElementById('video-player');
const resolutionSelect = document.getElementById('resolution-select');
const cameraSettingsContent = document.getElementById('camera-settings-content');
const cameraPreviewContainer = document.getElementById('camera-preview-container');
const cameraPreviewImage = document.getElementById('camera-preview-image');
const lightbox = document.getElementById('lightbox');
const lightboxImage = document.getElementById('lightbox-image');
const closeLightbox = document.querySelector('.close-lightbox');
const cameraSettingsButton = document.getElementById('camera-settings-button');
const cameraSettingsOverlay = document.getElementById('camera-settings-overlay');
const closeCameraSettings = document.getElementById('close-camera-settings');
const refreshSessionButton = document.getElementById('refresh-session-button');
const videoLoading = document.getElementById('video-loading');
const ignoredPatternsList = document.getElementById('ignored-patterns-list');
const newPatternInput = document.getElementById('new-pattern-input');
const addPatternButton = document.getElementById('add-pattern-button');

// Global variables
let state = {
    isCapturing: false,
    currentSession: null,
    autoMode: false,
    ignoredPatterns: []
};

let currentSessionId = null; // Track the current session ID for downloads
let sessionsExpanded = false; // Track whether the sessions list is expanded

// Variable to store the polling interval ID
let statusPollingInterval = null;

// Variable to store the most recent image URL
let mostRecentImageUrl = null;

// Application state
let appState = {
    auto_mode: false,
    camera: null,
    interval: 5,
    is_capturing: false,
    current_session: null,
    camera_settings: {
        brightness: 0.5,
        contrast: 1.0,
        exposure: 0.5,
        resolution: '1280x720'
    },
    ignored_patterns: []  // Add ignored patterns to app state
};

// Function to save sessions expanded state to localStorage
function saveSessionsExpandedState() {
    try {
        localStorage.setItem('sessionsExpanded', sessionsExpanded);
    } catch (e) {
        console.error('Error saving sessions expanded state:', e);
    }
}

// Function to load sessions expanded state from localStorage
function loadSessionsExpandedState() {
    try {
        const savedState = localStorage.getItem('sessionsExpanded');
        if (savedState !== null) {
            sessionsExpanded = savedState === 'true';
        }
    } catch (e) {
        console.error('Error loading sessions expanded state:', e);
    }
}

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    try {
        // log the state
        console.log('Initializing application state:', state);
        
        // Load sessions expanded state from localStorage
        loadSessionsExpandedState();
        
        // Fetch application state first
        await fetchState();
        
        // Then fetch status and cameras
        await fetchStatus();
        await fetchCameras();
        
        // Set up event listeners
        setupEventListeners();
        
        // Set up regular status polling for UI updates
        setupStatusPolling();
        
        // Initialize tab content
        const firstTab = document.querySelector('.tab-button[data-tab="tab-camera"]');
        if (firstTab) {
            firstTab.classList.add('active');
            document.getElementById('tab-camera').classList.add('active');
        }
        
        // Enable drag-to-scroll for frames container
        enableDragToScroll(document.getElementById('frames-container'));
        
        // Enable drag-to-scroll for sessions container
        enableDragToScroll(document.getElementById('sessions-container'));
        
        // Pre-initialize the selected camera
        const cameraSelect = document.getElementById('camera-select');
        if (cameraSelect.options.length > 0) {
            await preInitializeCamera(cameraSelect.value);
        }
        
        console.log('Timelapser initialized');
    } catch (error) {
        console.error('Error during initialization:', error);
    }
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
                is_capturing: state.is_capturing !== undefined ? state.is_capturing : appState.is_capturing,
                current_session: state.current_session !== undefined ? state.current_session : appState.current_session,
                camera_settings: state.camera_settings || appState.camera_settings,
                ignored_patterns: state.ignored_patterns || appState.ignored_patterns
            };
            
            console.log('State loaded:', appState);
            
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
        // Special handling for interval: if it's 1, keep it at 1
        // Otherwise, ensure it's a multiple of 5
        let interval = appState.interval;
        if (interval > 1) {
            interval = Math.round(interval / 5) * 5;
            interval = Math.max(5, interval);
        }
        
        intervalInput.value = interval;
        intervalValue.textContent = interval + 's';
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
        
        if (appState.camera_settings.resolution !== undefined) {
            resolutionSelect.value = appState.camera_settings.resolution;
        }
    }
    
    // Update ignored patterns list
    updateIgnoredPatternsList();
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
    //refreshCamerasButton.addEventListener('click', fetchCameras);
    
    // Status refresh button
    //refreshStatusButton.addEventListener('click', fetchStatus);
    
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
        
        // Save state to server
        console.log('Saving auto_mode state:', appState.auto_mode);
        saveState();
    });
    
    // Interval input
    intervalInput.addEventListener('input', () => {
        // Get the current value
        let value = parseInt(intervalInput.value);
        
        // Special handling: if value is 1, keep it at 1
        // Otherwise, round to the nearest multiple of 5
        if (value > 1) {
            value = Math.round(value / 5) * 5;
            // Ensure minimum of 5 for values greater than 1
            value = Math.max(5, value);
        }
        
        // Update the displayed value
        intervalValue.textContent = value + 's';
    });
    
    intervalInput.addEventListener('change', () => {
        // Get the current value
        let value = parseInt(intervalInput.value);
        
        // Special handling: if value is 1, keep it at 1
        // Otherwise, round to the nearest multiple of 5
        if (value > 1) {
            value = Math.round(value / 5) * 5;
            // Ensure minimum of 5 for values greater than 1
            value = Math.max(5, value);
            // Update the slider value to match
            intervalInput.value = value;
        }
        
        // Update state
        appState.interval = value;
        intervalValue.textContent = value + 's';
        saveState();
    });
    
    // Mobile tab navigation
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Get all tab content elements
            const allTabContent = document.querySelectorAll('.tab-content');
            
            // Remove active class from all buttons and content
            tabButtons.forEach(btn => btn.classList.remove('active'));
            allTabContent.forEach(content => {
                content.classList.remove('active');
            });
            
            // Add active class to clicked button
            button.classList.add('active');
            
            // Show corresponding content
            const tabId = button.getAttribute('data-tab');
            const targetContent = document.getElementById(tabId);
            if (targetContent) {
                targetContent.classList.add('active');
                
                // Scroll to top of the tab content
                targetContent.scrollIntoView({ behavior: 'smooth' });
                window.scrollTo(0, 0); // Ensure we're at the top of the page
                
                // Reset sessions expanded state when switching to sessions tab
                if (tabId === 'tab-sessions') {
                    // Only reset if we're not already expanded
                    if (sessionsExpanded) {
                        sessionsExpanded = false;
                        saveSessionsExpandedState();
                        fetchStatus(); // Refresh the sessions list
                    }
                }
            }
        });
    });
    
    // Camera settings sliders
    brightnessSlider.addEventListener('input', updateSliderValue);
    contrastSlider.addEventListener('input', updateSliderValue);
    exposureSlider.addEventListener('input', updateSliderValue);
    
    // Resolution select
    resolutionSelect.addEventListener('change', () => {
        // Update state
        appState.camera_settings.resolution = resolutionSelect.value;
        saveState();
    });
    
    // Apply settings button
    applySettingsButton.addEventListener('click', applyCameraSettings);
    
    // Reset settings button
    resetSettingsButton.addEventListener('click', resetCameraSettings);
    
    // Back button
    backButton.addEventListener('click', () => {
        sessionOverlay.classList.add('hidden');
        currentSessionId = null;
        fetchStatus(); // Refresh sessions list
    });
    
    // Close session overlay when clicking outside the content
    sessionOverlay.addEventListener('click', (event) => {
        if (event.target === sessionOverlay) {
            sessionOverlay.classList.add('hidden');
            currentSessionId = null;
            fetchStatus(); // Refresh sessions list
        }
    });
    
    // Close session overlay with escape key
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            if (!lightbox.classList.contains('hidden')) {
                lightbox.classList.add('hidden');
            } else if (!sessionOverlay.classList.contains('hidden')) {
                sessionOverlay.classList.add('hidden');
                currentSessionId = null;
                fetchStatus(); // Refresh sessions list
            }
        }
    });
    
    // Create video button
    createVideoButton.addEventListener('click', createVideo);
    
    // Refresh session button
    refreshSessionButton.addEventListener('click', () => {
        if (currentSessionId) {
            viewSessionDetails(currentSessionId);
        }
    });
    
    // Close lightbox
    closeLightbox.addEventListener('click', () => {
        lightbox.classList.add('hidden');
    });
    
    // Close lightbox when clicking outside the image
    lightbox.addEventListener('click', (event) => {
        if (event.target === lightbox) {
            lightbox.classList.add('hidden');
        }
    });
    
    // Close lightbox with escape key
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !lightbox.classList.contains('hidden')) {
            lightbox.classList.add('hidden');
        } else if (event.key === 'Escape' && !cameraSettingsOverlay.classList.contains('hidden')) {
            cameraSettingsOverlay.classList.add('hidden');
        }
    });
    
    // Add click event to camera preview image to open lightbox
    cameraPreviewImage.addEventListener('click', () => {
        if (mostRecentImageUrl) {
            lightboxImage.src = mostRecentImageUrl;
            lightbox.classList.remove('hidden');
        }
    });
    
    // Camera settings button
    cameraSettingsButton.addEventListener('click', () => {
        cameraSettingsOverlay.classList.remove('hidden');
    });
    
    // Close camera settings
    closeCameraSettings.addEventListener('click', () => {
        cameraSettingsOverlay.classList.add('hidden');
    });
    
    // Close camera settings when clicking outside the content
    cameraSettingsOverlay.addEventListener('click', (event) => {
        if (event.target === cameraSettingsOverlay) {
            cameraSettingsOverlay.classList.add('hidden');
        }
    });
    
    // Add change event listener to camera select
    cameraSelect.addEventListener('change', () => {
        appState.camera = cameraSelect.value;
        saveState();
        // Pre-initialize the selected camera
        preInitializeCamera(cameraSelect.value);
    });
    
    // Add pattern button
    addPatternButton.addEventListener('click', addIgnoredPattern);
    
    // New pattern input - add on Enter key
    newPatternInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            addIgnoredPattern();
        }
    });
    
    // Add event listener for cancel video button
    const cancelVideoButton = document.getElementById('cancel-video-button');
    if (cancelVideoButton) {
        cancelVideoButton.addEventListener('click', cancelVideoCreation);
    }
    
    // Download buttons
    document.getElementById('download-video-button').addEventListener('click', downloadSessionVideo);
    document.getElementById('download-frames-button').addEventListener('click', downloadSessionFrames);
}

// Setup regular status polling for UI updates
function setupStatusPolling() {
    // Always poll the status endpoint to keep the UI updated
    // This is separate from the auto_mode feature which controls external API polling
    // Using a 5-second interval to avoid too many requests since we're also fetching sessions
    statusPollingInterval = setInterval(fetchStatus, 5000);
    console.log('UI status polling enabled (includes session updates)');
}

// Fetch application status
async function fetchStatus() {
    try {
        const response = await fetch('/status');
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const status = await response.json();
        
        // Update appState with capturing status and current session
        // but preserve ignored patterns
        const preservedPatterns = appState.ignored_patterns;
        appState.is_capturing = status.is_capturing;
        appState.current_session = status.current_session;
        appState.ignored_patterns = preservedPatterns;  // Restore patterns
        
        // Update status indicator
        if (status.is_capturing) {
            statusIndicator.className = 'status-indicator status-active';
            statusText.textContent = 'Capturing';
            startButton.disabled = true;
            stopButton.disabled = false;
            
            // Show current session info
            if (status.current_session) {
                currentSession.textContent = `Current session: ${status.current_session}`;
                
                // Update most recent image if available
                if (status.latest_frame) {
                    updateCameraPreview('/image/' + status.latest_frame);
                }
            }
        } else {
            statusIndicator.className = 'status-indicator status-inactive';
            statusText.textContent = 'Not capturing';
            startButton.disabled = false;
            stopButton.disabled = true;
            currentSession.textContent = '';
        }
        
        // Update activity information - show regardless of capture status
        if (status.current_file) {
            // Show the activity info div
            activityInfoDiv.classList.remove('hidden');
            
            // Update the activity file text
            activityFileSpan.textContent = status.current_file;
            
            // Show/hide the ignored status
            if (status.is_ignored) {
                activityIgnoredP.classList.remove('hidden');
            } else {
                activityIgnoredP.classList.add('hidden');
            }
        } else {
            // Hide the activity info div if no current file
            activityInfoDiv.classList.add('hidden');
        }
        
        // Update auto mode status and appState
        if (status.auto_mode !== undefined) {
            // Only update if different from current state to avoid overriding user changes
            if (appState.auto_mode !== status.auto_mode) {
                console.log(`Auto mode updated from server: ${status.auto_mode}`);
                
                // Update appState with the server value
                appState.auto_mode = status.auto_mode;
                
                // Update UI
                autoModeStatus.textContent = `Auto mode: ${status.auto_mode ? 'Enabled' : 'Disabled'}`;
                autoModeCheckbox.checked = status.auto_mode;
            } else {
                // Just update the text
                autoModeStatus.textContent = `Auto mode: ${status.auto_mode ? 'Enabled' : 'Disabled'}`;
            }
        }
        
        // Update interval if provided
        if (status.interval !== undefined && status.interval !== parseInt(intervalInput.value)) {
            // Special handling for interval: if it's 1, keep it at 1
            // Otherwise, ensure it's a multiple of 5
            let interval = status.interval;
            if (interval > 1) {
                interval = Math.round(interval / 5) * 5;
                interval = Math.max(5, interval);
            }
            
            appState.interval = interval;
            intervalInput.value = interval;
            intervalValue.textContent = interval + 's';
        }
        
        // Update camera selection if provided
        if (status.selected_camera && (!cameraSelect.value || cameraSelect.value !== status.selected_camera)) {
            appState.camera = status.selected_camera;
            // Find the option with this value
            const options = Array.from(cameraSelect.options);
            const option = options.find(opt => opt.value === status.selected_camera);
            
            if (option) {
                cameraSelect.value = status.selected_camera;
            }
        }
        
        // Update sessions list
        if (status.sessions) {
            updateSessionsList(status.sessions, status.current_session);
            
            // If no recent image and we have sessions with thumbnails, use the most recent session thumbnail
            if (!mostRecentImageUrl && status.sessions.length > 0) {
                const sessionsWithThumbnails = status.sessions.filter(session => session.thumbnail);
                if (sessionsWithThumbnails.length > 0) {
                    // Sort by start time to get the most recent
                    sessionsWithThumbnails.sort((a, b) => {
                        if (a.info && b.info && a.info.start_time && b.info.start_time) {
                            return new Date(b.info.start_time) - new Date(a.info.start_time);
                        }
                        return 0;
                    });
                    
                    const mostRecentSession = sessionsWithThumbnails[0];
                    updateCameraPreview('/image/' + mostRecentSession.thumbnail);
                }
            }
        }
        
        return status;
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
            // Immediately update appState to reflect capturing status
            appState.is_capturing = true;
            
            // Update UI
            statusIndicator.className = 'status-indicator status-active';
            statusText.textContent = 'Capturing';
            startButton.disabled = true;
            stopButton.disabled = false;
            
            // Update current session if session_id is provided
            if (result.session_id) {
                currentSession.textContent = `Current session: ${result.session_id}`;
            }
            
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
            // Immediately update appState to reflect stopped status
            appState.is_capturing = false;
            
            // Update UI
            statusIndicator.className = 'status-indicator status-inactive';
            statusText.textContent = 'Not capturing';
            startButton.disabled = false;
            stopButton.disabled = true;
            currentSession.textContent = '';
            
            // Fetch full status to update sessions list
            fetchStatus();
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
        // Show loading state
        testButton.disabled = true;
        testButton.textContent = 'Capturing...';
        
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
            // Update camera preview
            updateCameraPreview(data.image);
            
            // Camera settings are now always visible, no need to expand
        } else {
            // If there's a resolution error, suggest trying a lower resolution
            if (data.error && data.error.includes('resolution')) {
                alert('Failed to capture test image: ' + data.error + '\n\nTry selecting a lower resolution in Camera Settings.');
                
                // Open camera settings overlay
                cameraSettingsOverlay.classList.remove('hidden');
                
                // Focus on the resolution dropdown
                resolutionSelect.focus();
            } else {
                alert('Failed to capture test image: ' + (data.error || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error capturing test image:', error);
        alert('Error capturing test image: ' + error.message);
    } finally {
        // Reset button state
        testButton.disabled = false;
        testButton.textContent = 'Test Capture';
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
        const [width, height] = resolutionSelect.value.split('x').map(Number);
        
        const settings = {
            brightness: parseFloat(brightnessSlider.value),
            contrast: parseFloat(contrastSlider.value),
            exposure: parseFloat(exposureSlider.value),
            width: width,
            height: height
        };
        
        // Show loading indicator or disable button
        applySettingsButton.disabled = true;
        applySettingsButton.textContent = 'Applying...';
        
        // Update state (will be updated again with actual values from server response)
        appState.camera_settings = {
            ...appState.camera_settings,
            brightness: settings.brightness,
            contrast: settings.contrast,
            exposure: settings.exposure,
            resolution: resolutionSelect.value
        };
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
            // Check if the server adjusted the resolution
            if (result.actual_resolution && result.actual_resolution !== resolutionSelect.value) {
                // Update the resolution dropdown to match what the camera actually supports
                const options = Array.from(resolutionSelect.options);
                const option = options.find(opt => opt.value === result.actual_resolution);
                
                if (option) {
                    resolutionSelect.value = result.actual_resolution;
                } else {
                    // Add the new resolution option if it doesn't exist
                    const newOption = document.createElement('option');
                    newOption.value = result.actual_resolution;
                    newOption.textContent = result.actual_resolution;
                    resolutionSelect.appendChild(newOption);
                    resolutionSelect.value = result.actual_resolution;
                }
                
                // Update state with actual resolution
                appState.camera_settings.resolution = result.actual_resolution;
                saveState();
                
                alert(`Camera settings applied. Note: Camera adjusted resolution to ${result.actual_resolution}`);
            } else {
                alert('Camera settings applied successfully');
            }
        } else {
            alert(`Failed to apply camera settings: ${result.error}`);
        }
    } catch (error) {
        console.error('Error applying camera settings:', error);
        alert(`Error applying camera settings: ${error.message}`);
    } finally {
        // Reset button state
        applySettingsButton.disabled = false;
        applySettingsButton.textContent = 'Apply Settings';
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
    
    // Reset resolution to default
    resolutionSelect.value = '1280x720';
    
    // Update state
    appState.camera_settings = {
        brightness: 0.5,
        contrast: 1.0,
        exposure: 0.5,
        resolution: '1280x720'
    };
    saveState();
}

// Helper function to extract filename without path and extension
function getDisplayTitle(fullPath) {
    if (!fullPath) return null;
    const filename = fullPath.split(/[/\\]/).pop(); // Get the last part after any slashes
    return filename.replace(/\.[^/.]+$/, ''); // Remove extension
}

// Helper function to update the sessions list
function updateSessionsList(sessions, activeSessionId) {
    // If we're currently viewing session details, don't update anything
    // This prevents disrupting the user's current view
    if (currentSessionId && !sessionOverlay.classList.contains('hidden')) {
        // Don't update anything while the session overlay is open
        return;
    }
    
    // Clear existing sessions
    sessionsContainer.innerHTML = '';
    
    if (!sessions || sessions.length === 0) {
        sessionsContainer.innerHTML = '<p>No timelapse sessions available.</p>';
        return;
    }
    
    // Determine if we need a "Show More" button (more than 5 sessions)
    const showMoreNeeded = sessions.length > 5 && !sessionsExpanded;
    
    // Get the sessions to display initially
    const initialSessions = showMoreNeeded ? sessions.slice(0, 5) : sessions;
    const remainingSessions = showMoreNeeded ? sessions.slice(5) : [];
    
    // Function to create a session card
    const createSessionCard = (session) => {
        // Skip invalid sessions
        if (!session || !session.id) return null;
        
        const sessionCard = document.createElement('div');
        sessionCard.className = 'session-card';
        
        // Add thumbnail if available
        if (session.thumbnail) {
            const thumbnail = document.createElement('img');
            thumbnail.src = '/image/' + session.thumbnail;
            thumbnail.alt = 'Session thumbnail';
            thumbnail.title = 'Click to view session details';
            // Change click event to view session details instead of opening lightbox
            thumbnail.addEventListener('click', () => {
                viewSessionDetails(session.id);
            });
            sessionCard.appendChild(thumbnail);
        }
        
        // Check if this is the active session - only mark as active if the session ID matches AND is_capturing is true
        const isActive = session.id === activeSessionId && appState.is_capturing === true;
        
        // Session info with safe access to nested properties
        const sessionInfo = document.createElement('div');
        const startTime = session.info && session.info.start_time ? formatTimestamp(session.info.start_time) : 'Unknown';
        
        // Get display title - use activity file if available, otherwise use session ID
        let displayTitle = session.id;
        if (session.info && session.info.activity_file) {
            displayTitle = getDisplayTitle(session.info.activity_file) || session.id;
        }
        
        sessionInfo.innerHTML = `
            <strong>${displayTitle}</strong>
            <p>Frames: ${session.frame_count || 0}</p>
            <p>Started: ${startTime}</p>
            ${isActive ? '<p class="status-active">Active</p>' : ''}
        `;
        sessionCard.appendChild(sessionInfo);
        
        // Button container
        const buttonContainer = document.createElement('div');
        
        // View button
        const viewButton = document.createElement('button');
        viewButton.textContent = 'View';
        viewButton.addEventListener('click', () => viewSessionDetails(session.id));
        buttonContainer.appendChild(viewButton);
        
        // Delete button (only for inactive sessions)
        if (!isActive) {
            const deleteButton = document.createElement('button');
            deleteButton.textContent = 'Delete';
            deleteButton.className = 'secondary';
            deleteButton.style.marginLeft = '5px';
            deleteButton.addEventListener('click', () => deleteSession(session.id));
            buttonContainer.appendChild(deleteButton);
        }
        
        sessionCard.appendChild(buttonContainer);
        return sessionCard;
    };
    
    // Add initial session cards
    initialSessions.forEach(session => {
        const sessionCard = createSessionCard(session);
        if (sessionCard) {
            sessionsContainer.appendChild(sessionCard);
        }
    });
    
    // Add "Show More" button if needed
    if (showMoreNeeded) {
        const showMoreContainer = document.createElement('div');
        showMoreContainer.className = 'show-more-container';
        showMoreContainer.style.textAlign = 'center';
        showMoreContainer.style.marginTop = '15px';
        
        const showMoreButton = document.createElement('button');
        showMoreButton.textContent = `Show More (${remainingSessions.length} more)`;
        showMoreButton.className = 'show-more-button';
        
        showMoreButton.addEventListener('click', () => {
            // Set the expanded state to true
            sessionsExpanded = true;
            saveSessionsExpandedState();
            
            // Remove the show more button
            showMoreContainer.remove();
            
            // Add the remaining sessions
            remainingSessions.forEach(session => {
                const sessionCard = createSessionCard(session);
                if (sessionCard) {
                    sessionsContainer.appendChild(sessionCard);
                }
            });
            
            // Add a "Show Less" button
            const showLessContainer = document.createElement('div');
            showLessContainer.className = 'show-less-container';
            showLessContainer.style.textAlign = 'center';
            showLessContainer.style.marginTop = '15px';
            
            const showLessButton = document.createElement('button');
            showLessButton.textContent = 'Show Less';
            showLessButton.className = 'show-less-button';
            
            showLessButton.addEventListener('click', () => {
                // Set the expanded state to false
                sessionsExpanded = false;
                saveSessionsExpandedState();
                
                // Refresh the sessions list (which will revert to showing only 5)
                updateSessionsList(sessions, activeSessionId);
            });
            
            showLessContainer.appendChild(showLessButton);
            sessionsContainer.appendChild(showLessContainer);
        });
        
        showMoreContainer.appendChild(showMoreButton);
        sessionsContainer.appendChild(showMoreContainer);
    }
    
    // If sessions are expanded but we're showing all sessions now, add a "Show Less" button
    // This handles the case where sessions were expanded but now there are 5 or fewer sessions
    if (sessionsExpanded && !showMoreNeeded && sessions.length > 0) {
        const showLessContainer = document.createElement('div');
        showLessContainer.className = 'show-less-container';
        showLessContainer.style.textAlign = 'center';
        showLessContainer.style.marginTop = '15px';
        
        const showLessButton = document.createElement('button');
        showLessButton.textContent = 'Show Less';
        showLessButton.className = 'show-less-button';
        
        showLessButton.addEventListener('click', () => {
            // Set the expanded state to false
            sessionsExpanded = false;
            saveSessionsExpandedState();
            
            // Refresh the sessions list
            updateSessionsList(sessions, activeSessionId);
        });
        
        showLessContainer.appendChild(showLessButton);
        sessionsContainer.appendChild(showLessContainer);
    }
}

// View session details
async function viewSessionDetails(sessionId) {
    try {
        currentSessionId = sessionId;
        
        // Fetch sessions to get session info
        const sessionsResponse = await fetch('/sessions');
        let displayTitle = sessionId;
        let sessionsData = null;
        
        if (sessionsResponse.ok) {
            sessionsData = await sessionsResponse.json();
            const sessionInfo = sessionsData.sessions.find(session => session.id === sessionId);
            
            // Get display title - use activity file if available, otherwise use session ID
            if (sessionInfo && sessionInfo.info && sessionInfo.info.activity_file) {
                // Extract just the filename without path and extension
                const fullPath = sessionInfo.info.activity_file;
                displayTitle = getDisplayTitle(fullPath) || sessionId;
            }
        }
        
        // Update session name
        sessionName.textContent = displayTitle;
        
        // Show session overlay
        sessionOverlay.classList.remove('hidden');
        videoContainer.classList.add('hidden');
        
        // Fetch frames for this session
        const response = await fetch(`/frames/${sessionId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Check if the response has a success flag and it's false
        if (data.success === false) {
            throw new Error(data.error || 'Unknown error');
        }
        
        // Check if this session is active
        const isActive = sessionId === appState.current_session && appState.is_capturing;
        
        // Update session name with active indicator if needed
        if (isActive) {
            sessionName.innerHTML = `${displayTitle} <span class="status-active" style="display: inline-block; margin-left: 5px; vertical-align: middle;"></span>`;
            
            // Disable create video button for active sessions
            createVideoButton.disabled = true;
            createVideoButton.title = "Cannot create video while capture is in progress";
        } else {
            sessionName.textContent = displayTitle;
            
            // Enable create video button for inactive sessions
            createVideoButton.disabled = false;
            createVideoButton.title = "";
        }
        
        // Clear existing frames
        framesContainer.innerHTML = '';
        
        // Get frames from response (handle both formats for backward compatibility)
        const frames = data.frames || [];
        
        if (frames.length === 0) {
            framesContainer.innerHTML = '<p>No frames available for this session.</p>';
            return;
        }
        
        // Add frames (most recent 5)
        // Since frames are now already sorted newest first from the backend,
        // we can just take the first 5 frames without reversing
        const recentFrames = frames.slice(0, 5);
        
        recentFrames.forEach(frame => {
            const frameElement = document.createElement('div');
            frameElement.className = 'frame';
            
            const frameImage = document.createElement('img');
            frameImage.src = `/image/${frame.path}`;
            frameImage.alt = `Frame ${frame.filename}`;
            frameImage.style.width = '100%';
            
            // Add click event to show preview
            frameImage.addEventListener('click', () => {
                // Show in lightbox instead of preview container
                lightboxImage.src = `/image/${frame.path}`;
                lightbox.classList.remove('hidden');
            });
            
            frameElement.appendChild(frameImage);
            framesContainer.appendChild(frameElement);
        });
        
        // Check if a video exists for this session - use the already fetched sessions data
        if (sessionsData) {
            const sessionInfo = sessionsData.sessions.find(session => session.id === sessionId);
            
            if (sessionInfo && sessionInfo.has_video) {
                // Show video if it exists
                // Add timestamp to prevent caching
                const timestamp = new Date().getTime();
                videoPlayer.src = `/video/${sessionId}?t=${timestamp}`;  // Use the /video endpoint instead of direct path
                videoContainer.classList.remove('hidden');
                
                // Add indicator to the create video button
                createVideoButton.innerHTML = "Recreate Video";
                createVideoButton.title = "A video already exists. Click to recreate.";
            } else {
                // Reset button text if no video exists
                createVideoButton.innerHTML = "Create Video";
                createVideoButton.title = "";
            }
        }
    } catch (error) {
        console.error('Error viewing session details:', error);
        alert(`Failed to fetch frames: ${error.message}`);
        
        // Go back to sessions list on error
        sessionOverlay.classList.add('hidden');
        currentSessionId = null;
    }
}

// Create video
async function createVideo() {
    try {
        // Check if this session is active
        const isActive = currentSessionId === appState.current_session && appState.is_capturing;
        
        // Prevent creating video for active sessions
        if (isActive) {
            alert("Cannot create video while capture is in progress. Please stop the capture first.");
            return;
        }
        
        // Check if a video already exists for this session
        const sessionsResponse = await fetch('/sessions');
        if (sessionsResponse.ok) {
            const sessionsData = await sessionsResponse.json();
            const sessionInfo = sessionsData.sessions.find(session => session.id === currentSessionId);
            
            if (sessionInfo && sessionInfo.has_video) {
                // Ask for confirmation before overwriting
                if (!confirm("A video already exists for this session. Do you want to overwrite it?")) {
                    return; // User cancelled
                }
            }
        }
        
        // Show loading spinner and disable button
        videoLoading.classList.remove('hidden');
        createVideoButton.disabled = true;
        
        // Show cancel button
        const cancelVideoButton = document.getElementById('cancel-video-button');
        if (cancelVideoButton) {
            cancelVideoButton.classList.remove('hidden');
            cancelVideoButton.disabled = false;
        }
        
        // Reset progress bar
        const progressBar = document.getElementById('video-progress-bar');
        const progressText = document.getElementById('video-progress-text');
        const statusText = document.getElementById('video-status-text');
        progressBar.style.width = '0%';
        progressText.textContent = '0%';
        statusText.textContent = 'Creating video...';
        
        // Start progress tracking
        let progressTrackingId = null;
        
        try {
            // Start the video creation process
            const createVideoRequest = fetch('/create_video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    fps: parseInt(fpsInput.value)
                })
            });
            
            // Start tracking progress immediately
            progressTrackingId = setInterval(async () => {
                const isCompleted = await trackVideoProgress(currentSessionId);
                if (isCompleted) {
                    clearInterval(progressTrackingId);
                    
                    // Hide cancel button when completed
                    if (cancelVideoButton) {
                        cancelVideoButton.classList.add('hidden');
                    }
                }
            }, 1000); // Check progress every second
            
            // Wait for the request to complete
            const response = await createVideoRequest;
            const data = await response.json();
            
            // Hide loading spinner and enable button
            videoLoading.classList.add('hidden');
            createVideoButton.disabled = false;
            
            // Hide cancel button
            if (cancelVideoButton) {
                cancelVideoButton.classList.add('hidden');
            }
            
            if (data.success) {
                // Show the video container
                document.getElementById('video-container').classList.remove('hidden');
                
                // Add timestamp to video URL to prevent caching
                const timestamp = new Date().getTime();
                const videoPlayer = document.getElementById('video-player');
                videoPlayer.src = `/video/${currentSessionId}?t=${timestamp}`;  // Use the /video endpoint instead of direct path
                
                // Reset video player
                videoPlayer.load();
                
                // Hide the loading indicator
                videoLoading.classList.add('hidden');
                createVideoButton.classList.remove('hidden');
                createVideoButton.disabled = false;
                createVideoButton.title = "";
                
                // Show success message
                if (data.video_existed) {
                    alert(`Video successfully recreated with ${data.frame_count} frames.`);
                } else {
                    alert(`Video successfully created with ${data.frame_count} frames.`);
                }
            } else if (data.cancelled) {
                alert(data.message || 'Video creation was cancelled.');
                
                // Clear the progress tracking
                if (progressTrackingId) {
                    clearInterval(progressTrackingId);
                }
            } else {
                alert('Failed to create video: ' + (data.error || 'Unknown error'));
            }
        } catch (error) {
            console.error('Error creating video:', error);
            alert('Error creating video: ' + error.message);
            
            // Hide loading spinner and enable button
            videoLoading.classList.add('hidden');
            createVideoButton.disabled = false;
            
            // Hide cancel button
            if (cancelVideoButton) {
                cancelVideoButton.classList.add('hidden');
            }
            
            // Clear the progress tracking
            if (progressTrackingId) {
                clearInterval(progressTrackingId);
            }
        }
    } catch (error) {
        console.error('Error creating video:', error);
        alert('Error creating video: ' + error.message);
    }
}

// Cancel video creation
async function cancelVideoCreation() {
    if (!currentSessionId) {
        alert('No active session to cancel.');
        return;
    }
    
    if (!confirm('Are you sure you want to cancel video creation? This cannot be undone.')) {
        return;
    }
    
    try {
        // Disable the cancel button to prevent multiple clicks
        const cancelVideoButton = document.getElementById('cancel-video-button');
        if (cancelVideoButton) {
            cancelVideoButton.disabled = true;
        }
        
        // Update status text
        const statusText = document.getElementById('video-status-text');
        statusText.textContent = 'Cancelling video creation...';
        
        // Send cancel request
        const response = await fetch(`/cancel_video/${currentSessionId}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            statusText.textContent = 'Video creation cancelled.';
        } else {
            statusText.textContent = 'Failed to cancel: ' + (data.error || 'Unknown error');
            
            // Re-enable the cancel button
            if (cancelVideoButton) {
                cancelVideoButton.disabled = false;
            }
        }
    } catch (error) {
        console.error('Error cancelling video creation:', error);
        
        // Re-enable the cancel button
        const cancelVideoButton = document.getElementById('cancel-video-button');
        if (cancelVideoButton) {
            cancelVideoButton.disabled = false;
        }
        
        // Update status text
        const statusText = document.getElementById('video-status-text');
        statusText.textContent = 'Error cancelling: ' + error.message;
    }
}

// Track video creation progress
async function trackVideoProgress(sessionId) {
    const progressBar = document.getElementById('video-progress-bar');
    const progressText = document.getElementById('video-progress-text');
    const statusText = document.getElementById('video-status-text');
    
    try {
        const response = await fetch(`/video_progress/${sessionId}`);
        if (response.ok) {
            try {
                // Get the raw text first
                const rawText = await response.text();
                
                // Try to parse the JSON
                let data;
                try {
                    data = JSON.parse(rawText);
                } catch (jsonError) {
                    console.error('Error parsing JSON from video_progress:', jsonError);
                    console.log('Raw response:', rawText);
                    
                    // Create a default data object to continue showing progress
                    data = {
                        status: 'processing',
                        progress: 50,
                        error: 'Invalid JSON response'
                    };
                }
                
                // Update progress bar
                const progress = Math.round(data.progress || 0);
                progressBar.style.width = `${progress}%`;
                progressText.textContent = `${progress}%`;
                
                // Calculate elapsed time - prefer elapsed_seconds if available
                let elapsedText = '';
                if (data.elapsed_seconds) {
                    const elapsed = Math.round(data.elapsed_seconds);
                    elapsedText = ` (${elapsed}s elapsed)`;
                } else if (data.start_time) {
                    const elapsed = Math.round((Date.now() / 1000) - data.start_time);
                    elapsedText = ` (${elapsed}s elapsed)`;
                }
                
                // Update status text with more detailed information
                if (data.status === 'completed') {
                    statusText.textContent = 'Video creation completed!' + elapsedText;
                    
                    // Hide cancel button
                    const cancelVideoButton = document.getElementById('cancel-video-button');
                    if (cancelVideoButton) {
                        cancelVideoButton.classList.add('hidden');
                    }
                    
                    return true; // Signal completion
                } else if (data.status === 'failed') {
                    statusText.textContent = `Failed: ${data.error || 'Unknown error'}` + elapsedText;
                    
                    // Hide cancel button
                    const cancelVideoButton = document.getElementById('cancel-video-button');
                    if (cancelVideoButton) {
                        cancelVideoButton.classList.add('hidden');
                    }
                    
                    return true; // Signal completion (with error)
                } else if (data.status === 'cancelled') {
                    statusText.textContent = `Cancelled: ${data.error || 'Video creation was cancelled'}` + elapsedText;
                    
                    // Hide cancel button
                    const cancelVideoButton = document.getElementById('cancel-video-button');
                    if (cancelVideoButton) {
                        cancelVideoButton.classList.add('hidden');
                    }
                    
                    return true; // Signal completion (cancelled)
                } else if (data.status === 'processing') {
                    // Show more detailed progress information
                    if (data.frame && data.total_frames) {
                        statusText.textContent = `Processing: Frame ${data.frame}/${data.total_frames}${elapsedText}`;
                    } else {
                        statusText.textContent = `Processing video...${elapsedText}`;
                    }
                } else {
                    statusText.textContent = `Creating video...${elapsedText}`;
                }
            } catch (error) {
                console.error('Error processing response:', error);
                statusText.textContent = 'Creating video... (status unknown)';
            }
        }
    } catch (error) {
        console.error('Error tracking progress:', error);
    }
    
    return false; // Not completed
}

// Delete session
async function deleteSession(sessionId) {
    // Confirm deletion
    if (!confirm(`Are you sure you want to delete session "${sessionId}"? This cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/delete/${sessionId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // If we're currently viewing this session, close the overlay
            if (currentSessionId === sessionId && !sessionOverlay.classList.contains('hidden')) {
                sessionOverlay.classList.add('hidden');
                currentSessionId = null;
            }
            
            // Refresh sessions list
            fetchStatus();
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
    
    try {
        // Check if timestamp is already in a readable format (contains dashes or spaces)
        if (timestamp.includes('-') || timestamp.includes(' ')) {
            return timestamp;
        }
        
        // Convert YYYYMMDD_HHMMSS to a more readable format
        const year = timestamp.substring(0, 4);
        const month = timestamp.substring(4, 6);
        const day = timestamp.substring(6, 8);
        
        // Check if we have the time part (after underscore)
        let timeStr = '';
        if (timestamp.includes('_') && timestamp.length > 9) {
            const hour = timestamp.substring(9, 11);
            const minute = timestamp.substring(11, 13);
            const second = timestamp.length >= 15 ? timestamp.substring(13, 15) : '00';
            timeStr = ` ${hour}:${minute}:${second}`;
        }
        
        return `${year}-${month}-${day}${timeStr}`;
    } catch (error) {
        console.warn('Error formatting timestamp:', error);
        return timestamp || 'Unknown'; // Return original or 'Unknown' if null
    }
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

// Helper function to update the camera preview
function updateCameraPreview(imageUrl) {
    if (imageUrl) {
        mostRecentImageUrl = imageUrl;
        cameraPreviewImage.src = imageUrl;
        
        // Make sure the preview image has the title attribute
        cameraPreviewImage.title = "Click to enlarge";
    }
}

/**
 * Enables drag-to-scroll functionality for a container
 * @param {HTMLElement} element - The scrollable container element
 */
function enableDragToScroll(element) {
    if (!element) return;
    
    let isDown = false;
    let isDragging = false;
    let startX;
    let scrollLeft;
    let startTime;
    let startScrollLeft;
    
    element.addEventListener('mousedown', (e) => {
        isDown = true;
        isDragging = false; // Reset dragging state
        element.classList.add('active');
        startX = e.pageX - element.offsetLeft;
        scrollLeft = element.scrollLeft;
        startTime = new Date().getTime();
        startScrollLeft = element.scrollLeft;
        // Don't prevent default here to allow clicks
    });
    
    element.addEventListener('mouseleave', () => {
        isDown = false;
        isDragging = false;
        element.classList.remove('active');
        element.classList.remove('grabbing');
    });
    
    element.addEventListener('mouseup', (e) => {
        // If we've been dragging, prevent the click
        if (isDragging) {
            e.preventDefault();
            e.stopPropagation();
        }
        
        isDown = false;
        isDragging = false;
        element.classList.remove('active');
        element.classList.remove('grabbing');
    });
    
    element.addEventListener('mousemove', (e) => {
        if (!isDown) return;
        
        const x = e.pageX - element.offsetLeft;
        const walk = (x - startX) * 2; // Scroll speed multiplier
        
        // Only consider it a drag if we've moved more than 5px or scrolled
        if (!isDragging && (Math.abs(walk) > 5 || element.scrollLeft !== startScrollLeft)) {
            isDragging = true;
            element.classList.add('grabbing');
        }
        
        if (isDragging) {
            e.preventDefault();
            element.scrollLeft = scrollLeft - walk;
        }
    });
    
    // Add click handler to prevent clicks immediately after dragging
    element.addEventListener('click', (e) => {
        if (isDragging) {
            e.preventDefault();
            e.stopPropagation();
        }
    }, true); // Use capture phase
}

// Initialize drag-to-scroll functionality
document.addEventListener('DOMContentLoaded', function() {
    // Apply drag scrolling to the sessions container
    enableDragToScroll(document.getElementById('sessions-container'));
    
    // Also apply to frames container when it's available
    const framesContainer = document.getElementById('frames-container');
    if (framesContainer) {
        enableDragToScroll(framesContainer);
    }
});

// Add a new ignored pattern
function addIgnoredPattern() {
    const pattern = newPatternInput.value.trim();
    
    if (pattern) {
        // Add to app state if not already present
        if (!appState.ignored_patterns.includes(pattern)) {
            appState.ignored_patterns.push(pattern);
            
            // Update UI
            updateIgnoredPatternsList();
            
            // Save state
            saveState();
            
            // Clear input
            newPatternInput.value = '';
        } else {
            alert('This pattern is already in the list.');
        }
    }
}

// Remove an ignored pattern
function removeIgnoredPattern(pattern) {
    // Remove from app state
    appState.ignored_patterns = appState.ignored_patterns.filter(p => p !== pattern);
    
    // Update UI
    updateIgnoredPatternsList();
    
    // Save state
    saveState();
}

// Update the ignored patterns list in the UI
function updateIgnoredPatternsList() {
    // Clear current list
    ignoredPatternsList.innerHTML = '';
    
    // Add each pattern
    if (appState.ignored_patterns && appState.ignored_patterns.length > 0) {
        appState.ignored_patterns.forEach(pattern => {
            const item = document.createElement('div');
            item.className = 'ignored-pattern-item';
            
            const patternText = document.createElement('span');
            patternText.className = 'ignored-pattern-text';
            patternText.textContent = pattern;
            
            const removeButton = document.createElement('button');
            removeButton.className = 'remove-pattern-button';
            removeButton.innerHTML = '&times;';
            removeButton.title = 'Remove pattern';
            removeButton.addEventListener('click', () => removeIgnoredPattern(pattern));
            
            item.appendChild(patternText);
            item.appendChild(removeButton);
            ignoredPatternsList.appendChild(item);
        });
    } else {
        // Show a message if no patterns
        const emptyMessage = document.createElement('p');
        emptyMessage.className = 'info-text';
        emptyMessage.textContent = 'No ignored patterns. Add patterns below to ignore specific activities.';
        ignoredPatternsList.appendChild(emptyMessage);
    }
}

// Function to download the session video
function downloadSessionVideo() {
    if (!currentSessionId) {
        console.error('No session ID available for download');
        return;
    }
    
    // Create a download link and trigger it
    const downloadUrl = `/download_video/${currentSessionId}`;
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `timelapse_${currentSessionId}.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// Function to download the session frames as a ZIP
function downloadSessionFrames() {
    if (!currentSessionId) {
        console.error('No session ID available for download');
        return;
    }
    
    // Get the FPS value from the input
    const fpsInput = document.getElementById('fps-input');
    const fps = fpsInput ? parseInt(fpsInput.value) || 30 : 30;
    
    // Show initial loading indicator
    const downloadButton = document.getElementById('download-frames-button');
    const originalText = downloadButton.innerHTML;
    downloadButton.innerHTML = `
        <div class="spinner" style="width: 16px; height: 16px;"></div>
        Checking...
    `;
    downloadButton.disabled = true;
    
    // First check if a ZIP file already exists
    fetch(`/check_zip_exists/${currentSessionId}`)
        .then(response => response.json())
        .then(data => {
            if (data.exists) {
                // Ask the user if they want to use the existing ZIP or create a new one
                downloadButton.innerHTML = originalText;
                downloadButton.disabled = false;
                
                const useExisting = confirm(
                    `An existing ZIP file was found (${data.size_formatted}, created on ${data.modified_time}).\n\n` +
                    `Do you want to use this existing file?\n\n` +
                    `- Click OK to use the existing ZIP file\n` +
                    `- Click Cancel to create a new ZIP file with current settings`
                );
                
                if (useExisting) {
                    // Use the existing ZIP file
                    startDownload(false);
                } else {
                    // Create a new ZIP file
                    startDownload(true);
                }
            } else {
                // No existing ZIP file, create a new one
                startDownload(false);
            }
        })
        .catch(error => {
            console.error('Error checking if ZIP exists:', error);
            downloadButton.innerHTML = originalText;
            downloadButton.disabled = false;
            alert('Error checking if ZIP file exists. Please try again.');
        });
    
    // Function to start the download process
    function startDownload(forceNew) {
        // Show loading indicator
        downloadButton.innerHTML = `
            <div class="spinner" style="width: 16px; height: 16px;"></div>
            Preparing ZIP... 0%
        `;
        downloadButton.disabled = true;
        
        // Create the download URL with the force parameter if needed
        const downloadUrl = `/download_frames/${currentSessionId}?fps=${fps}${forceNew ? '&force=true' : ''}`;
        
        // Start polling for progress
        let progressInterval = setInterval(() => {
            fetch(`/zip_progress/${currentSessionId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.status === "completed") {
                        clearInterval(progressInterval);
                        downloadButton.innerHTML = `
                            <div class="spinner" style="width: 16px; height: 16px;"></div>
                            Downloading...
                        `;
                        
                        // Use a more reliable method for downloading large files
                        // Instead of creating a link and clicking it, open in a new tab/window
                        // This helps avoid the Content-Length mismatch error
                        window.open(downloadUrl, '_blank');
                        
                        // Reset button after a short delay
                        setTimeout(() => {
                            downloadButton.innerHTML = originalText;
                            downloadButton.disabled = false;
                        }, 1000);
                    } else if (data.status === "error") {
                        clearInterval(progressInterval);
                        downloadButton.innerHTML = originalText;
                        downloadButton.disabled = false;
                        alert('Error preparing ZIP file: ' + (data.message || 'Unknown error'));
                    } else {
                        // Update progress
                        const progress = data.progress || 0;
                        downloadButton.innerHTML = `
                            <div class="spinner" style="width: 16px; height: 16px;"></div>
                            Preparing ZIP... ${progress}%
                        `;
                    }
                })
                .catch(error => {
                    console.error('Error checking zip progress:', error);
                    // Don't clear the interval or reset the button on network errors
                    // Just continue polling
                });
        }, 1000);
        
        // Use fetch to start the download process
        fetch(downloadUrl, { method: 'HEAD' })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                
                // The actual download will be triggered by the progress polling
                // when it detects that the ZIP is complete
            })
            .catch(error => {
                console.error('Error checking download availability:', error);
                // Don't clear the interval here, as the file might still be being created
                // The progress polling will handle the download when it's ready
            });
    }
}


