"""
Wakeword Handler for Dual Audio Player
Integrate with MCP to trigger song playback
"""

import os
import sys
from pathlib import Path
from dual_audio_player import DualAudioPlayer
from song_library import SongLibrary

class SongWakewordHandler:
    def __init__(self):
        self.library = SongLibrary()
        self.player_window = None
    
    def handle_command(self, command: str) -> bool:
        """
        Handle wakeword command like "Gem sing the song never gonna give you up"
        Returns True if handled successfully.
        """
        command = command.lower().strip()
        
        # Check for wakeword patterns
        patterns = [
            "gem sing the song ",
            "sing the song ",
            "gem play the song ",
            "play the song ",
            "gem sing ",
            "sing ",
        ]
        
        song_name = None
        for pattern in patterns:
            if command.startswith(pattern):
                song_name = command[len(pattern):].strip()
                break
        
        if not song_name:
            return False
        
        print(f"🎵 Wakeword detected! Searching for: {song_name}")
        
        # Find the song
        result = self.library.find_song(song_name)
        
        if not result:
            print(f"❌ Song '{song_name}' not found in library")
            print(f"Available songs: {', '.join(self.library.list_songs())}")
            return False
        
        file1, file2 = result
        print(f"✓ Found song files:")
        print(f"  File 1: {file1}")
        print(f"  File 2: {file2}")
        
        # Launch player in a separate thread to avoid blocking
        import threading
        player_thread = threading.Thread(target=self.launch_player, args=(file1, file2), daemon=True)
        player_thread.start()
        
        return True
    
    def launch_player(self, file1: str, file2: str, device1: str = None, device2: str = None):
        """Launch dual audio player with pre-loaded files"""
        import tkinter as tk
        
        # Create hidden root window
        root = tk.Tk()
        root.withdraw()  # Hide main window
        
        # Create player
        player = DualAudioPlayer()
        player.root.deiconify()  # Show player window
        
        # Load files and devices
        player.load_files(file1, file2, device1, device2)
        
        # Start player
        player.run()
    
    def list_available_songs(self):
        """Print list of available songs"""
        songs = self.library.list_songs()
        
        if not songs:
            print("No songs in library yet!")
            print(f"Add songs to: {self.library.music_folder}")
            return
        
        print("\n🎵 Available songs in library:")
        for song in songs:
            print(f"  - {song}")
        print()


if __name__ == "__main__":
    # Test the handler
    handler = SongWakewordHandler()
    
    print("Dual Audio Player - Wakeword Handler Test")
    print("=" * 50)
    
    # List available songs
    handler.list_available_songs()
    
    # Test command
    test_command = "gem sing the song never_gonna_give_you_up"
    print(f"Testing command: {test_command}")
    
    result = handler.handle_command(test_command)
    
    if result:
        print("✓ Command handled successfully!")
    else:
        print("✗ Command not recognized or song not found")
