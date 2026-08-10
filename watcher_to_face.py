import os
import pygame
import warnings
import time
import configparser
import sys
from threading import Thread

# --- Import sounddevice for audio device selection ---
try:
    import sounddevice as sd
except ImportError:
    print("FATAL ERROR: The 'sounddevice' library is required. Please install it using: pip install sounddevice")
    sys.exit(1)

# --- Suppress specific warnings ---
warnings.filterwarnings(
    "ignore", 
    message="Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work"
)

# --- Import project-specific modules ---
from livelink.connect.livelink_init import create_socket_connection, initialize_py_face
from livelink.animations.default_animation import default_animation_loop, stop_default_animation
from utils.files.file_utils import initialize_directories
from utils.audio_face_workers import process_wav_file
from utils.emote_sender.send_emote import EmoteConnect

# --- Configuration ---
ENABLE_EMOTE_CALLS = False

# --- MODIFIED: Programmatically find the path to the settings file ---
# Get the absolute path of the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
# Go up two directory levels to get to the root 'Gem-System' folder
# (from NeuroSync_Player -> Neurosync -> Gem-System)
root_dir = os.path.dirname(os.path.dirname(script_dir))
# Construct the full, correct path to the settings file
SETTINGS_FILE = os.path.join(root_dir, 'mcp_settings.ini')


def get_playback_device_from_ini(config):
    """
    Reads the selected audio output device from the [Audio] section of the INI file.
    """
    print("--- Reading audio device from settings ---")
    try:
        # Get the raw string, e.g., "[18] Voicemeeter Input (VB-Audio Voi"
        device_str = config.get('Audio', 'selected_output')
        
        if device_str is None or device_str.lower() == 'none' or ']' not in device_str:
            print("❌ Audio output device is not set in mcp_settings.ini. Please configure it in the control panel.")
            return None
            
        # The device name is everything after the "] "
        device_name = device_str.split('] ', 1)[1]
        return device_name
        
    except (configparser.NoSectionError, configparser.NoOptionError):
        print(f"❌ FATAL ERROR: Could not find [Audio] section or 'selected_output' in '{SETTINGS_FILE}'.")
        print("   Please run the Master Control Panel first to select an audio device and save the settings.")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred while reading the audio device: {e}")
        return None

# --- Helper function for robust file deletion ---
def delete_file_with_retry(filepath, max_retries=5, delay=0.2):
    """
    Attempts to delete a file, retrying on failure to handle file locks.
    """
    for attempt in range(max_retries):
        try:
            os.remove(filepath)
            print(f"✅ Deleted '{os.path.basename(filepath)}'. Waiting for next file...")
            return True # Success
        except PermissionError:
            print(f"Attempt {attempt + 1}/{max_retries}: Could not delete file, it's locked. Retrying in {delay}s...")
            time.sleep(delay)
        except FileNotFoundError:
            print(f"File '{os.path.basename(filepath)}' was already deleted.")
            return True # Also a success
        except Exception as e:
            print(f"❌ An unexpected error occurred while trying to delete the file: {e}")
            return False # Unhandled error
    
    print(f"❌ FAILED to delete file '{os.path.basename(filepath)}' after {max_retries} attempts.")
    return False # Failed

# --- Main application entry point ---
if __name__ == "__main__":
    
    # --- Step 1: Load the configuration file ---
    config = configparser.ConfigParser()
    if not os.path.exists(SETTINGS_FILE):
        print(f"❌ FATAL ERROR: The settings file '{SETTINGS_FILE}' was not found.")
        print("   Please run the Master Control Panel first to generate it.")
        sys.exit(1)
        
    config.read(SETTINGS_FILE)
    
    # --- Step 2: Get settings from the loaded config ---
    try:
        target_file_path = config.get('Watcher', 'target_file_path')
        selected_device_name = get_playback_device_from_ini(config)
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"❌ FATAL ERROR: A required setting is missing from '{SETTINGS_FILE}'. Details: {e}")
        print("   Please ensure the [Watcher] section with 'target_file_path' and the [Audio] section exist.")
        sys.exit(1)

    if selected_device_name is None:
        print("Could not determine audio device from settings. Exiting.")
        sys.exit(1)
    
    print(f"\n✅ Using audio device from settings: '{selected_device_name}'")

    # --- 3. Initialize Pygame with the Selected Device ---
    try:
        pygame.mixer.pre_init(44100, -16, 2, 512, devicename=selected_device_name)
        pygame.init()
        print("✅ Pygame audio mixer initialized successfully.")
    except Exception as e:
        print(f"❌ FATAL ERROR: Could not initialize Pygame audio on the selected device. Error: {e}")
        sys.exit(1)

    # --- 4. Initialize project directories and Live Link connection ---
    initialize_directories()
    py_face = initialize_py_face()
    socket_connection = create_socket_connection()
    
    # Start the default background animation thread
    default_animation_thread = Thread(target=default_animation_loop, args=(py_face,))
    default_animation_thread.start()

    print("--- Automatic Processor Started (Definitive Deletion Mode) ---")
    print(f"Watching for file: {target_file_path}")
    print("Send a request to your TTS server to begin. Press Ctrl+C to stop.")

    try:
        # --- 5. Main watcher loop ---
        while True:
            if os.path.exists(target_file_path):
                print(f"\n✅ File '{os.path.basename(target_file_path)}' detected. Verifying it's complete...")
                
                last_size = os.path.getsize(target_file_path)
                time.sleep(0.1) 
                while last_size != os.path.getsize(target_file_path):
                    last_size = os.path.getsize(target_file_path)
                    print("   - File is still being written, waiting...")
                    time.sleep(0.1)
                
                print("✅ File is stable. Processing...")
                
                if ENABLE_EMOTE_CALLS:
                    EmoteConnect.send_emote("startspeaking")
                
                try:
                    process_wav_file(target_file_path, py_face, socket_connection, default_animation_thread)
                    print("✅ Processing complete.")

                except Exception as e:
                    print(f"❌ An error occurred during processing: {e}")

                finally:
                    if ENABLE_EMOTE_CALLS:
                        EmoteConnect.send_emote("stopspeaking")
                    
                    try:
                        if pygame.mixer.get_init():
                            print("Unloading audio from Pygame to release file lock...")
                            pygame.mixer.music.stop()
                            pygame.mixer.music.unload()
                            print("File lock released.")
                    except Exception as e:
                        print(f"Warning during Pygame unload: {e}")

                    delete_file_with_retry(target_file_path)
            
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping the watcher script.")

    finally:
        # --- 6. Cleanly shut down all resources ---
        print("Cleaning up resources...")
        stop_default_animation.set()
        if default_animation_thread and default_animation_thread.is_alive():
            default_animation_thread.join()
        pygame.quit()
        socket_connection.close()
        print("Cleanup complete. Exiting.")