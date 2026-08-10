import sounddevice as sd
import numpy as np
import os
import platform
import time
import math

# --- Configuration ---
BAR_PADDING = 25          # Space for labels, etc. Must be an integer.
MIN_DB = -80.0            # The quietest sound level we want to show
MAX_DB = 0.0              # The loudest sound level (clipping)
SMOOTHING_FACTOR = 0.85   # How much to smooth the meter's movement (0.0 to 1.0)

# --- ANSI Color Codes ---
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'
COLOR_RED = '\033[91m'
COLOR_RESET = '\033[0m'

# --- Global state variables for the audio callback ---
g_smoothed_db = MIN_DB
g_peak_db = MIN_DB
g_peak_hold_time = 0
PEAK_HOLD_DURATION = 1.0 # seconds

def clear_screen():
    """Clears the console screen."""
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def select_audio_device():
    """Lists available input devices and prompts the user to select one."""
    print("--- Audio Device Selection ---")
    try:
        devices = sd.query_devices()
        input_devices = [(i, d) for i, d in enumerate(devices) if d['max_input_channels'] > 0]
        if not input_devices:
            print("ERROR: No audio input devices found.")
            return None
        print("Available audio input devices:")
        default_idx = sd.default.device[0]
        for index, device in input_devices:
            is_default = '(default)' if index == default_idx else ''
            print(f"  {index}: {device['name']} {is_default}")
        while True:
            try:
                choice = input(f"\nEnter device index (or press Enter for default): ")
                if choice == '': return default_idx
                choice_index = int(choice)
                if any(choice_index == i for i, d in input_devices): return choice_index
                else: print("Invalid index. Please try again.")
            except ValueError: print("Invalid input. Please enter a number.")
    except Exception as e:
        print(f"ERROR: Could not query audio devices. Details: {e}")
        return None

def audio_callback(indata, frames, time_info, status):
    """This function is called by the sounddevice stream for each new audio chunk."""
    global g_smoothed_db, g_peak_db, g_peak_hold_time
    if status:
        print(status)

    # Calculate the RMS (Root Mean Square) of the audio chunk
    rms = np.sqrt(np.mean(indata**2))
    
    # Convert RMS to Decibels (dB)
    # Handle the case where rms is zero to avoid log10(0)
    if rms > 0:
        current_db = 20 * math.log10(rms)
    else:
        current_db = MIN_DB

    # Apply smoothing (Exponential Moving Average)
    g_smoothed_db = (SMOOTHING_FACTOR * g_smoothed_db) + ((1 - SMOOTHING_FACTOR) * current_db)
    
    # Update peak value
    if g_smoothed_db > g_peak_db:
        g_peak_db = g_smoothed_db
        g_peak_hold_time = time.time()

def run_vu_meter(device_id):
    """Starts listening to the microphone and displays the refined VU meter."""
    global g_peak_db
    try:
        samplerate = sd.query_devices(device_id, 'input')['default_samplerate']
    except Exception as e:
        print(f"Could not get device sample rate. Falling back to 44100 Hz. Error: {e}")
        samplerate = 44100
        
    clear_screen()
    device_name = sd.query_devices(device_id)['name']
    print(f"--- Live VU Meter ---")
    print(f"Device: {device_name}")
    print("Press Ctrl+C to exit.\n")

    try:
        with sd.InputStream(device=device_id, channels=1, samplerate=samplerate, callback=audio_callback):
            while True:
                # --- Display Logic ---
                terminal_width = os.get_terminal_size().columns
                bar_width = terminal_width - BAR_PADDING
                
                # Check if peak hold time has expired
                if time.time() - g_peak_hold_time > PEAK_HOLD_DURATION:
                    g_peak_db = max(g_smoothed_db, g_peak_db - 2) # Slowly decay the peak

                # --- Map dB to bar length ---
                # Clamp the value to ensure it's within our MIN/MAX range
                clamped_db = max(MIN_DB, min(g_smoothed_db, MAX_DB))
                bar_length = int(((clamped_db - MIN_DB) / (MAX_DB - MIN_DB)) * bar_width)
                
                # Clamp peak_pos to be within the bar's boundaries
                clamped_peak_db = max(MIN_DB, min(g_peak_db, MAX_DB))
                peak_pos = int(((clamped_peak_db - MIN_DB) / (MAX_DB - MIN_DB)) * bar_width)
                
                # --- Build the bar string with colors ---
                bar_str = ""
                for i in range(bar_width):
                    char = ' '
                    if i < bar_length:
                        # Determine color based on position
                        percent = i / bar_width
                        if percent < 0.7:
                            char = COLOR_GREEN + '━'
                        elif percent < 0.9:
                            char = COLOR_YELLOW + '━'
                        else:
                            char = COLOR_RED + '━'
                    # Add peak indicator
                    if i == peak_pos:
                        # Use a different character for peak to make it stand out
                        char = COLOR_RED + '┃'

                    bar_str += char

                # --- Print the final line ---
                # The f-string formatting aligns the dB value neatly
                output = (
                    f"[{bar_str}{COLOR_RESET}] "
                    f"{g_smoothed_db:6.2f} dB"
                )
                print(output, end='\r')
                
                time.sleep(0.05) # Refresh rate

    except KeyboardInterrupt:
        print("\n\nExiting VU meter.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")

if __name__ == '__main__':
    selected_device = select_audio_device()
    if selected_device is not None:
        run_vu_meter(selected_device)