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

# --- NEW: Robust, portable method to find the project root ---
def find_project_root(marker_file='.project_root'):
    print("\n--- Starting Root Discovery ---")
    try:
        script_path = os.path.abspath(__file__)
        current_dir = os.path.dirname(script_path)
    except NameError:
        current_dir = os.getcwd()

    limit = 10 
    for i in range(limit):
        if os.path.exists(os.path.join(current_dir, marker_file)):
            return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    return None

root_dir = find_project_root()
if not root_dir:
    raise FileNotFoundError("Could not find the project root. Make sure a '.project_root' file exists in your main 'Gem-System' folder.")

SETTINGS_FILE = os.path.join(root_dir, 'mcp_settings.ini')

def get_playback_device_from_ini(config):
    try:
        device_str = config.get('Audio', 'selected_output')
        if device_str is None or device_str.lower() == 'none' or ']' not in device_str:
            return None
        # Extract name after the [ID] part
        device_name = device_str.split('] ', 1)[1]
        return device_name
    except Exception:
        return None

def delete_file_with_retry(filepath, max_retries=5, delay=0.2):
    for attempt in range(max_retries):
        try:
            os.remove(filepath)
            print(f"✅ Deleted '{os.path.basename(filepath)}'. Waiting for next file...")
            return True
        except PermissionError:
            time.sleep(delay)
        except FileNotFoundError:
            return True
        except Exception:
            return False
    print(f"❌ FAILED to delete file '{os.path.basename(filepath)}'.")
    return False

if __name__ == "__main__":
    
    config = configparser.ConfigParser()
    if not os.path.exists(SETTINGS_FILE):
        print(f"❌ FATAL ERROR: The settings file was not found: '{SETTINGS_FILE}'")
        sys.exit(1)
        
    config.read(SETTINGS_FILE)
    
    try:
        target_file_path = config.get('Watcher', 'target_file_path')
        requested_name = get_playback_device_from_ini(config)
    except Exception as e:
        print(f"❌ FATAL ERROR: Missing setting. Details: {e}")
        sys.exit(1)

    # ---------------------------------------------------------
    # SMART AUDIO INITIALIZATION (Fixes 'No such device')
    # ---------------------------------------------------------
    print("\n" + "="*60)
    print(f"🔍  Searching for audio device match for: '{requested_name}'")

    # 1. Init Pygame Base (Video) first to get access to device lists
    try:
        pygame.init() 
        from pygame._sdl2 import get_audio_device_names
        
        # Get actual hardware names
        available_devices = get_audio_device_names(False) # False = Output
        
        final_device_name = None
        
        # 2. Smart Match Algorithm
        if requested_name:
            for device in available_devices:
                # Check for exact match OR substring match (e.g. "Speakers" inside "Speakers (Realtek)")
                if requested_name == device or requested_name in device:
                    final_device_name = device
                    print(f"✅  MATCH FOUND: Using hardware device: '{final_device_name}'")
                    break
        
        # 3. Apply the configuration
        # We must quit the default init and re-init with the specific mixer settings
        pygame.quit() 
        
        if final_device_name:
            # Use the verified hardware name
            pygame.mixer.pre_init(44100, -16, 2, 512, devicename=final_device_name)
        else:
            # Fallback to system default if no match found
            print("⚠️  NO MATCH / FALLBACK: Using System Default Audio Device.")
            pygame.mixer.pre_init(44100, -16, 2, 512, devicename=None)

        # 4. Final Initialization
        pygame.init()
        pygame.mixer.init()
        
        if pygame.mixer.get_init():
            print("🔊  Audio Engine is Ready.")
        else:
            print("❌  Audio Engine failed to start.")
            sys.exit(1)

    except Exception as e:
        print(f"❌ CRITICAL AUDIO ERROR: {e}")
        print("   -> Defaulting to standard system audio to prevent crash.")
        try:
            pygame.quit()
            pygame.init()
            pygame.mixer.init()
        except:
            pass

    print("="*60 + "\n")
    # ---------------------------------------------------------

    initialize_directories()
    py_face = initialize_py_face()
    socket_connection = create_socket_connection()
    
    default_animation_thread = Thread(target=default_animation_loop, args=(py_face,))
    default_animation_thread.start()

    print("--- Automatic Processor Started ---")
    print(f"Watching for file: {target_file_path}")

    try:
        while True:
            if os.path.exists(target_file_path):
                print(f"\n✅ File detected: '{os.path.basename(target_file_path)}'")
                
                # Wait for file write to complete
                last_size = -1
                while last_size != os.path.getsize(target_file_path):
                    last_size = os.path.getsize(target_file_path)
                    time.sleep(0.1)
                
                if ENABLE_EMOTE_CALLS:
                    EmoteConnect.send_emote("startspeaking")
                
                try:
                    process_wav_file(target_file_path, py_face, socket_connection, default_animation_thread)
                    print("✅ Processing complete.")
                except Exception as e:
                    print(f"❌ Error during processing: {e}")
                finally:
                    if ENABLE_EMOTE_CALLS:
                        EmoteConnect.send_emote("stopspeaking")
                    
                    # Release audio lock
                    try:
                        if pygame.mixer.get_init():
                            pygame.mixer.music.stop()
                            pygame.mixer.music.unload()
                    except:
                        pass

                    delete_file_with_retry(target_file_path)
            
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        stop_default_animation.set()
        if default_animation_thread and default_animation_thread.is_alive():
            default_animation_thread.join()
        pygame.quit()
        socket_connection.close()
        print("Exiting.")