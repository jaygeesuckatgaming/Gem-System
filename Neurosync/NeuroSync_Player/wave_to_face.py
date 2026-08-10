import os
import pygame
import warnings
import time
import configparser
import sys
from threading import Thread

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
    
    # Initialize project directories and Live Link connection
    initialize_directories()
    py_face = initialize_py_face()
    socket_connection = create_socket_connection()
    
    # Start the default background animation thread
    default_animation_thread = Thread(target=default_animation_loop, args=(py_face,))
    default_animation_thread.start()

    # Load configuration from the settings file
    config = configparser.ConfigParser()
    try:
        config.read('watcher_settings.ini')
        target_file_path = config.get('Watcher', 'target_file_path')
    except (configparser.NoSectionError, configparser.NoOptionError, FileNotFoundError):
        print("FATAL ERROR: Could not find 'watcher_settings.ini' or 'target_file_path' within it.")
        print("Please create the file and add the [Watcher] section with the full path to the audio file.")
        sys.exit(1) # Exit if the config is missing or invalid

    print("--- Automatic Processor Started (Definitive Deletion Mode) ---")
    print(f"Watching for file: {target_file_path}")
    print("Send a request to your TTS server to begin. Press Ctrl+C to stop.")

    try:
        # Main watcher loop
        while True:
            if os.path.exists(target_file_path):
                print(f"\n✅ File '{os.path.basename(target_file_path)}' detected. Verifying it's complete...")
                
                # Robust check to ensure the file has finished writing
                last_size = os.path.getsize(target_file_path)
                time.sleep(0.1) # Wait a moment to see if the size changes
                while last_size != os.path.getsize(target_file_path):
                    last_size = os.path.getsize(target_file_path)
                    print("   - File is still being written, waiting...")
                    time.sleep(0.1)
                
                print("✅ File is stable. Processing...")
                
                if ENABLE_EMOTE_CALLS:
                    EmoteConnect.send_emote("startspeaking")
                
                try:
                    # This function will play the audio, which locks the file via Pygame.
                    process_wav_file(target_file_path, py_face, socket_connection, default_animation_thread)
                    print("✅ Processing complete.")

                except Exception as e:
                    print(f"❌ An error occurred during processing: {e}")

                finally:
                    if ENABLE_EMOTE_CALLS:
                        EmoteConnect.send_emote("stopspeaking")
                    
                    # CRITICAL FIX: Unload the audio from Pygame to release the file lock
                    # This must happen BEFORE attempting to delete the file.
                    try:
                        if pygame.mixer.get_init():
                            print("Unloading audio from Pygame to release file lock...")
                            pygame.mixer.music.stop()
                            pygame.mixer.music.unload()
                            print("File lock released.")
                    except Exception as e:
                        print(f"Warning during Pygame unload: {e}")

                    # Now, deletion will succeed.
                    delete_file_with_retry(target_file_path)
            
            # Wait for a second before checking again to be efficient
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping the watcher script.")

    finally:
        # Cleanly shut down all resources
        print("Cleaning up resources...")
        stop_default_animation.set()
        if default_animation_thread and default_animation_thread.is_alive():
            default_animation_thread.join()
        pygame.quit()
        socket_connection.close()
        print("Cleanup complete. Exiting.")