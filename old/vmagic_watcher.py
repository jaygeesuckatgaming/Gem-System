"""
VMagicMirror Watcher - Monitors MCP chat and triggers motions
Runs alongside MCP, no MCP changes needed!
"""
import keyboard
import time
import os
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

def send_hotkey(key):
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

def check_message(msg):
    """Check if message contains Gem motion command"""
    msg_lower = msg.lower()
    
    for motion, key in MOTION_MAP.items():
        if f'gem {motion}' in msg_lower:
            print(f"\n[VMagic] Detected: 'Gem {motion}'")
            if send_hotkey(key):
                print(f"[VMagic] Sent Ctrl+Alt+{key}")
            return True
    
    return False

print("="*60)
print("VMagicMirror Watcher")
print("="*60)
print("\nMonitoring for commands like:")
for motion in MOTION_MAP.keys():
    print(f"  - Gem {motion}")
print("\nPress Ctrl+C to stop\n")

# Simple test
print("Testing hotkey...")
if send_hotkey('1'):
    print("Test successful! VMagicMirror should have received Ctrl+Alt+1")
else:
    print("Test failed - check permissions")

print("\nWatcher ready!")

# In a real implementation, this would monitor:
# - MCP console output
# - A log file
# - Or intercept chat messages

try:
    while True:
        # For now, just keep running
        # Later we can add file monitoring or pipe interception
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopped")
