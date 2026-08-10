import time
import os
import sys
import threading
import re # For parsing the command string
from flask import Flask, request, jsonify
from onvif import ONVIFCamera

# --- Try to import keyboard, provide instructions if it fails ---
KEYBOARD_ENABLED = True # Set to False to disable keyboard control
# ... (keyboard import logic remains the same as previous version) ...
try:
    import keyboard
except ImportError:
    print("INFO: 'keyboard' library not installed or import failed. Keyboard control will be disabled.")
    KEYBOARD_ENABLED = False
except Exception as e:
    if "You must be root to use this library on linux" in str(e): # Basic check
        print(f"Error importing keyboard: {e}")
        print("On Linux, 'keyboard' library often requires root privileges.")
        print("Keyboard control will be disabled.")
    else:
        print(f"An unexpected error occurred importing keyboard: {e}")
        print("Keyboard control will be disabled.")
    KEYBOARD_ENABLED = False

# --- Configuration - MODIFY THESE ---
CAMERA_IP = '192.168.1.100'
ONVIF_PORT = 80
USERNAME = 'admin'
PASSWORD = 'password'

# --- WSDL Directory ---
# ... (WSDL_DIR logic remains the same) ...
try:
    import onvif_zeep
    WSDL_DIR = os.path.join(os.path.dirname(onvif_zeep.__file__), 'wsdl')
except ImportError:
    print("Could not auto-detect WSDL directory. Please set it manually.")
    WSDL_DIR = '/path/to/your/onvif_zeep/wsdl' # <-- !!! IMPORTANT: SET THIS MANUALLY IF NEEDED !!!


# --- CALIBRATION VALUES (YOU MUST ADJUST THESE FOR YOUR CAMERA!) ---
# These are EXAMPLE values. Experiment to find what works for your camera.
# For a 'RelativeMove' command.
# Value such that: degrees * DEGREES_TO_PAN_TILT_TRANSLATION_UNIT = ONVIF translation
# Example: If 10 degrees pan = 0.1 ONVIF translation, then this is 0.1/10 = 0.01
DEGREES_TO_PAN_TILT_TRANSLATION_UNIT = 0.01

# Value such that: percent * PERCENT_TO_ZOOM_TRANSLATION_UNIT = ONVIF translation
# Example: If 20% zoom change = 0.2 ONVIF translation, then this is 0.2/20 = 0.01
PERCENT_TO_ZOOM_TRANSLATION_UNIT = 0.01

# Default speed for relative moves if not specified by command/request
DEFAULT_RELATIVE_MOVE_SPEED = 0.5


# --- Movement Parameters for Keyboard (if enabled) ---
PAN_SPEED_KEYBOARD = 0.5
TILT_SPEED_KEYBOARD = 0.5
ZOOM_SPEED_KEYBOARD = 0.5

# --- Global ONVIF and State Variables ---
mycam = None
active_profile_token = None
# ... (keyboard state variables remain the same if KEYBOARD_ENABLED) ...
# For keyboard state
current_kb_pan_velocity = 0.0
current_kb_tilt_velocity = 0.0
current_kb_zoom_velocity = 0.0
kb_is_moving = False

_current_onvif_pan = None
_current_onvif_tilt = None
_current_onvif_zoom = None
position_lock = threading.Lock()

# --- Flask App ---
app = Flask(__name__)

# --- Helper Functions (ONVIF Operations, Position Update, etc.) ---
# ... (get_ptz_service_instance, update_and_get_current_position, print_current_position_console) ...
# ... (_generic_continuous_move, _generic_stop_move, _generic_relative_move) ...
# These functions remain largely the same as the previous version.
# Make sure _generic_relative_move uses the translation values directly.

def get_ptz_service_instance():
    if not mycam:
        raise Exception("ONVIFCamera (mycam) not initialized.")
    return mycam.create_ptz_service()

def update_and_get_current_position(ptz_service_instance=None):
    global _current_onvif_pan, _current_onvif_tilt, _current_onvif_zoom
    if not active_profile_token: return None, None, None
    ptz = ptz_service_instance if ptz_service_instance else get_ptz_service_instance()
    if not ptz: return _current_onvif_pan, _current_onvif_tilt, _current_onvif_zoom
    local_pan, local_tilt, local_zoom = None, None, None
    try:
        status_request = ptz.create_type('GetStatus')
        status_request.ProfileToken = active_profile_token
        ptz_status = ptz.GetStatus(status_request)
        if ptz_status and ptz_status.Position:
            if ptz_status.Position.PanTilt:
                local_pan = ptz_status.Position.PanTilt.x
                local_tilt = ptz_status.Position.PanTilt.y
            if ptz_status.Position.Zoom:
                local_zoom = ptz_status.Position.Zoom.x
        with position_lock:
            _current_onvif_pan = local_pan if local_pan is not None else _current_onvif_pan
            _current_onvif_tilt = local_tilt if local_tilt is not None else _current_onvif_tilt
            _current_onvif_zoom = local_zoom if local_zoom is not None else _current_onvif_zoom
            return_pan, return_tilt, return_zoom = _current_onvif_pan, _current_onvif_tilt, _current_onvif_zoom
        # print_current_position_console() # Commented out to reduce noise during API calls
        return return_pan, return_tilt, return_zoom
    except Exception as e:
        print(f"Error getting PTZ status: {e}")
        with position_lock:
            return _current_onvif_pan, _current_onvif_tilt, _current_onvif_zoom

def print_current_position_console(): # Keep for keyboard
    with position_lock:
        pan_str = f"{_current_onvif_pan:.3f}" if _current_onvif_pan is not None else "N/A"
        tilt_str = f"{_current_onvif_tilt:.3f}" if _current_onvif_tilt is not None else "N/A"
        zoom_str = f"{_current_onvif_zoom:.3f}" if _current_onvif_zoom is not None else "N/A"
    sys.stdout.write(f"\rCONSOLE Pos: Pan={pan_str}, Tilt={tilt_str}, Zoom={zoom_str}      ")
    sys.stdout.flush()

def _generic_continuous_move(pan_velocity, tilt_velocity, zoom_velocity, ptz_service_instance=None):
    if not active_profile_token: return False
    ptz = ptz_service_instance if ptz_service_instance else get_ptz_service_instance()
    if not ptz: return False
    request = ptz.create_type('ContinuousMove')
    request.ProfileToken = active_profile_token
    request.Velocity = ptz.zeep_client.get_element('ns0:PTZSpeed')()
    request.Velocity.PanTilt = ptz.zeep_client.get_element('ns0:Vector2D')()
    request.Velocity.PanTilt.x = pan_velocity
    request.Velocity.PanTilt.y = tilt_velocity
    request.Velocity.Zoom = ptz.zeep_client.get_element('ns0:Vector1D')()
    request.Velocity.Zoom.x = zoom_velocity
    try:
        ptz.ContinuousMove(request)
        return True
    except Exception as e:
        print(f"\nError sending ContinuousMove: {e}")
        return False

def _generic_stop_move(stop_pan_tilt=True, stop_zoom=True, ptz_service_instance=None):
    if not active_profile_token: return False
    ptz = ptz_service_instance if ptz_service_instance else get_ptz_service_instance()
    if not ptz: return False
    request = ptz.create_type('Stop')
    request.ProfileToken = active_profile_token
    request.PanTilt = stop_pan_tilt
    request.Zoom = stop_zoom
    try:
        ptz.Stop(request)
        time.sleep(0.1) # Small delay for stop to register before getting status
        update_and_get_current_position(ptz_service_instance=ptz if ptz_service_instance else None)
        return True
    except Exception as e:
        print(f"\nError sending Stop: {e}")
        return False

def _generic_relative_move(pan_translation, tilt_translation, zoom_translation,
                           pan_speed=DEFAULT_RELATIVE_MOVE_SPEED,
                           tilt_speed=DEFAULT_RELATIVE_MOVE_SPEED,
                           zoom_speed=DEFAULT_RELATIVE_MOVE_SPEED,
                           ptz_service_instance=None):
    if not active_profile_token: return False
    ptz = ptz_service_instance if ptz_service_instance else get_ptz_service_instance()
    if not ptz: return False
    request = ptz.create_type('RelativeMove')
    request.ProfileToken = active_profile_token
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
        time.sleep(0.5) # Give camera time to move
        update_and_get_current_position(ptz_service_instance=ptz if ptz_service_instance else None)
        return True
    except Exception as e:
        print(f"\nError sending RelativeMove: {e}")
        return False

# --- Command Parsing Logic ---
def parse_command_string(command_str):
    """
    Parses a command string like "pan left 10 degrees" or "zoom in 20 percent".
    Returns a dictionary with action, direction, value, unit or None if parsing fails.
    """
    # Regex to capture action (pan, tilt, zoom), direction (left, right, up, down, in, out),
    # value (numeric), and unit (degrees, percent).
    # Making direction and unit optional for simpler commands like "stop"
    pattern = re.compile(
        r"^(pan|tilt|zoom|stop)\s*(left|right|up|down|in|out)?\s*(\d+\.?\d*)?\s*(degrees|percent|level)?$",
        re.IGNORECASE
    )
    match = pattern.match(command_str.strip())

    if not match:
        return None

    action, direction, value_str, unit = match.groups()

    parsed = {"action": action.lower()}
    if direction:
        parsed["direction"] = direction.lower()
    if value_str:
        try:
            parsed["value"] = float(value_str)
        except ValueError:
            return None # Value not a valid number
    if unit:
        parsed["unit"] = unit.lower()
    
    # Basic validation
    if action == "pan" and direction not in ["left", "right"]: return None
    if action == "tilt" and direction not in ["up", "down"]: return None
    if action == "zoom" and direction not in ["in", "out"]: return None
    if action in ["pan", "tilt", "zoom"] and ("value" not in parsed or "unit" not in parsed):
        if action == "zoom" and "unit" not in parsed and "value" in parsed: # allow "zoom 50" to mean level
             if parsed.get("unit") is None: parsed["unit"] = "level" # default to 'level' for zoom if no unit
        elif not (action == "zoom" and parsed.get("unit") == "level"): # For zoom level, value is enough
            return None # Missing value or unit for pan/tilt/zoom percentage movements

    return parsed

# --- Flask Routes ---
@app.route('/command', methods=['POST'])
def flask_command():
    command_string = request.data.decode('utf-8') # Get raw POST data as string
    if not command_string:
        return jsonify({"status": "error", "message": "Empty command string"}), 400

    print(f"Received command string: '{command_string}'")
    parsed_cmd = parse_command_string(command_string)

    if not parsed_cmd:
        return jsonify({"status": "error", "message": f"Invalid command format: '{command_string}'"}), 400

    action = parsed_cmd.get("action")
    direction = parsed_cmd.get("direction")
    value = parsed_cmd.get("value")
    unit = parsed_cmd.get("unit")

    pan_translation = 0.0
    tilt_translation = 0.0
    zoom_translation = 0.0
    success = False

    if action == "stop":
        success = _generic_stop_move(stop_pan_tilt=True, stop_zoom=True)
        message = "Stop command processed."

    elif action == "pan":
        if unit != "degrees" or value is None:
            return jsonify({"status": "error", "message": "Pan command requires value in degrees (e.g., 'pan left 10 degrees')"}), 400
        translation_value = value * DEGREES_TO_PAN_TILT_TRANSLATION_UNIT
        if direction == "left":
            pan_translation = -translation_value
        elif direction == "right":
            pan_translation = translation_value
        success = _generic_relative_move(pan_translation, tilt_translation, zoom_translation)
        message = f"Pan {direction} by {value} degrees (approx. translation {pan_translation:.3f}) command processed."
    
    elif action == "tilt":
        if unit != "degrees" or value is None:
            return jsonify({"status": "error", "message": "Tilt command requires value in degrees (e.g., 'tilt up 5 degrees')"}), 400
        translation_value = value * DEGREES_TO_PAN_TILT_TRANSLATION_UNIT
        if direction == "up":
            tilt_translation = translation_value # Positive Y is often UP
        elif direction == "down":
            tilt_translation = -translation_value
        success = _generic_relative_move(pan_translation, tilt_translation, zoom_translation)
        message = f"Tilt {direction} by {value} degrees (approx. translation {tilt_translation:.3f}) command processed."

    elif action == "zoom":
        if unit == "percent" and value is not None: # Relative zoom by percentage
            translation_value = value * PERCENT_TO_ZOOM_TRANSLATION_UNIT
            if direction == "in":
                zoom_translation = translation_value
            elif direction == "out":
                zoom_translation = -translation_value
            success = _generic_relative_move(pan_translation, tilt_translation, zoom_translation)
            message = f"Zoom {direction} by {value} percent (approx. translation {zoom_translation:.3f}) command processed."
        # Placeholder for absolute zoom if needed later using AbsoluteMove and GetStatus with limits
        # elif unit == "level" and value is not None:
        #     # This would require AbsoluteMove and knowing the camera's zoom range (0.0 to 1.0)
        #     # zoom_level = max(0.0, min(1.0, value / 100.0)) # Assuming value is 0-100 for level
        #     # success = _generic_absolute_move(pan_abs, tilt_abs, zoom_abs=zoom_level)
        #     message = f"Absolute zoom to level {value} (approx. {zoom_level:.3f}) - NOT YET FULLY IMPLEMENTED FOR ABSOLUTE."
        #     return jsonify({"status": "info", "message": message}), 501 # Not Implemented
        else:
            return jsonify({"status": "error", "message": "Zoom command requires value and unit (e.g., 'zoom in 10 percent')"}), 400


    else: # Should not happen if parse_command_string is correct
        return jsonify({"status": "error", "message": "Unknown action"}), 400

    if success:
        # update_and_get_current_position() # _generic_relative_move and _generic_stop_move already call this
        pan, tilt, zoom = update_and_get_current_position() # Get fresh values after move
        return jsonify({
            "status": "success", 
            "message": message,
            "command_parsed": parsed_cmd,
            "final_position": {"pan": pan, "tilt": tilt, "zoom": zoom}
            }), 200
    else:
        return jsonify({"status": "error", "message": f"Failed to execute command: {command_string}"}), 500


@app.route('/position', methods=['GET'])
def flask_get_position():
    # ... (remains the same) ...
    pan, tilt, zoom = update_and_get_current_position()
    if pan is not None or tilt is not None or zoom is not None:
        return jsonify({
            "status": "success",
            "pan": pan,
            "tilt": tilt,
            "zoom": zoom
        }), 200
    else:
        return jsonify({"status": "error", "message": "Could not retrieve position"}), 500

# --- Keyboard Control Functions (if KEYBOARD_ENABLED) ---
# ... (keyboard functions kb_perform_continuous_move, kb_stop_move, on_press, on_release remain the same) ...
if KEYBOARD_ENABLED:
    def kb_perform_continuous_move(pan_velocity, tilt_velocity, zoom_velocity=0.0):
        global kb_is_moving, current_kb_pan_velocity, current_kb_tilt_velocity, current_kb_zoom_velocity
        current_kb_pan_velocity = pan_velocity; current_kb_tilt_velocity = tilt_velocity; current_kb_zoom_velocity = zoom_velocity
        success = _generic_continuous_move(pan_velocity, tilt_velocity, zoom_velocity)
        if success: kb_is_moving = (pan_velocity != 0.0 or tilt_velocity != 0.0 or zoom_velocity != 0.0)
        return success

    def kb_stop_move(stop_pan_tilt=True, stop_zoom=True):
        global kb_is_moving, current_kb_pan_velocity, current_kb_tilt_velocity, current_kb_zoom_velocity
        success = _generic_stop_move(stop_pan_tilt, stop_zoom)
        if success:
            if stop_pan_tilt: current_kb_pan_velocity = 0.0; current_kb_tilt_velocity = 0.0
            if stop_zoom: current_kb_zoom_velocity = 0.0
            kb_is_moving = (current_kb_pan_velocity != 0.0 or current_kb_tilt_velocity != 0.0 or current_kb_zoom_velocity != 0.0)
            if not kb_is_moving: sys.stdout.write("\rKB Movement stopped.                                           \n")
        return success

    def on_press(key_event):
        global current_kb_pan_velocity, current_kb_tilt_velocity, current_kb_zoom_velocity
        try:
            key_name = key_event.name
            new_pan,new_tilt,new_zoom = current_kb_pan_velocity,current_kb_tilt_velocity,current_kb_zoom_velocity
            if key_name == 'left': new_pan = -PAN_SPEED_KEYBOARD
            elif key_name == 'right': new_pan = PAN_SPEED_KEYBOARD
            elif key_name == 'up': new_tilt = TILT_SPEED_KEYBOARD
            elif key_name == 'down': new_tilt = -TILT_SPEED_KEYBOARD
            elif key_name == '+': new_zoom = ZOOM_SPEED_KEYBOARD
            elif key_name == '-': new_zoom = -ZOOM_SPEED_KEYBOARD
            elif key_name == 's': kb_stop_move(True, True); return
            elif key_name in ['q', 'esc']: return
            if key_name in ['left', 'right', 'up', 'down', '+', '-']:
                if new_pan!=current_kb_pan_velocity or new_tilt!=current_kb_tilt_velocity or new_zoom!=current_kb_zoom_velocity:
                    sys.stdout.write(f"\rKB Moving: P={new_pan:.1f} T={new_tilt:.1f} Z={new_zoom:.1f}         "); sys.stdout.flush()
                    kb_perform_continuous_move(new_pan, new_tilt, new_zoom)
        except Exception as e: print(f"\nError in on_press: {e}")

    def on_release(key_event):
        global current_kb_pan_velocity, current_kb_tilt_velocity, current_kb_zoom_velocity
        try:
            key_name = key_event.name
            stop_p,stop_t,stop_z = False,False,False
            if key_name == 'left' and current_kb_pan_velocity < 0: stop_p=True
            elif key_name == 'right' and current_kb_pan_velocity > 0: stop_p=True
            elif key_name == 'up' and current_kb_tilt_velocity > 0: stop_t=True
            elif key_name == 'down' and current_kb_tilt_velocity < 0: stop_t=True
            elif key_name == '+' and current_kb_zoom_velocity > 0: stop_z=True
            elif key_name == '-' and current_kb_zoom_velocity < 0: stop_z=True
            changed_pt,changed_z = False,False
            if stop_p: current_kb_pan_velocity=0.0; changed_pt=True
            if stop_t: current_kb_tilt_velocity=0.0; changed_pt=True
            if stop_z: current_kb_zoom_velocity=0.0; changed_z=True
            if changed_pt or changed_z:
                if current_kb_pan_velocity==0.0 and current_kb_tilt_velocity==0.0 and current_kb_zoom_velocity==0.0:
                    kb_stop_move(True,True)
                else:
                    sys.stdout.write(f"\rKB Updating: P={current_kb_pan_velocity:.1f} T={current_kb_tilt_velocity:.1f} Z={current_kb_zoom_velocity:.1f}      "); sys.stdout.flush()
                    kb_perform_continuous_move(current_kb_pan_velocity,current_kb_tilt_velocity,current_kb_zoom_velocity)
        except Exception as e: print(f"\nError in on_release: {e}")

# --- Main Setup and Execution ---
# ... (initialize_camera_system, __main__ loop, Flask thread start, and shutdown logic remain the same) ...
def initialize_camera_system():
    global mycam, active_profile_token
    print(f"Using WSDL directory: {WSDL_DIR}")
    if not os.path.isdir(WSDL_DIR): return False
    try:
        mycam = ONVIFCamera(CAMERA_IP, ONVIF_PORT, USERNAME, PASSWORD, WSDL_DIR)
        print(f"ONVIFCamera object for {CAMERA_IP}:{ONVIF_PORT}")
        ptz_test = mycam.create_ptz_service()
        if not ptz_test: print("Failed PTZ service test."); return False
        print("PTZ service test OK.")
        media_service = mycam.create_media_service()
        profiles = media_service.GetProfiles()
        if not profiles: print("No media profiles."); return False
        active_profile_token = profiles[0].token
        print(f"Profile token: {active_profile_token}")
        print("Fetching initial position..."); update_and_get_current_position()
        return True
    except Exception as e:
        print(f"Error camera setup: {e}"); import traceback; traceback.print_exc()
        return False

if __name__ == '__main__':
    if not initialize_camera_system():
        print("Failed to initialize camera. Exiting."); sys.exit(1)

    if KEYBOARD_ENABLED:
        print("\n--- Keyboard Control Enabled ---")
        print("ARROW KEYS: Pan/Tilt | '+': Zoom In | '-': Zoom Out | 's': Manual Stop")
        print("Press 'q' or 'Esc' in console to quit.")
        keyboard.on_press(on_press); keyboard.on_release(on_release)
        _SCRIPT_RUNNING = True
        def quit_program_kb_hook(e=None):
            global _SCRIPT_RUNNING
            if e and e.name not in ['q', 'esc']: return
            _SCRIPT_RUNNING = False; print("\nQuit by keyboard. Stopping Flask...")
        keyboard.on_press_key("q", quit_program_kb_hook, suppress=False)
        keyboard.on_press_key("esc", quit_program_kb_hook, suppress=True)
    else:
        _SCRIPT_RUNNING = True
        print("\n--- Keyboard Control Disabled ---")

    print("\n--- Flask Web Server ---")
    print(f"Listening for POST/GET requests on http://0.0.0.0:5000")
    print("Endpoints:")
    print("  POST /command        (raw text string, e.g., 'pan left 10 degrees')")
    print("  GET  /position")
    
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False), daemon=True)
    flask_thread.start()

    try:
        while _SCRIPT_RUNNING and flask_thread.is_alive():
            if KEYBOARD_ENABLED: print_current_position_console() # Update console pos if keyboard is on
            time.sleep(0.5)
    except KeyboardInterrupt: print("\nCtrl+C. Shutting down.")
    finally:
        _SCRIPT_RUNNING = False
        print("Cleaning up...")
        if mycam and active_profile_token:
            print("Stopping camera movement..."); _generic_stop_move(True, True)
        if KEYBOARD_ENABLED: keyboard.unhook_all(); print("Keyboard hooks released.")
        print("\nExited.")
        if mycam: # only print if camera was init
             pan_f, tilt_f, zoom_f = update_and_get_current_position()
             print(f"Final Pos: P={pan_f}, T={tilt_f}, Z={zoom_f}")
        print()