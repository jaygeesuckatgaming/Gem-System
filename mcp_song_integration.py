"""
Song Wakeword Integration for MCP v2
Add this import and handler to mcp_v2.py
"""

# Add this import near the top of mcp_v2.py (after line 42):
# from song_wakeword import SongWakewordHandler

# Add this global variable after settings are loaded:
# song_handler = SongWakewordHandler()

# Add this function to check for song commands:
def check_song_command(text):
    """
    Check if text contains a song command and handle it.
    Returns True if handled, False otherwise.
    """
    text_lower = text.lower().strip()
    
    # Check for song wakeword patterns
    song_patterns = [
        "gem sing the song ",
        "sing the song ",
        "gem play the song ",
        "play the song ",
        "gem sing ",
        "sing ",
    ]
    
    song_name = None
    for pattern in song_patterns:
        if text_lower.startswith(pattern):
            song_name = text_lower[len(pattern):].strip()
            break
    
    if song_name:
        print(f"🎵 Song command detected: '{song_name}'")
        try:
            from song_wakeword import SongWakewordHandler
            handler = SongWakewordHandler()
            
            # Launch player in background thread
            import threading
            thread = threading.Thread(target=handler.handle_command, args=(text,))
            thread.daemon = True
            thread.start()
            
            return True
        except Exception as e:
            print(f"Error handling song command: {e}")
    
    return False

# Example usage in your chat/response processing:
# if check_song_command(user_message):
#     return  # Song command was handled, skip normal processing
