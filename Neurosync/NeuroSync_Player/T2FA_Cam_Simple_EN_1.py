import time
import os
import sys

# --- Try to import keyboard, provide instructions if it fails ---
try:
    import keyboard
except ImportError:
    print("The 'keyboard' library is not installed.")
    print("Please install it by running: pip install keyboard")
    print("On Linux, you might also need: sudo apt-get install python3-dev libxtst-dev")
    print("And you might need to run the script with sudo: sudo python your_script.py")
    sys.exit(1)
except Exception as e:
    if "You must be root to use this library on linux" in str(e):
        print(f"Error importing keyboard: {e}")
        print("On Linux, this library often requires root privileges.")
        print("Try running: sudo python your_script.py")
    else:
        print(f"An unexpected error occurred importing keyboard: {e}")
    sys.exit(1)

# --- Attempt to import ONVIFCamera from the 'onvif' package ---
try:
    from onvif import ONVIFCamera
    print("Successfully imported 'ONVIFCamera' from the 'onvif' package.")
except ImportError as e:
    print(f"CRITICAL ERROR: Failed to import 'ONVIFCamera' from 'onvif'. Exception: {e}")
    print("This suggests that 'onvif-zeep' did not install correctly to provide the 'onvif' module,")
    print("or the 'onvif' module found is not the correct one.")
    print("Please ensure 'onvif-zeep' is installed. Check your site-packages for an 'onvif' folder.")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred importing ONVIFCamera: {e}")
    sys.exit(1)


# --- Configuration - MODIFY THESE ---
ENABLE_ONVIF_CONTROL = True
CAMERA_IP = '192.168.1.100'
ONVIF_PORT = 2020
USERNAME = 'jaygee'
PASSWORD = '1248aceg'

# --- WSDL Directory ---
# Using the path that worked for you previously.
# Ensure this 'wsdl' folder exists directly in your venv's site-packages.
WSDL_DIR_TO_PASS_TO_CONSTRUCTOR = r'C:\Users\jorge\Documents\AI\NeuroSync\NeuroSync_Player-main\aicam\Lib\site-packages\wsdl'
# If the above path doesn't work, or to let ONVIFCamera try its defaults:
# WSDL_DIR_TO_PASS_TO_CONSTRUCTOR = None
print(f"Attempting to use WSDL_DIR: '{WSDL_DIR_TO_PASS_TO_CONSTRUCTOR if WSDL_DIR_TO_PASS_TO_CONSTRUCTOR else 'None (let ONVIFCamera use defaults)'}'")


# --- Movement Parameters ---
PAN_SPEED = 0.5  # Try 1.0 if 0.5 doesn't work
TILT_SPEED = 0.5 # Try 1.0 if 0.5 doesn't work

# --- Debug Flag ---
DEBUG_MOVEMENT = True # Set to False to reduce print statements later

# Global variables
mycam = None
ptz_service = None
active_profile_token = None
current_pan_velocity = 0.0
current_tilt_velocity = 0.0
is_moving = False


def setup_camera():
    global mycam, ptz_service, active_profile_token

    if WSDL_DIR_TO_PASS_TO_CONSTRUCTOR and not os.path.isdir(WSDL_DIR_TO_PASS_TO_CONSTRUCTOR):
        print(f"WARNING: The specified WSDL_DIR '{WSDL_DIR_TO_PASS_TO_CONSTRUCTOR}' is not a valid directory.")
        print("This could lead to errors if ONVIFCamera cannot load WSDL files.")
        # Fallback or exit if critical
        # WSDL_DIR_TO_PASS_TO_CONSTRUCTOR = None # Optional: Fallback to None
        # print("Falling back to WSDL_DIR=None")

    try:
        print(f"Attempting to connect to camera at {CAMERA_IP}:{ONVIF_PORT}...")
        mycam = ONVIFCamera(CAMERA_IP, ONVIF_PORT, USERNAME, PASSWORD, WSDL_DIR_TO_PASS_TO_CONSTRUCTOR)
        print(f"Successfully connected to camera at {CAMERA_IP}:{ONVIF_PORT}")

        ptz_service = mycam.create_ptz_service()
        if ptz_service:
            print("PTZ service client created.")
        else:
            print("Failed to create PTZ service client.")
            mycam = None
            return False

        media_service = mycam.create_media_service()
        if not media_service:
            print("Failed to create Media service client.")
            mycam = None
            return False
            
        profiles = media_service.GetProfiles()
        if not profiles:
            print("Error: No media profiles found on the camera.")
            mycam = None
            return False
        
        active_profile_token = profiles[0].token
        print(f"Using profile token: {active_profile_token}")
        return True

    except Exception as e:
        print(f"Error during camera setup: {e}")
        import traceback
        traceback.print_exc()
        mycam = None
        return False

def perform_continuous_move(pan_velocity, tilt_velocity):
    global ptz_service, active_profile_token, is_moving
    global current_pan_velocity, current_tilt_velocity

    if DEBUG_MOVEMENT:
        print(f"[DEBUG perform_continuous_move] Called with pan_vel={pan_velocity:.2f}, tilt_vel={tilt_velocity:.2f}. Current is_moving: {is_moving}")

    if not ptz_service or not active_profile_token:
        print("PTZ service or profile token not available. Cannot move.")
        return

    current_pan_velocity = pan_velocity # Update global state first
    current_tilt_velocity = tilt_velocity

    if pan_velocity == 0.0 and tilt_velocity == 0.0 and not is_moving:
        if DEBUG_MOVEMENT:
            print(f"[DEBUG perform_continuous_move] Velocities are zero and not currently moving. Returning.")
        return

    request = ptz_service.create_type('ContinuousMove')
    request.ProfileToken = active_profile_token
    
    request.Velocity = ptz_service.zeep_client.get_element('ns0:PTZSpeed')()
    request.Velocity.PanTilt = ptz_service.zeep_client.get_element('ns0:Vector2D')()
    request.Velocity.PanTilt.x = pan_velocity
    request.Velocity.PanTilt.y = tilt_velocity
    # Optional: Try adding a timeout to see if it affects behavior
    # request.Timeout = "PT5S" # Example: move for up to 5 seconds, then camera might stop itself
    # request.Timeout = "PT0S" # Often means "until Stop command"

    if DEBUG_MOVEMENT:
        print(f"[DEBUG perform_continuous_move] Sending ContinuousMove: Profile='{request.ProfileToken}', Pan={request.Velocity.PanTilt.x:.2f}, Tilt={request.Velocity.PanTilt.y:.2f}")
    
    try:
        ptz_service.ContinuousMove(request)
        is_moving = (pan_velocity != 0.0 or tilt_velocity != 0.0) # Update based on command sent
        if DEBUG_MOVEMENT:
            print(f"[DEBUG perform_continuous_move] ContinuousMove sent. New is_moving: {is_moving}")
    except Exception as e:
        print(f"Error sending ContinuousMove: {e}")
        if DEBUG_MOVEMENT:
            import traceback
            traceback.print_exc()
        # Optionally, reset is_moving if command fails critically
        # is_moving = False 


def stop_move():
    global ptz_service, active_profile_token, is_moving
    global current_pan_velocity, current_tilt_velocity

    if DEBUG_MOVEMENT:
        print(f"[DEBUG stop_move] Called. Current is_moving: {is_moving}, current vels: pan={current_pan_velocity:.2f}, tilt={current_tilt_velocity:.2f}")

    if not ptz_service or not active_profile_token:
        print("PTZ service or profile token not available. Cannot stop.")
        return

    # Only send stop if we think we are moving OR if commanded velocities are now zero
    # (The latter case is handled by perform_continuous_move(0,0) if a key release leads to that)
    if not is_moving and (current_pan_velocity == 0.0 and current_tilt_velocity == 0.0):
        if DEBUG_MOVEMENT:
            print(f"[DEBUG stop_move] Camera is not considered to be moving OR target vels are zero, no explicit Stop command sent from here.")
        return

    request = ptz_service.create_type('Stop')
    request.ProfileToken = active_profile_token
    request.PanTilt = True
    request.Zoom = False

    if DEBUG_MOVEMENT:
        print(f"[DEBUG stop_move] Sending Stop: Profile='{request.ProfileToken}', PanTilt={request.PanTilt}, Zoom={request.Zoom}")

    try:
        ptz_service.Stop(request)
        is_moving = False
        current_pan_velocity = 0.0
        current_tilt_velocity = 0.0
        print("Movement stopped.") # Keep this non-debug print for user feedback
        if DEBUG_MOVEMENT:
            print(f"[DEBUG stop_move] Stop command sent. New is_moving: {is_moving}, vels reset.")
    except Exception as e:
        print(f"Error sending Stop command: {e}")
        if DEBUG_MOVEMENT:
            import traceback
            traceback.print_exc()


def on_press(key_event):
    global current_pan_velocity, current_tilt_velocity
    
    try:
        key_name = key_event.name
        if DEBUG_MOVEMENT:
            print(f"[DEBUG on_press] Key pressed: '{key_name}'. Current vels: pan={current_pan_velocity:.2f}, tilt={current_tilt_velocity:.2f}")

        new_pan_target = current_pan_velocity # What the pan speed should become
        new_tilt_target = current_tilt_velocity # What the tilt speed should become
        
        # Determine if this key press changes the target state
        changed_pan_due_to_this_key = False
        changed_tilt_due_to_this_key = False

        if key_name == 'left':
            if current_pan_velocity >= 0: # If not already moving left or stopped
                new_pan_target = -PAN_SPEED
                changed_pan_due_to_this_key = True
        elif key_name == 'right':
            if current_pan_velocity <= 0: # If not already moving right or stopped
                new_pan_target = PAN_SPEED
                changed_pan_due_to_this_key = True
        elif key_name == 'up':
            if current_tilt_velocity <= 0: # If not already moving up or stopped
                new_tilt_target = TILT_SPEED
                changed_tilt_due_to_this_key = True
        elif key_name == 'down':
            if current_tilt_velocity >= 0: # If not already moving down or stopped
                new_tilt_target = -TILT_SPEED
                changed_tilt_due_to_this_key = True
        
        # Only send a new command if this specific key press caused a change in its direction's target speed
        # or if it's initiating movement in a direction that was previously stopped.
        if changed_pan_due_to_this_key or changed_tilt_due_to_this_key:
            # Combine with potentially ongoing movement in the other axis
            final_pan_command = new_pan_target if changed_pan_due_to_this_key else current_pan_velocity
            final_tilt_command = new_tilt_target if changed_tilt_due_to_this_key else current_tilt_velocity
            
            # If a key for an already active direction is pressed again, we might not want to resend.
            # The 'changed_...' flags help here. We only proceed if this key press *alters* the state.
            # However, the logic `if current_pan_velocity >=0` for 'left' already handles not resending if already moving left.

            if DEBUG_MOVEMENT:
                 print(f"[DEBUG on_press] Change initiated by '{key_name}'. New target command: pan={final_pan_command:.2f}, tilt={final_tilt_command:.2f}")
            print(f"Moving: Pan={final_pan_command:.2f}, Tilt={final_tilt_command:.2f}") # User feedback
            perform_continuous_move(final_pan_command, final_tilt_command)
        elif DEBUG_MOVEMENT and key_name in ['left', 'right', 'up', 'down']:
            print(f"[DEBUG on_press] Key '{key_name}' pressed, but no change in target velocity for its axis (already moving that way or other key controls it). Not sending new command from on_press.")

    except Exception as e:
        print(f"Error in on_press: {e}")
        if DEBUG_MOVEMENT:
            import traceback
            traceback.print_exc()


def on_release(key_event):
    global current_pan_velocity, current_tilt_velocity # Read and will be updated by subsequent calls
    
    try:
        key_name = key_event.name
        if DEBUG_MOVEMENT:
            print(f"[DEBUG on_release] Key released: '{key_name}'. Current vels: pan={current_pan_velocity:.2f}, tilt={current_tilt_velocity:.2f}")

        # Determine new target velocities if this key release stops a specific direction
        pan_after_release = current_pan_velocity
        tilt_after_release = current_tilt_velocity
        key_caused_stop_in_its_direction = False

        if key_name == 'left' and current_pan_velocity < 0: # Was moving left
            pan_after_release = 0.0
            key_caused_stop_in_its_direction = True
        elif key_name == 'right' and current_pan_velocity > 0: # Was moving right
            pan_after_release = 0.0
            key_caused_stop_in_its_direction = True
        elif key_name == 'up' and current_tilt_velocity > 0: # Was moving up
            tilt_after_release = 0.0
            key_caused_stop_in_its_direction = True
        elif key_name == 'down' and current_tilt_velocity < 0: # Was moving down
            tilt_after_release = 0.0
            key_caused_stop_in_its_direction = True
        
        if not key_caused_stop_in_its_direction: 
            if DEBUG_MOVEMENT:
                print(f"[DEBUG on_release] Key '{key_name}' released, but it didn't correspond to an active movement direction being stopped. No command from on_release.")
            return 

        if DEBUG_MOVEMENT:
            print(f"[DEBUG on_release] Key '{key_name}' caused stop in its direction. New target vels after release: pan={pan_after_release:.2f}, tilt={tilt_after_release:.2f}")

        if pan_after_release == 0.0 and tilt_after_release == 0.0:
            # If all movements are now zero (i.e., this key release stopped the last active movement)
            # print(f"Key '{key_name}' released, stopping all movement.") # User feedback
            stop_move() 
        else:
            # If one direction stopped but another might still be active (e.g., diagonal movement, other key still held)
            # print(f"Key '{key_name}' released, updating move: Pan={pan_after_release:.2f}, Tilt={tilt_after_release:.2f}") # User feedback
            perform_continuous_move(pan_after_release, tilt_after_release)

    except Exception as e:
        print(f"Error in on_release: {e}")
        if DEBUG_MOVEMENT:
            import traceback
            traceback.print_exc()


# --- Main Program ---
if __name__ == '__main__':
    if not ENABLE_ONVIF_CONTROL:
        print("ONVIF camera control is disabled in the script configuration.")
        sys.exit(0)

    if not setup_camera():
        print("Failed to setup camera. Please check configuration and camera status.")
        print("Exiting.")
        sys.exit(1)

    print("\n--- Camera Control Initialized ---")
    print("Use ARROW KEYS to Pan/Tilt the camera.")
    print("Press 'Q' or 'ESC' to quit the program.")
    print("Ensure this terminal window has focus for keyboard input to be detected.")
    if sys.platform.startswith('linux'): # Only print Linux specific message on Linux
        print("If on Linux and arrow keys do not work, you might need to run with 'sudo'.")
    print() # Newline for cleaner log start

    keyboard.on_press(on_press, suppress=False) # suppress=False for arrow keys is usually fine
    keyboard.on_release(on_release)
    
    running = True
    def quit_program(event=None): # Parameter event is passed by keyboard.on_press_key
        global running
        if running: # Avoid multiple prints if key is held
            print("Exit key pressed. Preparing to shut down...")
            running = False

    # Hook specific keys for quitting, suppress to prevent them typing in terminal
    keyboard.on_press_key("q", quit_program, suppress=True)
    keyboard.on_press_key("esc", quit_program, suppress=True)

    try:
        while running:
            time.sleep(0.1) # Keep main thread alive, keyboard listener is in its own thread
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Forcing exit...")
        running = False # Ensure loop terminates
    finally:
        print("Cleaning up resources...")
        if ENABLE_ONVIF_CONTROL and mycam and ptz_service: # Check if camera was set up
            print("Stopping camera movement (if any)...")
            stop_move()  # Ensure camera stops movement before script exits
        
        keyboard.unhook_all() # Important to release all keyboard hooks
        print("Exited.")