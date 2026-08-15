"""
Song Library Manager
Search and manage dual-track song files
"""

import os
from pathlib import Path
from typing import Optional, Tuple

class SongLibrary:
    def __init__(self, music_folder: str = None):
        if music_folder is None:
            # Default to karaoke folder in requests
            self.music_folder = Path(__file__).parent / "requests" / "karaoke"
        else:
            self.music_folder = Path(music_folder)
        
        # Ensure folder exists
        self.music_folder.mkdir(exist_ok=True)
    
    def find_song(self, song_name: str) -> Optional[Tuple[str, str]]:
        """
        Find song files by name.
        Returns (file1_path, file2_path) or None if not found.
        
        Searches for:
        - {song_name}_vocals.wav and {song_name}_instrumental.wav
        - {song_name}_track1.wav and {song_name}_track2.wav
        - {song_name}_a.wav and {song_name}_b.wav
        """
        song_name = song_name.lower().replace(" ", "_").replace("-", "_")
        
        # Possible naming patterns
        patterns = [
            ("_vocals", "_instrumental"),
            ("_track1", "_track2"),
            ("_track_a", "_track_b"),
            ("_a", "_b"),
            ("_left", "_right"),
            ("_main", "_alt"),
        ]
        
        for pattern1, pattern2 in patterns:
            file1 = self.music_folder / f"{song_name}{pattern1}.wav"
            file2 = self.music_folder / f"{song_name}{pattern2}.wav"
            
            if file1.exists() and file2.exists():
                return (str(file1), str(file2))
        
        # Try without pattern (exact match)
        file1 = self.music_folder / f"{song_name}.wav"
        file2 = self.music_folder / f"{song_name}_2.wav"
        
        if file1.exists() and file2.exists():
            return (str(file1), str(file2))
        
        return None
    
    def list_songs(self) -> list:
        """List all available songs in the library"""
        songs = set()
        
        for file in self.music_folder.glob("*.wav"):
            name = file.stem
            
            # Remove common suffixes
            for suffix in ["_vocals", "_instrumental", "_track1", "_track2", "_a", "_b", "_2"]:
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
                    break
            
            songs.add(name)
        
        return sorted(list(songs))
    
    def add_song(self, file1: str, file2: str, song_name: str):
        """Add a new song to the library"""
        song_name = song_name.lower().replace(" ", "_").replace("-", "_")
        
        # Copy files to music folder with standard naming
        import shutil
        
        file1_path = Path(file1)
        file2_path = Path(file2)
        
        dest1 = self.music_folder / f"{song_name}_vocals.wav"
        dest2 = self.music_folder / f"{song_name}_instrumental.wav"
        
        shutil.copy2(file1_path, dest1)
        shutil.copy2(file2_path, dest2)
        
        print(f"Added song: {song_name}")
        return True


if __name__ == "__main__":
    # Test the library
    lib = SongLibrary()
    
    print(f"Music folder: {lib.music_folder}")
    print(f"Available songs: {lib.list_songs()}")
    
    # Test search
    result = lib.find_song("never_gonna_give_you_up")
    if result:
        print(f"Found: {result}")
    else:
        print("Song not found")
