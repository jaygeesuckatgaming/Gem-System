"""
VMagicMirror OSC Controller
Sends OSC messages to trigger motions
"""
from pythonosc.dispatcher import Dispatcher
from pythonosc.udp_client import SimpleUDPClient
import keyboard
import time

# VMagicMirror default OSC settings
OSC_HOST = "127.0.0.1"
OSC_PORT = 9000  # Default VMagicMirror OSC port

# Motion mapping (customize to match your VMagicMirror setup!)
MOTIONS = {
    'a': '/motion/1',
    's': '/motion/2',
    'd': '/motion/3',
    'f': '/motion/4',
    'g': '/motion/5',
    'h': '/motion/6',
    'j': '/motion/7',
    'k': '/motion/8',
}

print("="*60)
print("VMagicMirror OSC Controller")
print("="*60)

# Create OSC client
client = SimpleUDPClient(OSC_HOST, OSC_PORT)
print(f"\nTarget: {OSC_HOST}:{OSC_PORT}")
print("Make sure VMagicMirror is listening on this port!")

print("\n" + "="*60)
print("Controls:")
print("="*60)
for key, motion in MOTIONS.items():
    print(f"  {key.upper():8} -> {motion}")
print("\nPress Ctrl+C to exit")
print("="*60)

def send_motion(path):
    """Send OSC motion trigger"""
    try:
        client.send_message(path, [1.0])
        print(f"Sent: {path}")
    except Exception as e:
        print(f"Error: {e}")

print("\nReady! Press keys to trigger motions...\n")

# Keyboard listener
def on_press(event):
    key = event.name.lower()
    if key in MOTIONS:
        send_motion(MOTIONS[key])
    elif key == 'q':
        print("Quitting...")
        exit()

keyboard.on_press(on_press)

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nStopped")
