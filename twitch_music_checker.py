# ==============================================================================
#                      Twitch Music Request Checker
#          Verifies if songs are allowed under Twitch DJ Program
# ==============================================================================

import json
import os
import re
from typing import Optional, Dict, Tuple

RESTRICTED_ARTISTS_FILE = "twitch_restricted_artists.json"

LOCAL_RESTRICTED_LIST = [
    "ac/dc", "adele", "aerosmith", "beyoncé", "beatles", "black sabbath",
    "coldplay", "drake", "eagles", "guns n' roses", "kanye west", "led zeppelin",
    "metallica", "michael jackson", "pink floyd", "queen", "radiohead", "rolling stones",
    "taylor swift", "the weeknd", "u2", "whitney houston"
]

def load_restricted_artists():
    """Load restricted artists from local JSON file."""
    if os.path.exists(RESTRICTED_ARTISTS_FILE):
        try:
            with open(RESTRICTED_ARTISTS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [artist.lower().strip() for artist in data.get('artists', [])]
        except Exception as e:
            print(f"TWITCH CHECKER ERROR: Could not load restricted artists: {e}")
    return [artist.lower() for artist in LOCAL_RESTRICTED_LIST]

def save_restricted_artists(artists: list):
    """Save restricted artists to local JSON file."""
    try:
        with open(RESTRICTED_ARTISTS_FILE, 'w', encoding='utf-8') as f:
            json.dump({'artists': artists}, f, indent=2)
        print(f"TWITCH CHECKER: Saved {len(artists)} restricted artists to {RESTRICTED_ARTISTS_FILE}")
    except Exception as e:
        print(f"TWITCH CHECKER ERROR: Could not save restricted artists: {e}")

def check_local_blacklist(artist: str, restricted_list: list) -> bool:
    """Check if artist is in local restricted list."""
    artist_clean = artist.lower().strip()
    for restricted in restricted_list:
        if restricted in artist_clean or artist_clean in restricted:
            return True
    return False

def parse_song_request(text: str, llm_parse_function) -> Optional[Dict[str, str]]:
    """
    Parse a song request into clean artist/track format.
    
    Args:
        text: Raw chat message (e.g., "can u play shape of you by ed")
        llm_parse_function: Function to call LLM for parsing
    
    Returns:
        Dict with 'artist' and 'track' keys, or None if parsing fails
    """
    patterns = [
        r'(?:play|song|track|music)\s+(?:by\s+)?(.+?)(?:\s+by\s+)(.+?)(?:\s|$)',
        r'(.+?)\s+-\s+(.+)',
        r'by\s+(.+?)\s+(?:-|:)?\s*(.+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                return {
                    'artist': groups[1].strip() if 'by' in pattern else groups[0].strip(),
                    'track': groups[0].strip() if 'by' in pattern else groups[1].strip()
                }
    
    if llm_parse_function:
        try:
            prompt = f"""Parse this song request into JSON format. Extract artist and track name.
            Request: "{text}"
            
            Output ONLY valid JSON like this:
            {{"artist": "Artist Name", "track": "Song Title"}}
            
            If you cannot identify both artist and track, output null."""
            
            result = llm_parse_function(prompt)
            if result:
                json_match = re.search(r'\{[^}]+\}', result, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    if parsed.get('artist') and parsed.get('track'):
                        return parsed
        except Exception as e:
            print(f"TWITCH CHECKER: LLM parsing failed: {e}")
    
    return None

def check_twitch_catalog_browser(artist: str, track: str) -> str:
    """
    Check if song is allowed in Twitch DJ catalog using headless browser.
    
    Args:
        artist: Clean artist name
        track: Clean track name
    
    Returns:
        "Allowed", "Restricted", or "Not Found"
    """
    try:
        from playwright.sync_api import sync_playwright
        
        query = f"{artist} - {track}"
        print(f"TWITCH CHECKER: Searching catalog for '{query}'")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://www.twitch.tv/dj-signup#dj-music-catalog", timeout=30000)
            
            page.wait_for_selector("input[placeholder*='Search']", timeout=10000)
            page.fill("input[placeholder*='Search']", query)
            page.keyboard.press("Enter")
            
            page.wait_for_timeout(2000)
            
            results_html = page.content()
            browser.close()
            
            if "Allowed" in results_html and "Restricted" not in results_html:
                print(f"TWITCH CHECKER: '{query}' is ALLOWED")
                return "Allowed"
            elif "Restricted" in results_html:
                print(f"TWITCH CHECKER: '{query}' is RESTRICTED")
                return "Restricted"
            else:
                print(f"TWITCH CHECKER: '{query}' NOT FOUND")
                return "Not Found"
                
    except ImportError:
        print("TWITCH CHECKER ERROR: playwright not installed. Run: pip install playwright")
        return "Error: playwright not installed"
    except Exception as e:
        print(f"TWITCH CHECKER ERROR: {e}")
        return f"Error: {str(e)}"

class TwitchMusicChecker:
    """Main class for Twitch music request verification."""
    
    def __init__(self, llm_parse_function=None):
        self.restricted_list = load_restricted_artists()
        self.llm_parse_function = llm_parse_function
        print(f"TWITCH CHECKER: Initialized with {len(self.restricted_list)} restricted artists")
    
    def verify_request(self, request_text: str) -> Dict:
        """
        Verify if a song request is allowed.
        
        Args:
            request_text: Raw chat message from viewer
        
        Returns:
            Dict with status, artist, track, and message
        """
        parsed = parse_song_request(request_text, self.llm_parse_function)
        
        if not parsed:
            return {
                'status': 'error',
                'message': "I couldn't identify the song. Please format as: 'Artist - Track'"
            }
        
        artist = parsed['artist']
        track = parsed['track']
        
        if check_local_blacklist(artist, self.restricted_list):
            return {
                'status': 'restricted',
                'artist': artist,
                'track': track,
                'message': f"Sorry! {artist} is restricted under Twitch's DJ Program guidelines."
            }
        
        catalog_result = check_twitch_catalog_browser(artist, track)
        
        if catalog_result == "Allowed":
            return {
                'status': 'allowed',
                'artist': artist,
                'track': track,
                'message': f"✅ '{track}' by {artist} is allowed!"
            }
        elif catalog_result == "Restricted":
            return {
                'status': 'restricted',
                'artist': artist,
                'track': track,
                'message': f"Sorry! '{track}' by {artist} is restricted."
            }
        else:
            return {
                'status': 'not_found',
                'artist': artist,
                'track': track,
                'message': f"'{track}' by {artist} was not found in the Twitch DJ catalog."
            }

if __name__ == "__main__":
    print("Twitch Music Checker - Test Mode")
    print("=" * 50)
    
    checker = TwitchMusicChecker()
    
    test_requests = [
        "play shape of you by ed sheeran",
        "can you play led zeppelin stairway to heaven",
        "req: taylor swift - shake it off"
    ]
    
    for req in test_requests:
        print(f"\nTesting: '{req}'")
        result = checker.verify_request(req)
        print(f"Result: {result['status']} - {result['message']}")
