"""
Gem Voice to VMagicMirror Bridge
Listens for "Gem wave" etc. and sends hotkeys to VMagicMirror
Run this alongside MCP - no MCP changes needed!
"""
import keyboard
import time
import re

MOTION_MAP = {
    'wave': '1',
    'dance': '2',
    'bow': '3',
    'jump': '4',
    'spin': '5',
    'clap': '6',
    'laugh': '7',
    'cry': '8',
    'sleep': '9',
}

def send_ctrl_alt(key):
    """Send Ctrl+Alt+{key}"""
    try:
        keyboard.press('ctrl')
        keyboard.press('alt')
        keyboard.press(key)
        time.sleep(0.05)
        keyboard.release(key)
        keyboard.release('alt')
        keyboard.release('ctrl')
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def check_and_trigger(text):
    """Check if text contains Gem motion command"""
    text_lower = text.lower()
    
    # Look for pattern "gem {motion}"
    for motion, key in MOTION_MAP.items():
        if re.search(rf'gem\s+{motion}', text_lower):
            print(f"\n[VMagic] Detected: 'Gem {motion}'")
            if send_ctrl_alt(key):
                print(f"[VMagic] ✓ Sent Ctrl+Alt+{key}")
            return True
    
    return False

print("="*60)
print("Gem Voice to VMagicMirror Bridge")
print("="*60)
print("\nListening for commands:")
for motion in MOTION_MAP.keys():
    print(f"  - 'Gem {motion}'")
print("\nPress Ctrl+C to stop\n")

# Test
print("Testing hotkey (Ctrl+Alt+1)...")
if send_ctrl_alt('1'):
    print("✓ Test successful!")
else:
    print("✗ Test failed - run as Administrator")

print("\nBridge ready! Waiting for voice commands...\n")

# Listen to keyboard (you'd integrate this with your voice system)
# For now, just monitor for manual testing
def on_message(event):
    if event.event_type == 'down':
        # In real use, this would come from your voice recognition
        # For testing, you can simulate by typing
        pass

keyboard.hook(on_message)

try:
    while True:
        # In production, this would receive from your voice system
        # Example integration:
        # message = await voice_system.get_last_message()
        # check_and_trigger(message)
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\n\nStopped")
