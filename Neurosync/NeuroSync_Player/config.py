import os
import configparser

# --- NEW: Robust, portable method to find the project root ---
def find_project_root(marker_file='.project_root'):
    """Walks up from the script's location to find the project root."""
    try:
        # Start from the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        # Fallback for environments where __file__ is not defined
        current_dir = os.getcwd()
        
    while True:
        # Check if the anchor file exists in the current directory
        if os.path.exists(os.path.join(current_dir, marker_file)):
            return current_dir
        # Go up one level
        parent_dir = os.path.dirname(current_dir)
        # If we have reached the top of the filesystem (e.g., "C:\"), stop
        if parent_dir == current_dir:
            return None
        current_dir = parent_dir

root_dir = find_project_root()
if not root_dir:
    # This will stop the script with a clear error if the anchor file is missing.
    raise FileNotFoundError("Could not find the project root. Make sure a '.project_root' file exists in your main 'Gem-System' folder.")

# Construct the full path to the settings file
SETTINGS_FILE = os.path.join(root_dir, 'mcp_settings.ini')


# --- Now, read the configuration ---
config = configparser.ConfigParser()
# Provide a safe default value
default_neurosync_url = "http://127.0.0.1:9000/audio_to_blendshapes"
neurosync_url_from_ini = default_neurosync_url

if os.path.exists(SETTINGS_FILE):
    try:
        config.read(SETTINGS_FILE)
        # Read the URL from the [Neurosync] section, using the default as a fallback
        neurosync_url_from_ini = config.get('Neurosync', 'neurosync_local_url', fallback=default_neurosync_url)
        print(f"✅ config.py: Successfully loaded settings from '{SETTINGS_FILE}'")
    except Exception as e:
        print(f"⚠️ config.py WARNING: Could not read Neurosync URL from settings file. Using default. Error: {e}")
else:
    # This branch is now less likely to be hit because of the check above, but is good for safety.
    print(f"⚠️ config.py WARNING: Settings file not found. Using default Neurosync URL.")


# --- Original settings from your script ---
USE_LOCAL_LLM = True
USE_STREAMING = True
LLM_API_URL = "http://127.0.0.1:5050/generate_llama"
LLM_STREAM_URL = "http://127.0.0.1:5050/generate_stream"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "YOUR-KEY-GOES-HERE")

MAX_CHUNK_LENGTH = 500
FLUSH_TOKEN_COUNT = 300

DEFAULT_VOICE_NAME = 'bf_isabella'
USE_LOCAL_AUDIO = True
LOCAL_TTS_URL = "http://127.0.0.1:8000/generate_speech" 
USE_COMBINED_ENDPOINT = False

ENABLE_EMOTE_CALLS = False
USE_VECTOR_DB = False


BASE_SYSTEM_MESSAGE = "You are Mai, be nice.\n\n"

# ---------------------------
# Emote Sender Configuration (new)
# ---------------------------
EMOTE_SERVER_ADDRESS = "127.0.0.1"
EMOTE_SERVER_PORT = 7777

# ---------------------------
# Transcription Server Configuration (new)
# ---------------------------
TRANSCRIPTION_SERVER_URL = "http://127.0.0.1:6969/transcribe"

# ---------------------------
# Embedding Configurations (new)
# ---------------------------
USE_OPENAI_EMBEDDING = False
EMBEDDING_LOCAL_SERVER_URL = "http://127.0.0.1:7070/get_embedding"
EMBEDDING_OPENAI_MODEL = "text-embedding-3-small"
LOCAL_EMBEDDING_SIZE = 768
OPENAI_EMBEDDING_SIZE = 1536

# ---------------------------
# Neurosync API Configurations (new)
# ---------------------------

# --- Use the value read from the INI file ---
NEUROSYNC_LOCAL_URL = neurosync_url_from_ini

# ---------------------------
# TTS with Blendshapes Endpoint (new)
# ---------------------------
TTS_WITH_BLENDSHAPES_REALTIME_API = "http://127.0.0.1:8000/synthesize_and_blendshapes"

### ignore these
NEUROSYNC_API_KEY = "YOUR-NEUROSYNC-API-KEY" # ignore this 
NEUROSYNC_REMOTE_URL = "https://api.neurosync.info/audio_to_blendshapes" #ignore this


def get_llm_config(system_message=None):
    """
    Returns a dictionary of LLM configuration parameters.
    
    If no system_message is provided, it defaults to BASE_SYSTEM_MESSAGE.
    """
    if system_message is None:
        system_message = BASE_SYSTEM_MESSAGE
    return {
        "USE_VECTOR_DB":USE_VECTOR_DB,
        "USE_LOCAL_LLM": USE_LOCAL_LLM,
        "USE_STREAMING": USE_STREAMING,
        "LLM_API_URL": LLM_API_URL,
        "LLM_STREAM_URL": LLM_STREAM_URL,
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "max_chunk_length": MAX_CHUNK_LENGTH,
        "flush_token_count": FLUSH_TOKEN_COUNT,
        "system_message": system_message,
    }


def setup_warnings():
    """
    Set up common warning filters.
    """
    import warnings
    warnings.filterwarnings(
        "ignore", 
        message="Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work"
    )