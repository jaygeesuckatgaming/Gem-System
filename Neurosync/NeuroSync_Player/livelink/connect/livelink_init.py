import socket
from livelink.connect.pylivelinkface import PyLiveLinkFace, FaceBlendShape
import os            # --- NEW ---
import configparser  # --- NEW ---

# --- NEW: Robust, portable method to find the project root ---
def find_project_root(marker_file='.project_root'):
    """Walks up from the script's location to find the project root."""
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        current_dir = os.getcwd()
    while True:
        if os.path.exists(os.path.join(current_dir, marker_file)):
            return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            return None
        current_dir = parent_dir

root_dir = find_project_root()
if not root_dir:
    raise FileNotFoundError("Could not find the project root. Make sure a '.project_root' file exists in your main 'Gem-System' folder.")
SETTINGS_FILE = os.path.join(root_dir, 'mcp_settings.ini')

# --- MODIFIED: Read settings from the INI file ---
config = configparser.ConfigParser()
# Provide safe defaults that match the original hardcoded values
UDP_IP_FROM_INI = "192.168.1.101"
UDP_PORT_FROM_INI = 11111

if os.path.exists(SETTINGS_FILE):
    try:
        config.read(SETTINGS_FILE)
        UDP_IP_FROM_INI = config.get('LiveLink', 'ip', fallback=UDP_IP_FROM_INI)
        UDP_PORT_FROM_INI = config.getint('LiveLink', 'port', fallback=UDP_PORT_FROM_INI)
        print(f"✅ livelink_init.py: Successfully loaded [LiveLink] settings.")
    except Exception as e:
        print(f"⚠️ livelink_init.py WARNING: Could not read [LiveLink] settings. Using defaults. Error: {e}")
else:
    print(f"⚠️ livelink_init.py WARNING: Settings file not found. Using default LiveLink settings.")

# --- Use the loaded (or default) values ---
UDP_IP = UDP_IP_FROM_INI
UDP_PORT = UDP_PORT_FROM_INI

def create_socket_connection():
    # This function now uses the globally defined UDP_IP and UDP_PORT
    print(f"Attempting to connect to LiveLink at {UDP_IP}:{UDP_PORT}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect((UDP_IP, UDP_PORT))
    print("✅ Socket connection established.")
    return s

def initialize_py_face():
    py_face = PyLiveLinkFace()
    initial_blendshapes = [0.0] * 61
    for i, value in enumerate(initial_blendshapes):
        py_face.set_blendshape(FaceBlendShape(i), float(value))
    return py_face