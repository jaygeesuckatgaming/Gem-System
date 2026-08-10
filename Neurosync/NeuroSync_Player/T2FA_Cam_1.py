from flask import Flask, request, jsonify
from threading import Thread, Event # Added Event for ONVIF init status
import pygame
import warnings
import time
import os
import re
from pythonosc import udp_client
from flask_cors import CORS

# --- ONVIF Imports (ensure onvif-zeep is installed: pip install onvif-zeep) ---
try:
    from onvif import ONVIFCamera
    ONVIF_AVAILABLE = True
except ImportError:
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    print("!!! WARNING: onvif-zeep library not found.                 !!!")
    print("!!! ONVIF Camera control will be DISABLED.                 !!!")
    print("!!! Install it with: pip install onvif-zeep                !!!")
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    ONVIF_AVAILABLE = False

warnings.filterwarnings(
    "ignore",
    message="Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work"
)
from utils.files.file_utils import save_generated_data, initialize_directories
from utils.generated_runners import run_audio_animation
from utils.neurosync.multi_part_return import get_tts_with_blendshapes
from utils.neurosync.neurosync_api_connect import send_audio_to_neurosync
from utils.tts.eleven_labs import get_elevenlabs_audio
from utils.tts.local_tts import call_local_tts
from livelink.connect.livelink_init import create_socket_connection, initialize_py_face
from livelink.animations.default_animation import default_animation_loop, stop_default_animation

from utils.emote_sender.send_emote import EmoteConnect
# -- SETTINGS --
voice_name = 'bf_isabella'  # bf_isabella
use_elevenlabs = False  # select ElevenLabs or Local TTS
use_combined_endpoint = True  # Only set this true if you have the combined realtime API with TTS + blendshape in one call.
ENABLE_EMOTE_CALLS = False

# --- OSC Configuration ---
OSC_CHAT_ROUTE_METHOD = ["POST"]
RECEIVER_IP = "127.0.0.1"
RECEIVER_PORT = 9001
OSC_ADDRESS = "/chat/message"

# --- ONVIF Camera Configuration - MODIFY THESE --- http://192.168.1.100:2020/onvif/device_service
ENABLE_ONVIF_CAMERA = ONVIF_AVAILABLE and True # Master switch, set to False to disable even if lib is present
ONVIF_CAMERA_IP = '192.168.1.100'  # Replace with your camera's IP
ONVIF_CAMERA_PORT = 2020              # Replace with ONVIF port
ONVIF_USERNAME = 'jaygee'           # Replace with camera username
ONVIF_PASSWORD = '1248aceg'        # Replace with camera password

# --- ONVIF WSDL Directory (Important!) ---
# Option 1: Try to auto-detect (works if onvif-zeep is in standard site-packages)
ONVIF_WSDL_DIR = r'C:\Users\jorge\Documents\AI\NeuroSync\NeuroSync_Player-main\async\Lib\site-packages\onvif_zeep-0.2.12-py3.12.egg\Lib\site-packages\wsdl'
if ONVIF_AVAILABLE:
    try:
        import onvif_zeep
        ONVIF_WSDL_DIR = os.path.join(os.path.dirname(onvif_zeep.__file__), 'wsdl')
        if not os.path.isdir(ONVIF_WSDL_DIR): # Fallback if auto-detect path isn't a dir
             print(f"Warning: Auto-detected ONVIF_WSDL_DIR '{ONVIF_WSDL_DIR}' is not a valid directory.")
             ONVIF_WSDL_DIR = None
    except Exception as e:
        print(f"Warning: Could not auto-detect ONVIF WSDL directory: {e}")
        ONVIF_WSDL_DIR = None

# Option 2: Set MANUALLY if auto-detect fails or you have a custom location
if ONVIF_WSDL_DIR is None and ONVIF_AVAILABLE:
    # ONVIF_WSDL_DIR = '/path/to/your/onvif_zeep/wsdl' # <-- !!! SET THIS MANUALLY IF NEEDED !!!
    ONVIF_WSDL_DIR = r'C:\Users\jorge\Documents\AI\NeuroSync\NeuroSync_Player-main\async\Lib\site-packages\onvif_zeep-0.2.12-py3.12.egg\Lib\site-packages\wsdl'
    print(ONVIF_WSDL_DIR)
    print("ONVIF_WSDL_DIR not set or auto-detection failed. Camera control might not work unless set manually.")
    print("If you installed onvif-zeep in a virtual environment, the path might be like:")
    print(".../your_env_name/lib/pythonX.Y/site-packages/onvif_zeep/wsdl")


# --- ONVIF CALIBRATION VALUES (YOU MUST ADJUST THESE FOR YOUR CAMERA!) ---
ONVIF_DEGREES_TO_PAN_TILT_TRANSLATION_UNIT = 0.01 # Example: 0.1 ONVIF translation / 10 degrees pan = 0.01
ONVIF_PERCENT_TO_ZOOM_TRANSLATION_UNIT = 0.01   # Example: 0.2 ONVIF translation / 20% zoom = 0.01
ONVIF_DEFAULT_RELATIVE_MOVE_SPEED = 0.5

# -- SETTINGS END --

print(f"--- OSC Sender Config ---")
print(f"Target IP:   {RECEIVER_IP}")
print(f"Target Port: {RECEIVER_PORT}")
print(f"OSC Address: {OSC_ADDRESS}")
print(f"OSC Rout Method: {OSC_CHAT_ROUTE_METHOD}")
print(f"-------------------------")

if ENABLE_ONVIF_CAMERA:
    print(f"--- ONVIF Camera Control Config ---")
    print(f"Enabled:     True")
    print(f"Camera IP:   {ONVIF_CAMERA_IP}")
    print(f"WSDL Dir:    {ONVIF_WSDL_DIR if ONVIF_WSDL_DIR else 'NOT SET (CRITICAL!)'}")
    print(f"Calibration: Degrees->Unit = {ONVIF_DEGREES_TO_PAN_TILT_TRANSLATION_UNIT}, Percent->Unit = {ONVIF_PERCENT_TO_ZOOM_TRANSLATION_UNIT}")
    print(f"---------------------------------")
else:
    print(f"--- ONVIF Camera Control: DISABLED ---")


app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize resources outside the route for efficiency
initialize_directories()
py_face = initialize_py_face()
socket_connection = create_socket_connection()
default_animation_thread = Thread(target=default_animation_loop, args=(py_face,))
default_animation_thread.start()

# --- ONVIF Global Variables ---
onvif_mycam = None
onvif_active_profile_token = None
onvif_camera_initialized = Event() # To signal if ONVIF setup was successful

# --- ONVIF Helper Functions ---
def onvif_get_ptz_service_instance():
    if not onvif_mycam:
        raise Exception("ONVIFCamera (onvif_mycam) not initialized.")
    return onvif_mycam.create_ptz_service()

def onvif_update_and_get_current_position(ptz_service_instance=None):
    # This function might be useful for a /onvif_position GET endpoint if you add one
    if not onvif_camera_initialized.is_set() or not onvif_active_profile_token:
        return None, None, None # ONVIF not ready

    ptz = ptz_service_instance if ptz_service_instance else onvif_get_ptz_service_instance()
    if not ptz: return None, None, None # Could not create service

    pan, tilt, zoom = None, None, None
    try:
        status_request = ptz.create_type('GetStatus')
        status_request.ProfileToken = onvif_active_profile_token
        ptz_status = ptz.GetStatus(status_request)
        if ptz_status and ptz_status.Position:
            if ptz_status.Position.PanTilt:
                pan = ptz_status.Position.PanTilt.x
                tilt = ptz_status.Position.PanTilt.y
            if ptz_status.Position.Zoom:
                zoom = ptz_status.Position.Zoom.x
        return pan, tilt, zoom
    except Exception as e:
        print(f"Error getting ONVIF PTZ status: {e}")
        return None, None, None # Return None on error

def _onvif_generic_relative_move(pan_translation, tilt_translation, zoom_translation,
                                 pan_speed=ONVIF_DEFAULT_RELATIVE_MOVE_SPEED,
                                 tilt_speed=ONVIF_DEFAULT_RELATIVE_MOVE_SPEED,
                                 zoom_speed=ONVIF_DEFAULT_RELATIVE_MOVE_SPEED,
                                 ptz_service_instance=None):
    if not onvif_camera_initialized.is_set() or not onvif_active_profile_token:
        print("ONVIF Relative move failed: Camera system not ready.")
        return False

    ptz = ptz_service_instance if ptz_service_instance else onvif_get_ptz_service_instance()
    if not ptz: return False

    request = ptz.create_type('RelativeMove')
    request.ProfileToken = onvif_active_profile_token
    request.Translation = ptz.zeep_client.get_element('ns0:PTZVector')()
    request.Translation.PanTilt = ptz.zeep_client.get_element('ns0:Vector2D')()
    request.Translation.PanTilt.x = pan_translation
    request.Translation.PanTilt.y = tilt_translation
    request.Translation.Zoom = ptz.zeep_client.get_element('ns0:Vector1D')()
    request.Translation.Zoom.x = zoom_translation
    request.Speed = ptz.zeep_client.get_element('ns0:PTZSpeed')()
    request.Speed.PanTilt = ptz.zeep_client.get_element('ns0:Vector2D')()
    request.Speed.PanTilt.x = pan_speed
    request.Speed.PanTilt.y = tilt_speed
    request.Speed.Zoom = ptz.zeep_client.get_element('ns0:Vector1D')()
    request.Speed.Zoom.x = zoom_speed
    try:
        ptz.RelativeMove(request)
        # Optional: Short delay and update position, but for quick commands, might not be critical here.
        # time.sleep(0.5)
        # onvif_update_and_get_current_position(ptz_service_instance=ptz)
        return True
    except Exception as e:
        print(f"\nError sending ONVIF RelativeMove: {e}")
        return False

def onvif_parse_command_string(command_str):
    pattern = re.compile(
        r"^(pan|tilt|zoom|stop)\s*(left|right|up|down|in|out)?\s*(\d+\.?\d*)?\s*(degrees|percent|level)?$",
        re.IGNORECASE
    )
    match = pattern.match(command_str.strip())
    if not match: return None
    action, direction, value_str, unit = match.groups()
    parsed = {"action": action.lower()}
    if direction: parsed["direction"] = direction.lower()
    if value_str:
        try: parsed["value"] = float(value_str)
        except ValueError: return None
    if unit: parsed["unit"] = unit.lower()
    # Basic validation (can be expanded)
    if action == "pan" and direction not in ["left", "right"]: return None
    if action == "tilt" and direction not in ["up", "down"]: return None
    if action == "zoom" and direction not in ["in", "out"]: return None
    if action in ["pan", "tilt", "zoom"] and "value" not in parsed : # Simplified: assume unit if value present
        if not (action == "zoom" and parsed.get("unit") == "level"):
            return None
    if action in ["pan", "tilt"] and "unit" not in parsed and "value" in parsed: parsed["unit"] = "degrees"
    if action == "zoom" and "unit" not in parsed and "value" in parsed: parsed["unit"] = "percent"

    return parsed

# --- ONVIF Initialization Function ---
def initialize_onvif_camera_system():
    global onvif_mycam, onvif_active_profile_token
    if not ENABLE_ONVIF_CAMERA:
        print("ONVIF camera system is disabled by configuration.")
        return

    if not ONVIF_WSDL_DIR or not os.path.isdir(ONVIF_WSDL_DIR):
        print(f"CRITICAL: ONVIF_WSDL_DIR ('{ONVIF_WSDL_DIR}') is not set or invalid. ONVIF Camera control will not work.")
        return

    print("Initializing ONVIF Camera System...")
    try:
        onvif_mycam = ONVIFCamera(ONVIF_CAMERA_IP, ONVIF_CAMERA_PORT, ONVIF_USERNAME, ONVIF_PASSWORD, ONVIF_WSDL_DIR)
        print(f"  Connected to ONVIFCamera object for {ONVIF_CAMERA_IP}")

        # Create a test PTZ service to ensure it's available
        ptz_service_test = onvif_mycam.create_ptz_service()
        if not ptz_service_test:
            print("  Failed to create PTZ service client during ONVIF initialization.")
            onvif_mycam = None # Clear if setup failed
            return
        print("  PTZ service client creation test successful.")

        media_service = onvif_mycam.create_media_service()
        profiles = media_service.GetProfiles()
        if not profiles:
            print("  Error: No media profiles found on ONVIF camera.")
            onvif_mycam = None
            return
        
        onvif_active_profile_token = profiles[0].token
        print(f"  Using ONVIF profile token: {onvif_active_profile_token}")
        
        # Fetch initial position (optional, but good for testing connection)
        # initial_pan, initial_tilt, initial_zoom = onvif_update_and_get_current_position()
        # print(f"  Initial ONVIF Cam Pos: P={initial_pan}, T={initial_tilt}, Z={initial_zoom}")
        
        onvif_camera_initialized.set() # Signal success
        print("ONVIF Camera System Initialized Successfully.")

    except Exception as e:
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"!!! ERROR during ONVIF Camera System initialization: {e}")
        print(f"!!! Check IP, port, credentials, and WSDL_DIR.       ")
        print(f"!!! ONVIF Camera control will be DISABLED.           ")
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        onvif_mycam = None
        onvif_active_profile_token = None


@app.route('/tts', methods=['POST', 'OPTIONS'])
def text_to_speech():
    # ... (Your existing TTS route remains unchanged) ...
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response
    try:
        if request.is_json:
            data = request.get_json()
            if 'chatmessage' in data:
                text_input = data.get('chatmessage', '').strip()
                chat_name = data.get('chatname', '')
                if 'request' in data and isinstance(data['request'], dict):
                    username = data['request'].get('username', '')
                    print(f"Message from {username or chat_name}: {text_input}")
            else:
                text_input = data.get('text', '').strip()
        else:
            text_input = request.data.decode('utf-8').strip()
            print(f"Received plain text: {text_input}")
        if not text_input: return jsonify({'error': 'No text provided'}), 400
        start_time = time.time()
        if use_combined_endpoint:
            audio_bytes, blendshapes = get_tts_with_blendshapes(text_input, voice_name)
            if audio_bytes and blendshapes:
                generation_time = time.time() - start_time
                print(f"Generation took {generation_time:.2f} seconds.")
                if ENABLE_EMOTE_CALLS: EmoteConnect.send_emote("startspeaking")
                try: run_audio_animation(audio_bytes, blendshapes, py_face, socket_connection, default_animation_thread)
                finally:
                    if ENABLE_EMOTE_CALLS: EmoteConnect.send_emote("stopspeaking")
                save_generated_data(audio_bytes, blendshapes)
            else: return jsonify({'error': 'Failed to retrieve audio and blendshapes from the API'}), 500
        else:
            if use_elevenlabs: audio_bytes = get_elevenlabs_audio(text_input, voice_name)
            else: audio_bytes = call_local_tts(text_input)
            if audio_bytes:
                generated_facial_data = send_audio_to_neurosync(audio_bytes)
                if generated_facial_data is not None:
                    generation_time = time.time() - start_time
                    print(f"Generation took {generation_time:.2f} seconds.")
                    if ENABLE_EMOTE_CALLS: EmoteConnect.send_emote("startspeaking")
                    try: run_audio_animation(audio_bytes, generated_facial_data, py_face, socket_connection, default_animation_thread)
                    finally:
                        if ENABLE_EMOTE_CALLS: EmoteConnect.send_emote("stopspeaking")
                    save_generated_data(audio_bytes, generated_facial_data)
                else: return jsonify({'error': 'Failed to get blendshapes from the API'}), 500
            else: return jsonify({'error': 'Failed to generate audio'}), 500
        return jsonify({'message': 'Speech and animation generated successfully'}), 200
    except Exception as e:
        print(f"Error: {e}"); return jsonify({'error': str(e)}), 500


# --- Create the OSC Client ---
# ... (Your existing OSC client setup remains unchanged) ...
try:
    osc_client = udp_client.SimpleUDPClient(RECEIVER_IP, RECEIVER_PORT)
    print(f"OSC client configured to send to {RECEIVER_IP}:{RECEIVER_PORT}")
except Exception as e:
    print(f"!!!!!!!!!!!!!! ERROR creating OSC client: {e} !!!!!!!!!!!!!!")
    osc_client = None

# --- Load Keywords from keywords.py ---
# ... (Your existing keyword loading logic remains unchanged) ...
LOADED_KEYWORDS = [] 
try:
    from keywords import keyword_list 
    LOADED_KEYWORDS = keyword_list
    if not LOADED_KEYWORDS: print("Warning: keyword_list from keywords.py is empty.")
    else: print(f"Loaded {len(LOADED_KEYWORDS)} keywords from keywords.py.")
except ImportError: print("Error: Could not import 'keyword_list' from keywords.py.")
except Exception as e: print(f"Error loading keywords from keywords.py: {e}")


@app.route('/receive_chat', methods=OSC_CHAT_ROUTE_METHOD)
def receive_chat_message():
    # ... (Your existing /receive_chat route remains unchanged) ...
    data = request.get_json()
    if not data or 'chatmessage' not in data:
        return jsonify({"status": "error", "message": "Missing 'chatmessage' in JSON payload"}), 400
    ai_response = data.get('chatmessage', '')
    sender = data.get('sender', 'Unknown')
    timestamp = data.get('timestamp', time.time())
    print(f"\nReceived from {sender} at {timestamp}: {ai_response}")
    keywords_to_send_via_osc = []
    if LOADED_KEYWORDS:
        ai_response_lower = ai_response.lower()
        for keyword_from_list in LOADED_KEYWORDS:
            if isinstance(keyword_from_list, str):
                if keyword_from_list.lower() in ai_response_lower:
                    keywords_to_send_via_osc.append(keyword_from_list)
            else: print(f"Warning: Non-string item in LOADED_KEYWORDS: {keyword_from_list}")
    if not keywords_to_send_via_osc:
        return jsonify({"status": "success", "message": "Received, no OSC keywords found"})
    if not osc_client:
        return jsonify({"status": "success", "message": "Received, OSC keywords found but client inactive"})
    print(f" -> Found OSC keywords to send: {keywords_to_send_via_osc}")
    sent_count = 0; errors = []
    for command_text in keywords_to_send_via_osc:
        try:
            osc_client.send_message(OSC_ADDRESS, [command_text, True])
            print(f"    Sent OSC: {OSC_ADDRESS} -> '{command_text}' with True")
            sent_count += 1
        except Exception as e:
            error_msg = f"Failed to send OSC for '{command_text}': {e}"; print(f"   !!! ERROR: {error_msg}"); errors.append(error_msg)
    if errors: return jsonify({"status": "partial_error", "message": f"Attempted {len(keywords_to_send_via_osc)} OSC. Sent {sent_count}, {len(errors)} errors.", "errors": errors}), 500
    else: return jsonify({"status": "success", "message": f"Received. Sent {sent_count} OSC keyword message(s)."})

# --- NEW FLASK ROUTE FOR ONVIF CAMERA CONTROL ---
@app.route('/onvif_command', methods=['POST', 'OPTIONS'])
def flask_onvif_command():
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type') # Add other headers if needed
        return response

    if not ENABLE_ONVIF_CAMERA:
        return jsonify({"status": "error", "message": "ONVIF camera control is disabled by server configuration."}), 503 # Service Unavailable
    
    if not onvif_camera_initialized.is_set(): # Check if ONVIF system is ready
        return jsonify({"status": "error", "message": "ONVIF camera system not initialized or failed to initialize. Check server logs."}), 503

    command_string = request.data.decode('utf-8').strip()
    if not command_string:
        return jsonify({"status": "error", "message": "Empty command string received for ONVIF"}), 400

    print(f"Received ONVIF command string: '{command_string}'")
    parsed_cmd = onvif_parse_command_string(command_string)

    if not parsed_cmd:
        return jsonify({"status": "error", "message": f"Invalid ONVIF command format: '{command_string}'"}), 400

    action = parsed_cmd.get("action")
    direction = parsed_cmd.get("direction")
    value = parsed_cmd.get("value")
    unit = parsed_cmd.get("unit") # Expected to be 'degrees' or 'percent' by parser for relevant actions

    pan_translation, tilt_translation, zoom_translation = 0.0, 0.0, 0.0
    success = False
    message = "ONVIF command received." # Default message

    # Note: ONVIF 'stop' is typically for ContinuousMove. RelativeMove is discrete.
    # If you add ContinuousMove later, a 'stop' action here would call _onvif_generic_stop_move.
    if action == "stop": # This is more conceptual for RelativeMove, as it stops after moving.
        message = "ONVIF 'stop' action received (RelativeMove is discrete, so no explicit stop needed after move)."
        # If you had a continuous move initiated by another command, you'd call a stop function here.
        # For now, just acknowledge.
        success = True # No actual ONVIF stop needed for relative moves
    elif action == "pan":
        if unit != "degrees" or value is None:
            return jsonify({"status": "error", "message": "Pan command needs value in degrees"}), 400
        translation_val = value * ONVIF_DEGREES_TO_PAN_TILT_TRANSLATION_UNIT
        pan_translation = -translation_val if direction == "left" else translation_val
        success = _onvif_generic_relative_move(pan_translation, 0.0, 0.0)
        message = f"ONVIF Pan {direction} by {value} deg (trans {pan_translation:.3f}) processed."
    elif action == "tilt":
        if unit != "degrees" or value is None:
            return jsonify({"status": "error", "message": "Tilt command needs value in degrees"}), 400
        translation_val = value * ONVIF_DEGREES_TO_PAN_TILT_TRANSLATION_UNIT
        tilt_translation = translation_val if direction == "up" else -translation_val
        success = _onvif_generic_relative_move(0.0, tilt_translation, 0.0)
        message = f"ONVIF Tilt {direction} by {value} deg (trans {tilt_translation:.3f}) processed."
    elif action == "zoom":
        if unit != "percent" or value is None: # Assuming "percent" for relative zoom
            return jsonify({"status": "error", "message": "Zoom command needs value in percent"}), 400
        translation_val = value * ONVIF_PERCENT_TO_ZOOM_TRANSLATION_UNIT
        zoom_translation = translation_val if direction == "in" else -translation_val
        success = _onvif_generic_relative_move(0.0, 0.0, zoom_translation)
        message = f"ONVIF Zoom {direction} by {value} % (trans {zoom_translation:.3f}) processed."
    else:
        return jsonify({"status": "error", "message": f"Unknown ONVIF action: {action}"}), 400

    if success:
        # For immediate feedback on position after move (optional, adds slight delay)
        # current_pan, current_tilt, current_zoom = onvif_update_and_get_current_position()
        return jsonify({
            "status": "success", 
            "message": message,
            "onvif_command_parsed": parsed_cmd,
            # "onvif_final_position": {"pan": current_pan, "tilt": current_tilt, "zoom": current_zoom}
            }), 200
    else:
        # If success is False but no specific error was returned by earlier checks
        if message == "ONVIF command received.": # Default message means action wasn't handled
             message = f"Failed to execute ONVIF command: '{command_string}'. Action not fully processed."

        return jsonify({"status": "error", "message": message}), 500

@app.route('/shutdown', methods=['POST', 'OPTIONS'])
def shutdown():
    # ... (Your existing shutdown route remains unchanged) ...
    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response
    try:
        stop_default_animation.set()
        if default_animation_thread: default_animation_thread.join()
        pygame.quit()
        if socket_connection: socket_connection.close() # Check if it exists
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None: raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return jsonify({'message': 'Server shutting down'}), 200
    except Exception as e: return jsonify({'error': str(e)}), 500

# Add a simple interactive mode if running directly
def interactive_mode():
    # ... (Your existing interactive mode remains largely unchanged) ...
    # If you want interactive ONVIF commands, you'd add logic here too.
    # For brevity, I'm omitting interactive ONVIF control.
    try:
        while True:
            text_input = input("Enter text for TTS (or 'onvif <cmd>' or 'q' to quit): ").strip()
            if text_input.lower() == 'q': break
            
            # Simple interactive ONVIF command hook
            if text_input.lower().startswith("onvif "):
                if not ENABLE_ONVIF_CAMERA or not onvif_camera_initialized.is_set():
                    print("ONVIF control not available/initialized for interactive mode.")
                    continue
                onvif_cmd_str = text_input[len("onvif "):].strip()
                print(f"Sending ONVIF cmd: '{onvif_cmd_str}'")
                # Mimic the POST request data for the handler (not a real POST)
                # This is a simplified way to test the logic path
                # For a real test, use curl or Postman against the running server.
                
                parsed_cmd = onvif_parse_command_string(onvif_cmd_str)
                if not parsed_cmd: 
                    print(f"Invalid ONVIF command: {onvif_cmd_str}")
                    continue

                action = parsed_cmd.get("action")
                direction = parsed_cmd.get("direction")
                value = parsed_cmd.get("value")
                unit = parsed_cmd.get("unit")
                pan_t, tilt_t, zoom_t = 0.0,0.0,0.0
                
                if action == "pan":
                    val = value * ONVIF_DEGREES_TO_PAN_TILT_TRANSLATION_UNIT
                    pan_t = -val if direction == "left" else val
                    _onvif_generic_relative_move(pan_t, 0.0, 0.0)
                elif action == "tilt":
                    val = value * ONVIF_DEGREES_TO_PAN_TILT_TRANSLATION_UNIT
                    tilt_t = val if direction == "up" else -val
                    _onvif_generic_relative_move(0.0, tilt_t, 0.0)
                elif action == "zoom":
                    val = value * ONVIF_PERCENT_TO_ZOOM_TRANSLATION_UNIT
                    zoom_t = val if direction == "in" else -val
                    _onvif_generic_relative_move(0.0, 0.0, zoom_t)
                else:
                    print(f"Interactive ONVIF action '{action}' not handled here.")
                continue # Go back to input prompt


            elif text_input: # TTS part
                start_time = time.time()
                if use_combined_endpoint:
                    # ... (TTS logic)
                    audio_bytes, blendshapes = get_tts_with_blendshapes(text_input, voice_name)
                    if audio_bytes and blendshapes:
                        # ... (animation logic)
                        run_audio_animation(audio_bytes, blendshapes, py_face, socket_connection, default_animation_thread)

                    else: print("❌ Failed to retrieve audio and blendshapes from the API.")
                else:
                    # ... (TTS logic)
                    if use_elevenlabs: audio_bytes = get_elevenlabs_audio(text_input, voice_name)
                    else: audio_bytes = call_local_tts(text_input)
                    if audio_bytes:
                        # ... (animation logic)
                        generated_facial_data = send_audio_to_neurosync(audio_bytes)
                        if generated_facial_data is not None:
                             run_audio_animation(audio_bytes, generated_facial_data, py_face, socket_connection, default_animation_thread)
                        else: print("❌ Failed to get blendshapes from the API.")
                    else: print("❌ Failed to generate audio.")
            else: print("⚠️ No text provided.")
    finally:
        stop_default_animation.set()
        if default_animation_thread: default_animation_thread.join()
        pygame.quit()
        if socket_connection: socket_connection.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the TTS and animation system.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--web", action="store_true", help="Run in web server mode (Flask).")
    group.add_argument("--interactive", action="store_true", help="Run in interactive command-line mode.")
    args = parser.parse_args()

    if args.web:
        # Initialize ONVIF Camera system BEFORE starting Flask app
        if ENABLE_ONVIF_CAMERA:
            initialize_onvif_camera_system() # Try to initialize it
        app.run(debug=False, port=13000, host='0.0.0.0')  # Added host='0.0.0.0'
    elif args.interactive:
        if ENABLE_ONVIF_CAMERA:
            initialize_onvif_camera_system()
        interactive_mode()