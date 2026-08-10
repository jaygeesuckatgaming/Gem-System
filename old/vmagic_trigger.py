"""
VMagicMirror Trigger for MCP
Call this from MCP to trigger motions
Usage: python vmagic_trigger.py wave
"""
import sys
import keyboard
import time

motion_map = {
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

if len(sys.argv) < 2:
    print("Usage: python vmagic_trigger.py <motion>")
    print("Motions: wave, dance, bow, jump, spin, clap, laugh, cry, sleep")
    sys.exit(1)

motion = sys.argv[1].lower()
if motion not in motion_map:
    print(f"Unknown motion: {motion}")
    sys.exit(1)

key = motion_map[motion]
print(f"Sending Ctrl+Alt+{key} for '{motion}'")

try:
    keyboard.press('ctrl')
    keyboard.press('alt')
    keyboard.press(key)
    time.sleep(0.05)
    keyboard.release(key)
    keyboard.release('alt')
    keyboard.release('ctrl')
    print("Sent!")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
