import pyautogui
import time
import pygetwindow # For focusing the window
import math

# --- Function to Focus Window and Perform a Click with Hold ---
def focus_window_and_click(window_title_substring, x, y,
                           click_hold_time, # How long to hold the mouse down for THIS action
                           delay_before_action=0.1,
                           move_duration=0.1,
                           pause_after_move=0.05):
    """
    Attempts to find and focus a window, then moves to (x,y) and performs a click with hold.
    Returns True if the click action was attempted, False on major errors.
    """
    focused_successfully = False
    try:
        if delay_before_action > 0:
            # print(f"  Delaying for {delay_before_action}s before action...") # Verbose
            time.sleep(delay_before_action)

        target_windows = pygetwindow.getWindowsWithTitle(window_title_substring)
        if not target_windows:
            print(f"  Error: No window found with title containing '{window_title_substring}'.")
            return False
        target_window = target_windows[0]

        if not target_window.isActive:
            # print(f"  Window '{target_window.title}' not active. Attempting to activate...") # Verbose
            try:
                if target_window.isMinimized:
                    target_window.restore()
                    time.sleep(0.1)
                target_window.activate()
                time.sleep(0.2) # Settle time for activation
                # Verify focus more reliably
                active_win_check = pygetwindow.getActiveWindow()
                if active_win_check and active_win_check.title == target_window.title:
                    focused_successfully = True
                # if focused_successfully: print(f"  Window '{target_window.title}' activated.") # Verbose
                # else: print(f"  Warning: Activation might not have fully succeeded.") # Verbose
            except Exception as e_focus:
                print(f"  Warning: Could not reliably activate window: {e_focus}")
        else:
            focused_successfully = True

        # If not focused successfully try to bring it to foreground as a fallback
        if not focused_successfully and target_window:
             print(f"  Fallback: Trying to bring '{target_window.title}' to foreground.")
             try:
                target_window.show()
                if hasattr(target_window, 'moveTo') and hasattr(target_window, 'left') and hasattr(target_window, 'top'):
                     target_window.moveTo(target_window.left, target_window.top) # "Touch" the window
                time.sleep(0.2)
             except Exception as e_show:
                  print(f"  Warning: Fallback focus method also failed ({e_show}).")


        screen_width, screen_height = pyautogui.size()
        if not (0 <= x < screen_width and 0 <= y < screen_height):
            print(f"  Error: Click coordinates ({x}, {y}) are outside screen bounds.")
            return False

        pyautogui.moveTo(x, y, duration=move_duration)
        if pause_after_move > 0: time.sleep(pause_after_move)

        # print(f"  Performing click at ({x}, {y}), holding for {click_hold_time:.2f}s...") # Verbose
        pyautogui.mouseDown(button='left')
        time.sleep(click_hold_time)
        pyautogui.mouseUp(button='left')
        return True

    except pyautogui.FailSafeException:
        print("  FAIL-SAFE TRIGGERED!")
        return False
    except Exception as e:
        print(f"  An error occurred in focus_window_and_click: {e}")
        return False


# --- Class for Simulating Camera Pan and Tilt by Clicking/Holding On-Screen UI Buttons ---
class SimulatedCameraControls:
    def __init__(self, window_title,
                 # Pan settings
                 full_pan_time_seconds=8.5, initial_pan_angle_degrees=0.0,
                 pan_left_button_x=None, pan_left_button_y=None,
                 pan_right_button_x=None, pan_right_button_y=None,
                 # Tilt settings
                 full_tilt_range_degrees=180.0,
                 full_tilt_time_seconds=5.0,
                 initial_tilt_angle_degrees=0.0, # This is the one from config
                 min_tilt_angle_degrees=-90.0,
                 max_tilt_angle_degrees=90.0,
                 tilt_up_button_x=None, tilt_up_button_y=None,
                 tilt_down_button_x=None, tilt_down_button_y=None
                ):

        # --- Pan Initialization ---
        if full_pan_time_seconds <= 0: raise ValueError("Full pan time must be positive.")
        if None in [pan_left_button_x, pan_left_button_y, pan_right_button_x, pan_right_button_y]:
            raise ValueError("Coordinates for pan UI buttons must be provided.")
        self.window_title = window_title
        self.full_pan_time_seconds = full_pan_time_seconds
        self.degrees_per_second_pan = 360.0 / self.full_pan_time_seconds
        self.current_pan_angle_degrees = self._normalize_pan_angle(initial_pan_angle_degrees)
        self.pan_left_coords = (pan_left_button_x, pan_left_button_y)
        self.pan_right_coords = (pan_right_button_x, pan_right_button_y)

        # --- Tilt Initialization ---
        if full_tilt_time_seconds <= 0: raise ValueError("Full tilt time must be positive.")
        if full_tilt_range_degrees <= 0: raise ValueError("Full tilt range must be positive.")
        if None in [tilt_up_button_x, tilt_up_button_y, tilt_down_button_x, tilt_down_button_y]:
            raise ValueError("Coordinates for tilt UI buttons must be provided.")
        if min_tilt_angle_degrees >= max_tilt_angle_degrees:
            raise ValueError("Min tilt angle must be less than max tilt angle.")

        self.full_tilt_range_degrees = full_tilt_range_degrees
        self.full_tilt_time_seconds = full_tilt_time_seconds
        self.degrees_per_second_tilt = self.full_tilt_range_degrees / self.full_tilt_time_seconds
        
        self.min_tilt_angle_degrees = min_tilt_angle_degrees # Store min from config
        self.max_tilt_angle_degrees = max_tilt_angle_degrees # Store max from config
        # Store the passed initial_tilt_angle_degrees as an attribute for reference
        self.initial_tilt_angle_degrees_config = initial_tilt_angle_degrees # Store for clarity
        self.current_tilt_angle_degrees = self._clamp_tilt_angle(self.initial_tilt_angle_degrees_config) # Use it here

        self.tilt_up_coords = (tilt_up_button_x, tilt_up_button_y)
        self.tilt_down_coords = (tilt_down_button_x, tilt_down_button_y)

        print(f"SimulatedCameraControls initialized for window '{self.window_title}'.")
        print(f"  Pan: 360° in {self.full_pan_time_seconds}s ({self.degrees_per_second_pan:.2f}°/s). Initial: {self.current_pan_angle_degrees:.2f}°")
        print(f"    Left UI: {self.pan_left_coords}, Right UI: {self.pan_right_coords}")
        print(f"  Tilt: {self.full_tilt_range_degrees}° range ({self.min_tilt_angle_degrees}° to {self.max_tilt_angle_degrees}°) in {self.full_tilt_time_seconds}s ({self.degrees_per_second_tilt:.2f}°/s). Initial: {self.current_tilt_angle_degrees:.2f}°")
        print(f"    Up UI: {self.tilt_up_coords}, Down UI: {self.tilt_down_coords}")

    # --- Pan Methods ---
    def _normalize_pan_angle(self, angle_degrees):
        normalized = angle_degrees % 360.0
        if normalized < 0: normalized += 360.0
        return normalized

    def get_current_pan_angle(self):
        return self.current_pan_angle_degrees

    def _pan_for_duration(self, duration_to_hold_button, direction):
        if duration_to_hold_button <= 0: return False
        target_coords = self.pan_left_coords if direction == 'left' else self.pan_right_coords
        # print(f"  Panning {direction}: Clicking UI at {target_coords}, holding for {duration_to_hold_button:.2f}s.") # Verbose
        success = focus_window_and_click(
            self.window_title, target_coords[0], target_coords[1], duration_to_hold_button
        )
        if success:
            angle_change = self.degrees_per_second_pan * duration_to_hold_button
            self.current_pan_angle_degrees += (angle_change if direction == 'right' else -angle_change)
            self.current_pan_angle_degrees = self._normalize_pan_angle(self.current_pan_angle_degrees)
            # print(f"  Pan {direction} done. New pan: {self.current_pan_angle_degrees:.2f}°") # Verbose
            return True
        # print(f"  Error: Panning {direction} failed.") # Verbose
        return False

    def point_pan_to_angle(self, target_pan_angle, max_hold_time_per_step=None):
        target_pan_angle = self._normalize_pan_angle(target_pan_angle)
        # print(f"Attempting to pan to {target_pan_angle:.2f}° (Current: {self.current_pan_angle_degrees:.2f}°)") # Verbose
        
        safety_count = 0
        while abs(self._normalize_pan_angle(target_pan_angle - self.current_pan_angle_degrees)) > 0.5 and safety_count < 20: # Tolerance
            current_pan = self.current_pan_angle_degrees
            angle_clockwise = self._normalize_pan_angle(target_pan_angle - current_pan)
            angle_counter_clockwise = self._normalize_pan_angle(current_pan - target_pan_angle)

            if angle_clockwise <= angle_counter_clockwise:
                degrees_to_turn = angle_clockwise
                direction = 'right'
            else:
                degrees_to_turn = angle_counter_clockwise
                direction = 'left'

            if degrees_to_turn < 0.5: break # Close enough
            # print(f"  Pan step: Current: {current_pan:.2f}°, Target: {target_pan_angle:.2f}°. Turn {degrees_to_turn:.2f}° {direction}.") # Verbose
            duration_to_hold = degrees_to_turn / self.degrees_per_second_pan
            if max_hold_time_per_step and duration_to_hold > max_hold_time_per_step:
                duration_to_hold = max_hold_time_per_step
            if not self._pan_for_duration(duration_to_hold, direction): return False
            time.sleep(0.05) 
            safety_count += 1
        
        if safety_count >= 20: print("Warning: Pan safety count reached. Angle might not be precise.")
        print(f"Pan request to {target_pan_angle:.2f}° complete. Current pan: {self.current_pan_angle_degrees:.2f}°")
        return True

    def reset_pan_orientation(self, new_angle_degrees=0.0):
        self.current_pan_angle_degrees = self._normalize_pan_angle(new_angle_degrees)
        print(f"Pan orientation reset to: {self.current_pan_angle_degrees:.2f}°")

    # --- Tilt Methods ---
    def _clamp_tilt_angle(self, angle_degrees):
        return max(self.min_tilt_angle_degrees, min(self.max_tilt_angle_degrees, angle_degrees))

    def get_current_tilt_angle(self):
        return self.current_tilt_angle_degrees

    def _tilt_for_duration(self, duration_to_hold_button, direction): # 'up' or 'down'
        if duration_to_hold_button <= 0: return False
        target_coords = self.tilt_up_coords if direction == 'up' else self.tilt_down_coords
        # print(f"  Tilting {direction}: Clicking UI at {target_coords}, holding for {duration_to_hold_button:.2f}s.") # Verbose
        success = focus_window_and_click(
            self.window_title, target_coords[0], target_coords[1], duration_to_hold_button
        )
        if success:
            angle_change = self.degrees_per_second_tilt * duration_to_hold_button
            self.current_tilt_angle_degrees += (angle_change if direction == 'up' else -angle_change)
            self.current_tilt_angle_degrees = self._clamp_tilt_angle(self.current_tilt_angle_degrees)
            # print(f"  Tilt {direction} done. New tilt: {self.current_tilt_angle_degrees:.2f}°") # Verbose
            return True
        # print(f"  Error: Tilting {direction} failed.") # Verbose
        return False

    def point_tilt_to_angle(self, target_tilt_angle, max_hold_time_per_step=None):
        target_tilt_angle = self._clamp_tilt_angle(target_tilt_angle)
        # print(f"Attempting to tilt to {target_tilt_angle:.2f}° (Current: {self.current_tilt_angle_degrees:.2f}°)") # Verbose
        
        safety_count = 0
        while abs(target_tilt_angle - self.current_tilt_angle_degrees) > 0.5 and safety_count < 20: # Tolerance
            current_tilt = self.current_tilt_angle_degrees
            degrees_to_tilt_remaining = target_tilt_angle - current_tilt

            if abs(degrees_to_tilt_remaining) < 0.5: break # Close enough
            
            direction = 'up' if degrees_to_tilt_remaining > 0 else 'down'
            degrees_to_tilt_this_step = abs(degrees_to_tilt_remaining)
            
            # print(f"  Tilt step: Current: {current_tilt:.2f}°, Target: {target_tilt_angle:.2f}°. Tilt {degrees_to_tilt_this_step:.2f}° {direction}.") # Verbose
            duration_to_hold = degrees_to_tilt_this_step / self.degrees_per_second_tilt
            
            if max_hold_time_per_step and duration_to_hold > max_hold_time_per_step:
                duration_to_hold = max_hold_time_per_step
            
            if not self._tilt_for_duration(duration_to_hold, direction): return False
            
            if (direction == 'up' and self.current_tilt_angle_degrees == self.max_tilt_angle_degrees and target_tilt_angle > self.current_tilt_angle_degrees) or \
               (direction == 'down' and self.current_tilt_angle_degrees == self.min_tilt_angle_degrees and target_tilt_angle < self.current_tilt_angle_degrees):
                # print("  Hit tilt limit during step.") # Verbose
                break 
            
            time.sleep(0.05) 
            safety_count += 1

        if safety_count >= 20: print("Warning: Tilt safety count reached. Angle might not be precise.")
        print(f"Tilt request to {target_tilt_angle:.2f}° complete. Current tilt: {self.current_tilt_angle_degrees:.2f}°")
        return True

    def reset_tilt_orientation(self, new_angle_degrees=0.0):
        # Use the stored initial_tilt_angle_degrees_config if new_angle_degrees is not provided for a "true reset"
        # or allow resetting to any arbitrary valid angle.
        # For now, let's assume new_angle_degrees is always given or defaults to 0 (which might not be initial)
        self.current_tilt_angle_degrees = self._clamp_tilt_angle(new_angle_degrees)
        print(f"Tilt orientation reset to: {self.current_tilt_angle_degrees:.2f}°")

# --- Main Execution Block ---
if __name__ == "__main__":
    print("--- ODM Camera Pan & Tilt Script ---")

    # --- USER CONFIGURATION ---
    TARGET_ODM_WINDOW_TITLE = "ODM" # <<< REPLACE WITH YOUR ODM WINDOW TITLE IF DIFFERENT

    # Pan settings
    CAMERA_FULL_PAN_TIME_SECONDS = 8.5
    CAMERA_INITIAL_PAN_ANGLE = 359.0 # This is the starting pan angle
    ODM_PAN_LEFT_BUTTON_X = 639
    ODM_PAN_LEFT_BUTTON_Y = 224
    ODM_PAN_RIGHT_BUTTON_X = 923
    ODM_PAN_RIGHT_BUTTON_Y = 224

    # Tilt settings based on your input:
    CAMERA_FULL_TILT_RANGE_DEGREES = 170.0 
    CAMERA_FULL_TILT_TIME_SECONDS = 6.0   
    
    CONFIG_INITIAL_TILT_ANGLE = 85.0 # Store the intended initial value from config
    CONFIG_MIN_TILT_ANGLE = CONFIG_INITIAL_TILT_ANGLE - (CAMERA_FULL_TILT_RANGE_DEGREES / 2.0) 
    CONFIG_MAX_TILT_ANGLE = CONFIG_INITIAL_TILT_ANGLE + (CAMERA_FULL_TILT_RANGE_DEGREES / 2.0) 
    
    ODM_TILT_UP_BUTTON_X = 784       
    ODM_TILT_UP_BUTTON_Y = 162      
    ODM_TILT_DOWN_BUTTON_X = 787     
    ODM_TILT_DOWN_BUTTON_Y = 271    

    SCRIPT_START_DELAY = 3
    PAUSE_BETWEEN_MAJOR_ACTIONS = 1.0 
    MAX_HOLD_PER_STEP = 4.0
    # --- END USER CONFIGURATION ---

    print(f"Script will start in {SCRIPT_START_DELAY} seconds. Ensure ODM is ready and visible.")
    time.sleep(SCRIPT_START_DELAY)

    try:
        camera = SimulatedCameraControls(
            window_title=TARGET_ODM_WINDOW_TITLE,
            full_pan_time_seconds=CAMERA_FULL_PAN_TIME_SECONDS,
            initial_pan_angle_degrees=CAMERA_INITIAL_PAN_ANGLE, # Pass the pan initial
            pan_left_button_x=ODM_PAN_LEFT_BUTTON_X, pan_left_button_y=ODM_PAN_LEFT_BUTTON_Y,
            pan_right_button_x=ODM_PAN_RIGHT_BUTTON_X, pan_right_button_y=ODM_PAN_RIGHT_BUTTON_Y,
            
            full_tilt_range_degrees=CAMERA_FULL_TILT_RANGE_DEGREES,
            full_tilt_time_seconds=CAMERA_FULL_TILT_TIME_SECONDS,
            initial_tilt_angle_degrees=CONFIG_INITIAL_TILT_ANGLE, # Pass the tilt initial from config
            min_tilt_angle_degrees=CONFIG_MIN_TILT_ANGLE,       # Pass min from config
            max_tilt_angle_degrees=CONFIG_MAX_TILT_ANGLE,       # Pass max from config
            tilt_up_button_x=ODM_TILT_UP_BUTTON_X, tilt_up_button_y=ODM_TILT_UP_BUTTON_Y,
            tilt_down_button_x=ODM_TILT_DOWN_BUTTON_X, tilt_down_button_y=ODM_TILT_DOWN_BUTTON_Y
        )
    except ValueError as e:
        print(f"Error initializing camera: {e}")
        print("Please check your configuration values.")
        exit()
    print("-" * 30)

    # --- Test Pan ---
    print("\n--- Testing Pan Operations ---")
    pan_targets = [90.0, 270.0, CAMERA_INITIAL_PAN_ANGLE] 
    for i, angle in enumerate(pan_targets):
        print(f"\nPan Test {i+1}: Requesting pan to {angle}°...")
        if not camera.point_pan_to_angle(angle, max_hold_time_per_step=MAX_HOLD_PER_STEP):
            print(f"Pan to {angle}° failed. Skipping further pan tests.")
            break
        time.sleep(PAUSE_BETWEEN_MAJOR_ACTIONS)
    
    # --- Test Tilt ---
    print("\n--- Testing Tilt Operations ---")
    tilt_targets = [
        CONFIG_MAX_TILT_ANGLE,    # Use the config variable for max
        CONFIG_MIN_TILT_ANGLE,    # Use the config variable for min
        CONFIG_INITIAL_TILT_ANGLE, # Use the config variable for initial
        CONFIG_INITIAL_TILT_ANGLE + 30, 
        CONFIG_INITIAL_TILT_ANGLE - 30  
    ]
    for i, angle in enumerate(tilt_targets):
        # Clamping the test angle itself before passing it to the function,
        # though point_tilt_to_angle also clamps its target internally.
        test_angle_clamped = max(CONFIG_MIN_TILT_ANGLE, min(CONFIG_MAX_TILT_ANGLE, angle))
        print(f"\nTilt Test {i+1}: Requesting tilt to {test_angle_clamped}°...")
        if not camera.point_tilt_to_angle(test_angle_clamped, max_hold_time_per_step=MAX_HOLD_PER_STEP):
            print(f"Tilt to {test_angle_clamped}° failed. Skipping further tilt tests.")
            break
        time.sleep(PAUSE_BETWEEN_MAJOR_ACTIONS)

    print("-" * 30)
    print("--- ODM Camera Pan & Tilt Script Finished ---")