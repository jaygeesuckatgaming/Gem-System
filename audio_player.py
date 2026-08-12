"""
Simple Audio File Watcher and Player
Watches for new WAV files and plays them automatically
No Neurosync, no face tracking - just audio playback
"""
import os
import time
import threading
from pathlib import Path
import pygame

# Configuration
WATCH_FOLDER = Path(__file__).parent / "tts_output"  # Centralized TTS output folder
AUDIO_FILE = WATCH_FOLDER / "server_output.wav"
CHECK_INTERVAL = 0.5  # Check every 0.5 seconds

# Initialize pygame mixer
pygame.mixer.init()

# State tracking
last_modified_time = 0
is_playing = False

def play_audio_file(file_path: Path):
    """Play the audio file"""
    global is_playing
    
    if not file_path.exists():
        print(f"[AUDIO PLAYER] File not found: {file_path}")
        return
    
    if is_playing:
        print("[AUDIO PLAYER] Already playing, skipping...")
        return
    
    try:
        print(f"[AUDIO PLAYER] Playing: {file_path.name}")
        pygame.mixer.music.load(str(file_path))
        pygame.mixer.music.play()
        is_playing = True
        
        # Wait for playback to complete
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        
        is_playing = False
        print("[AUDIO PLAYER] Playback complete")
        
    except Exception as e:
        print(f"[AUDIO PLAYER] Error playing file: {e}")
        is_playing = False

def watch_for_changes():
    """Watch for changes to the audio file"""
    global last_modified_time
    
    print(f"[AUDIO PLAYER] Watching: {WATCH_FOLDER}")
    print(f"[AUDIO PLAYER] Monitoring: {AUDIO_FILE}")
    print(f"[AUDIO PLAYER] Press Ctrl+C to stop")
    
    while True:
        try:
            if AUDIO_FILE.exists():
                current_modified_time = os.path.getmtime(AUDIO_FILE)
                
                # Check if file was modified since last check
                if current_modified_time != last_modified_time:
                    print(f"[AUDIO PLAYER] Detected new/updated file")
                    last_modified_time = current_modified_time
                    
                    # Small delay to ensure file is fully written
                    time.sleep(0.2)
                    
                    # Play in a separate thread so we can continue watching
                    play_thread = threading.Thread(target=play_audio_file, args=(AUDIO_FILE,))
                    play_thread.daemon = True
                    play_thread.start()
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            print("\n[AUDIO PLAYER] Stopping...")
            pygame.mixer.music.stop()
            break
        except Exception as e:
            print(f"[AUDIO PLAYER] Error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    watch_for_changes()
