"""
Simple Audio File Watcher and Player
Watches for new WAV files and plays them automatically
No Neurosync, no face tracking - just audio playback
"""
import os
import pygame
import time
import configparser
import sys
from threading import Thread

# --- Configuration ---
script_dir = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(script_dir, 'mcp_settings.ini')

def get_playback_device_from_ini(config):
    """
    Reads the selected audio output device from the [Audio] section of the INI file.
    Uses device ID for reliable matching.
    """
    try:
        device_str = config.get('Audio', 'selected_output')
        
        if device_str is None or device_str.lower() == 'none':
            print("Audio output device is not set in mcp_settings.ini. Using default.")
            return None
        
        # Extract device ID from "[ID] Name" format
        if ']' in device_str:
            device_id = int(device_str.split(']')[0].strip('['))
            device_name_partial = device_str.split('] ', 1)[1]
            print(f"Device ID from config: {device_id} (name: '{device_name_partial}')")
            
            import sounddevice as sd
            devices = sd.query_devices()
            
            # Find device by ID
            for dev in devices:
                if dev['index'] == device_id and dev['max_output_channels'] > 0:
                    full_name = dev['name']
                    print(f"Found device by ID: '{full_name}'")
                    return full_name
            
            # ID not found, try partial name match
            print(f"Device ID {device_id} not found, trying name match...")
            for dev in devices:
                if dev['name'].startswith(device_name_partial[:20]) and dev['max_output_channels'] > 0:
                    print(f"Found by partial name: '{dev['name']}'")
                    return dev['name']
            
            print(f"Could not find matching output device.")
            return None
        else:
            return None
            
    except (configparser.NoSectionError, configparser.NoOptionError):
        print("Could not find [Audio] section in settings. Using default device.")
        return None
    except Exception as e:
        print(f"Error reading audio device: {e}")
        return None

def delete_file_with_retry(filepath, max_retries=5, delay=0.2):
    """
    Attempts to delete a file, retrying on failure to handle file locks.
    """
    for attempt in range(max_retries):
        try:
            os.remove(filepath)
            print(f"Deleted '{os.path.basename(filepath)}'. Waiting for next file...")
            return True
        except PermissionError:
            print(f"Attempt {attempt + 1}/{max_retries}: File locked, retrying in {delay}s...")
            time.sleep(delay)
        except FileNotFoundError:
            print(f"File '{os.path.basename(filepath)}' was already deleted.")
            return True
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False
    
    print(f"FAILED to delete file '{os.path.basename(filepath)}' after {max_retries} attempts.")
    return False

if __name__ == "__main__":
    
    # --- Load configuration ---
    config = configparser.ConfigParser()
    if not os.path.exists(SETTINGS_FILE):
        print(f"Settings file '{SETTINGS_FILE}' not found. Using defaults.")
    else:
        config.read(SETTINGS_FILE)
    
    # --- Get audio device ---
    selected_device_name = get_playback_device_from_ini(config)
    
    if selected_device_name:
        print(f"Using audio device: '{selected_device_name}'")
    
    # --- Initialize Pygame with the correct device name ---
    # Use sounddevice to get the full device name from ID
    import sounddevice as sd
    devices = sd.query_devices()
    full_device_name = None
    
    # Try to find device by ID first
    try:
        device_str = config.get('Audio', 'selected_output')
        if ']' in device_str:
            device_id = int(device_str.split(']')[0].strip('['))
            for dev in devices:
                if dev['index'] == device_id and dev['max_output_channels'] > 0:
                    full_device_name = dev['name']
                    break
    except:
        pass
    
    print("\n" + "="*60)
    print(f"🔍  Searching for audio device match for: '{selected_device_name}'")

    try:
        pygame.init()
        from pygame._sdl2 import get_audio_device_names
        
        available_devices = get_audio_device_names(False)
        
        final_device_name = None
        
        if selected_device_name:
            for device in available_devices:
                if selected_device_name == device or selected_device_name in device:
                    final_device_name = device
                    print(f"✅  MATCH FOUND: Using hardware device: '{final_device_name}'")
                    break
        
        pygame.quit()
        
        if final_device_name:
            pygame.mixer.pre_init(44100, -16, 2, 512, devicename=final_device_name)
        else:
            print("⚠️  NO MATCH / FALLBACK: Using System Default Audio Device.")
            pygame.mixer.pre_init(44100, -16, 2, 512, devicename=None)

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
        
    print("Audio mixer ready.")
    
    # --- Get target file path from settings or use default ---
    # Use the centralized tts_output folder in the same directory as this script
    target_file_path = os.path.join(script_dir, 'tts_output', 'server_output.wav')
    
    print("--- Audio Player Started ---")
    print(f"Script directory: {script_dir}")
    print(f"Watching for file: {target_file_path}")
    print(f"File exists right now: {os.path.exists(target_file_path)}")
    print("Press Ctrl+C to stop.")
    
    try:
        while True:
            if os.path.exists(target_file_path):
                print(f"\nFile '{os.path.basename(target_file_path)}' detected. Verifying it's complete...")
                
                last_size = os.path.getsize(target_file_path)
                time.sleep(0.1) 
                while last_size != os.path.getsize(target_file_path):
                    last_size = os.path.getsize(target_file_path)
                    print("   - File is still being written, waiting...")
                    time.sleep(0.1)
                
                print("File is stable. Playing...")
                
                # Signal ducking start via signal file (for control_panel.py to detect)
                try:
                    import configparser
                    config = configparser.ConfigParser()
                    if os.path.exists('mcp_settings.ini'):
                        config.read('mcp_settings.ini')
                        ducking_enabled = config.getboolean('AudioDucking', 'enabled', fallback=False)
                        if ducking_enabled:
                            # Write signal file for control panel to detect
                            duck_amount = config.get('AudioDucking', 'duck_amount', fallback='-15')
                            attack_ms = config.get('AudioDucking', 'attack_ms', fallback='100')
                            release_ms = config.get('AudioDucking', 'release_ms', fallback='500')
                            
                            signal_file = os.path.join(script_dir, 'ducking_signal.txt')
                            with open(signal_file, 'w') as f:
                                f.write(f"{duck_amount}\n{attack_ms}\n{release_ms}\n")
                            print(f"Audio ducking signal sent (amount={duck_amount}dB)")
                except Exception as e:
                    print(f"Warning: Could not send ducking signal: {e}")
                
                try:
                    pygame.mixer.music.load(target_file_path)
                    pygame.mixer.music.play()
                    
                    # Wait for playback to complete
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    
                    print("Playback complete.")
                    
                except Exception as e:
                    print(f"Error during playback: {e}")
                
                finally:
                    # Remove ducking signal file (signals release)
                    try:
                        signal_file = os.path.join(script_dir, 'ducking_signal.txt')
                        if os.path.exists(signal_file):
                            os.remove(signal_file)
                            print("Audio ducking signal cleared")
                    except Exception as e:
                        print(f"Warning: Could not clear ducking signal: {e}")
                    
                    # Unload audio to release file lock
                    try:
                        if pygame.mixer.get_init():
                            pygame.mixer.music.stop()
                            pygame.mixer.music.unload()
                    except Exception as e:
                        print(f"Warning during unload: {e}")
                    
                    delete_file_with_retry(target_file_path)
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\nStopping the audio player.")
    
    finally:
        print("Cleaning up resources...")
        pygame.quit()
        print("Cleanup complete. Exiting.")
