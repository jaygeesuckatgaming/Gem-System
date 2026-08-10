import time
import os
import sys
import zeep # For zeep.exceptions

# --- Try to import keyboard ---
try:
    import keyboard
except ImportError:
    print("The 'keyboard' library is not installed. Please install it: pip install keyboard")
    sys.exit(1)
except Exception as e:
    if "You must be root to use this library on linux" in str(e):
        print(f"Error importing keyboard: {e}\nOn Linux, try: sudo python your_script.py")
    else:
        print(f"An unexpected error occurred importing keyboard: {e}")
    sys.exit(1)

# --- Attempt to import ONVIFCamera ---
try:
    from onvif import ONVIFCamera # Should be from a synchronous onvif-zeep
    print("Successfully imported 'ONVIFCamera'.")
except ImportError as e:
    print(f"CRITICAL ERROR: Failed to import 'ONVIFCamera'. Exception: {e}")
    print("Ensure 'onvif-zeep' is installed correctly in your virtual environment.")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred importing ONVIFCamera: {e}")
    sys.exit(1)

# --- Configuration ---
ENABLE_ONVIF_CONTROL = True
CAMERA_IP = '192.168.1.100'
ONVIF_PORT = 2020
USERNAME = 'jaygee'
PASSWORD = '1248aceg'

# --- WSDL Directory Setup ---
_script_dir = os.path.dirname(os.path.abspath(__file__))
# Assumes 'falk_onvif_wsdls' is at the same level as your script
# and directly contains common.xsd, ptz.wsdl, etc., from FalkTannhaeuser's repo.
WSDL_DIR_TO_PASS_TO_CONSTRUCTOR = os.path.join(_script_dir, 'wsdl')
print(f"Attempting to use WSDL_DIR: {WSDL_DIR_TO_PASS_TO_CONSTRUCTOR}")

# --- Movement Parameters & Key Mappings ---
PAN_SPEED_FACTOR = 0.7
TILT_SPEED_FACTOR = 0.7
DEBUG_MOVEMENT = True

# SCAN CODES (VERIFY THESE FOR YOUR SYSTEM'S ARROW KEYS)
# SCAN_CODE_LEFT = 75
SCAN_CODE_LEFT = 44
SCAN_CODE_RIGHT = 77
SCAN_CODE_UP = 72
SCAN_CODE_DOWN = 80
# Swedish key names (for key_event.name, primarily for debug prints now)
KEY_NAME_LEFT = 'vänsterpil'
KEY_NAME_RIGHT = 'högerpil'
KEY_NAME_UP = 'uppil'
KEY_NAME_DOWN = 'nedpil'

# --- Global Variables ---
mycam = None
ptz_service = None
active_media_profile = None
active_profile_token = None
XMAX_VEL, XMIN_VEL, YMAX_VEL, YMIN_VEL = 1.0, -1.0, 1.0, -1.0
PAN_TILT_VELOCITY_SPACE_URI = None
current_pan_velocity, current_tilt_velocity = 0.0, 0.0
is_moving = False

def setup_camera():
    global mycam, ptz_service, active_media_profile, active_profile_token
    global XMAX_VEL, XMIN_VEL, YMAX_VEL, YMIN_VEL, PAN_TILT_VELOCITY_SPACE_URI

    if not os.path.isdir(WSDL_DIR_TO_PASS_TO_CONSTRUCTOR):
        print(f"CRITICAL ERROR: WSDL_DIR '{WSDL_DIR_TO_PASS_TO_CONSTRUCTOR}' not found.")
        print("Ensure you have downloaded WSDLs from FalkTannhaeuser/python-onvif-zeep (the /wsdl folder at repo root)")
        print("and placed its contents into the specified directory.")
        return False

    try:
        print(f"Attempting to connect to camera at {CAMERA_IP}:{ONVIF_PORT} using WSDLs from '{WSDL_DIR_TO_PASS_TO_CONSTRUCTOR}'")
        mycam = ONVIFCamera(CAMERA_IP, ONVIF_PORT, USERNAME, PASSWORD, WSDL_DIR_TO_PASS_TO_CONSTRUCTOR)
        print(f"Successfully connected to camera.")

        ptz_service = mycam.create_ptz_service()
        if not ptz_service: print("Failed to create PTZ service."); mycam = None; return False
        print("PTZ service client created.")

        media_service = mycam.create_media_service()
        if not media_service: print("Failed to create Media service."); mycam = None; return False
        print("Media service client created.")
            
        profiles = media_service.GetProfiles() # This should be synchronous now
        if not profiles: print("Error: No media profiles found."); mycam = None; return False
        
        active_media_profile = profiles[0]
        # Use .token (lowercase) as per previous zeep hint
        active_profile_token = active_media_profile.token
        print(f"Using profile token: {active_profile_token} (Name: {active_media_profile.Name})")

        print("Fetching PTZ configuration options...")
        if hasattr(active_media_profile, 'PTZConfiguration') and active_media_profile.PTZConfiguration:
            ptz_config_token_obj = active_media_profile.PTZConfiguration
            ptz_token_val = ptz_config_token_obj.token # Use .token

            if ptz_token_val:
                request_opts = ptz_service.create_type('GetConfigurationOptions')
                request_opts.ConfigurationToken = ptz_token_val
                ptz_config_options = ptz_service.GetConfigurationOptions(request_opts) # Synchronous

                if ptz_config_options and ptz_config_options.Spaces:
                    if ptz_config_options.Spaces.ContinuousPanTiltVelocitySpace:
                        space = ptz_config_options.Spaces.ContinuousPanTiltVelocitySpace[0]
                        XMAX_VEL = space.XRange.Max; XMIN_VEL = space.XRange.Min
                        YMAX_VEL = space.YRange.Max; YMIN_VEL = space.YRange.Min
                        PAN_TILT_VELOCITY_SPACE_URI = space.URI
                        print(f"  PTZ Speed Ranges: X ({XMIN_VEL:.2f} to {XMAX_VEL:.2f}), Y ({YMIN_VEL:.2f} to {YMAX_VEL:.2f})")
                        print(f"  PanTilt Velocity Space URI: {PAN_TILT_VELOCITY_SPACE_URI}")
                    else: print("  Warning: ContinuousPanTiltVelocitySpace not found.")
                else: print("  Warning: No PTZ Spaces found or ptz_config_options is None.")
            else: print("  Warning: Active media profile's PTZConfiguration has no token.")
        else: print("  Warning: Active media profile has no PTZConfiguration. Using defaults.")
        return True
    except Exception as e:
        print(f"Error during camera setup: {e}")
        if "isodate" in str(e) and "ValueError: not enough values to unpack" in str(e):
            print(">>> DETECTED ISODATE ERROR: Camera likely sending malformed timestamp.")
        import traceback; traceback.print_exc(); mycam = None; return False

def perform_continuous_move(pan_velocity_factor, tilt_velocity_factor):
    global ptz_service, active_profile_token, is_moving, current_pan_velocity, current_tilt_velocity
    global XMAX_VEL, XMIN_VEL, YMAX_VEL, YMIN_VEL, PAN_TILT_VELOCITY_SPACE_URI

    actual_pan_velocity = 0.0
    if pan_velocity_factor > 0: actual_pan_velocity = XMAX_VEL * pan_velocity_factor
    elif pan_velocity_factor < 0: actual_pan_velocity = XMIN_VEL * abs(pan_velocity_factor)
    actual_tilt_velocity = 0.0
    if tilt_velocity_factor > 0: actual_tilt_velocity = YMAX_VEL * tilt_velocity_factor
    elif tilt_velocity_factor < 0: actual_tilt_velocity = YMIN_VEL * abs(tilt_velocity_factor)

    if DEBUG_MOVEMENT:
        print(f"[DEBUG MOVE] Factors pan_f={pan_velocity_factor:.2f}, tilt_f={tilt_velocity_factor:.2f}")
        print(f"[DEBUG MOVE] Actual vels: pan={actual_pan_velocity:.2f}, tilt={actual_tilt_velocity:.2f}. is_moving: {is_moving}")

    if not ptz_service or not active_profile_token: print("PTZ service/token not available."); return
    current_pan_velocity = actual_pan_velocity; current_tilt_velocity = actual_tilt_velocity
    if abs(actual_pan_velocity) < 1e-5 and abs(actual_tilt_velocity) < 1e-5 and not is_moving:
        if DEBUG_MOVEMENT: print("[DEBUG MOVE] Vels zero & not moving. Returning."); return

    request = ptz_service.create_type('ContinuousMove')
    request.ProfileToken = active_profile_token
    
    ONVIF_TYPES_NAMESPACE = '{http://www.onvif.org/ver10/schema}' # From common.xsd
    try:
        # Using PTZVector as it's more common if PTZSpeed isn't found,
        # and assuming common.xsd from FalkTannhaeuser's repo defines it.
        request.Velocity = ptz_service.zeep_client.get_element(ONVIF_TYPES_NAMESPACE + 'PTZVector')()
        request.Velocity.PanTilt = ptz_service.zeep_client.get_element(ONVIF_TYPES_NAMESPACE + 'Vector2D')()
        
        space_attr_name = 'space' if hasattr(request.Velocity.PanTilt, 'space') else ('_space' if hasattr(request.Velocity.PanTilt, '_space') else None)
        if PAN_TILT_VELOCITY_SPACE_URI and space_attr_name:
            setattr(request.Velocity.PanTilt, space_attr_name, PAN_TILT_VELOCITY_SPACE_URI)
        elif DEBUG_MOVEMENT: print("[DEBUG MOVE] PanTilt.space URI not set.")
    except zeep.exceptions.LookupError as e_lookup:
        print(f"ERROR in MOVE (Velocity Setup): Failed to find PTZ types in {ONVIF_TYPES_NAMESPACE}.")
        print(f"LookupError: {e_lookup}")
        if hasattr(e_lookup, 'message') and "Available elements are" in str(e_lookup.message): print(str(e_lookup.message))
        if DEBUG_MOVEMENT: import traceback; traceback.print_exc(); return 
    except Exception as e_type_creation:
        print(f"ERROR in MOVE: Unexpected error creating velocity structure: {e_type_creation}")
        if DEBUG_MOVEMENT: import traceback; traceback.print_exc(); return

    x_attr = 'x' if hasattr(request.Velocity.PanTilt, 'x') else '_x'
    y_attr = 'y' if hasattr(request.Velocity.PanTilt, 'y') else '_y'
    setattr(request.Velocity.PanTilt, x_attr, actual_pan_velocity)
    setattr(request.Velocity.PanTilt, y_attr, actual_tilt_velocity)
    
    if DEBUG_MOVEMENT:
        space_val = getattr(request.Velocity.PanTilt, space_attr_name, 'Not Set') if space_attr_name else 'No Space Attr'
        print(f"[DEBUG MOVE] Sending ContinuousMove: Pan={actual_pan_velocity:.2f}, Tilt={actual_tilt_velocity:.2f}, Space='{space_val}'")
    try:
        ptz_service.ContinuousMove(request) # Synchronous call
        is_moving = (abs(actual_pan_velocity) > 1e-5 or abs(actual_tilt_velocity) > 1e-5)
        if DEBUG_MOVEMENT: print(f"[DEBUG MOVE] ContinuousMove sent. New is_moving: {is_moving}")
    except Exception as e:
        print(f"Error sending ContinuousMove: {e}")
        if DEBUG_MOVEMENT: import traceback; traceback.print_exc()

def stop_move():
    global ptz_service, active_profile_token, is_moving, current_pan_velocity, current_tilt_velocity
    if DEBUG_MOVEMENT: print(f"[DEBUG STOP] Called. is_moving: {is_moving}")
    if not ptz_service or not active_profile_token: return
    if not is_moving and abs(current_pan_velocity) < 1e-5 and abs(current_tilt_velocity) < 1e-5:
        if DEBUG_MOVEMENT: print("[DEBUG STOP] Not moving. No Stop sent."); return
    request = ptz_service.create_type('Stop')
    request.ProfileToken = active_profile_token
    request.PanTilt = True; request.Zoom = False
    if DEBUG_MOVEMENT: print(f"[DEBUG STOP] Sending Stop.")
    try:
        ptz_service.Stop(request) # Synchronous call
        is_moving = False; current_pan_velocity = 0.0; current_tilt_velocity = 0.0
        print("Movement stopped.")
    except Exception as e:
        print(f"Error sending Stop command: {e}")
        if DEBUG_MOVEMENT: import traceback; traceback.print_exc()

def on_press(key_event):
    # (This logic remains the same, using scan codes)
    try:
        scan_code = key_event.scan_code
        if DEBUG_MOVEMENT: print(f"[DEBUG KB_PRESS] Event -> Scan: {scan_code}, Name: '{key_event.name}'.")
        new_pan_factor, new_tilt_factor = 0.0, 0.0
        if keyboard.is_pressed(SCAN_CODE_LEFT): new_pan_factor -= PAN_SPEED_FACTOR
        if keyboard.is_pressed(SCAN_CODE_RIGHT): new_pan_factor += PAN_SPEED_FACTOR
        if keyboard.is_pressed(SCAN_CODE_UP): new_tilt_factor += TILT_SPEED_FACTOR
        if keyboard.is_pressed(SCAN_CODE_DOWN): new_tilt_factor -= TILT_SPEED_FACTOR
        new_pan_factor = max(-PAN_SPEED_FACTOR, min(PAN_SPEED_FACTOR, new_pan_factor))
        new_tilt_factor = max(-TILT_SPEED_FACTOR, min(TILT_SPEED_FACTOR, new_tilt_factor))
        # Simplified: always call perform_move, let it decide if actual values changed enough
        print(f"Moving with factors: PanF={new_pan_factor:.2f}, TiltF={new_tilt_factor:.2f}")
        perform_continuous_move(new_pan_factor, new_tilt_factor)
    except Exception as e:
        print(f"Error in on_press: {e}")
        if DEBUG_MOVEMENT: import traceback; traceback.print_exc()

def on_release(key_event):
    # (This logic remains the same, using scan codes)
    try:
        scan_code = key_event.scan_code
        if DEBUG_MOVEMENT: print(f"[DEBUG KB_RELEASE] Event -> Scan: {scan_code}, Name: '{key_event.name}'.")
        if scan_code not in [SCAN_CODE_LEFT, SCAN_CODE_RIGHT, SCAN_CODE_UP, SCAN_CODE_DOWN]: return
        pan_factor_after_release, tilt_factor_after_release = 0.0, 0.0
        if keyboard.is_pressed(SCAN_CODE_LEFT): pan_factor_after_release -= PAN_SPEED_FACTOR
        if keyboard.is_pressed(SCAN_CODE_RIGHT): pan_factor_after_release += PAN_SPEED_FACTOR
        if keyboard.is_pressed(SCAN_CODE_UP): tilt_factor_after_release += TILT_SPEED_FACTOR
        if keyboard.is_pressed(SCAN_CODE_DOWN): tilt_factor_after_release -= TILT_SPEED_FACTOR
        pan_factor_after_release = max(-PAN_SPEED_FACTOR, min(PAN_SPEED_FACTOR, pan_factor_after_release))
        tilt_factor_after_release = max(-TILT_SPEED_FACTOR, min(TILT_SPEED_FACTOR, tilt_factor_after_release))
        if DEBUG_MOVEMENT: print(f"[DEBUG KB_RELEASE] New target factors: pan_f={pan_factor_after_release:.2f}, tilt_f={tilt_factor_after_release:.2f}")
        factor_tolerance = 1e-5
        if abs(pan_factor_after_release) < factor_tolerance and abs(tilt_factor_after_release) < factor_tolerance:
            if is_moving: stop_move()
        else:
            perform_continuous_move(pan_factor_after_release, tilt_factor_after_release)
    except Exception as e:
        print(f"Error in on_release: {e}")
        if DEBUG_MOVEMENT: import traceback; traceback.print_exc()

# --- Main Program ---
if __name__ == '__main__':
    if not ENABLE_ONVIF_CONTROL: print("ONVIF control disabled."); sys.exit(0)
    if KEY_NAME_LEFT == 'vänsterpil': print("NOTE: Using 'vänsterpil' for LEFT key name debug. Verify if different.")

    if not setup_camera(): print("Failed to setup camera. Exiting."); sys.exit(1)

    print("\n--- Camera Control Initialized (Synchronous) ---")
    print(f"  PTZ Speed Ranges: X_Pan ({XMIN_VEL:.2f} to {XMAX_VEL:.2f}), Y_Tilt ({YMIN_VEL:.2f} to {YMAX_VEL:.2f})")
    print(f"  PanTilt Velocity Space URI: {PAN_TILT_VELOCITY_SPACE_URI if PAN_TILT_VELOCITY_SPACE_URI else 'Not Set/Default'}")
    print("Use ARROW KEYS to Pan/Tilt. Press 'Q' or 'ESC' to quit.\n")

    keyboard.on_press(on_press, suppress=False)
    keyboard.on_release(on_release)
    
    running = True
    def quit_program_sync(event=None): global running; print("Exit key. Shutting down..."); running = False
    keyboard.on_press_key("q", quit_program_sync, suppress=True)
    keyboard.on_press_key("esc", quit_program_sync, suppress=True)

    try:
        while running: time.sleep(0.1)
    except KeyboardInterrupt: print("\nCtrl+C. Exiting."); running = False
    finally:
        print("Cleaning up..."); 
        if mycam and ptz_service: stop_move()
        keyboard.unhook_all(); print("Exited.")