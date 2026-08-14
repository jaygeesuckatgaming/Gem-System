"""
Sends Ctrl+Alt+1 keyboard shortcut
"""
import keyboard
import time

print("Sending Ctrl+Alt+1...")

# Press Ctrl + Alt + 1
keyboard.press('ctrl')
keyboard.press('alt')
keyboard.press('1')

# Hold for a moment
time.sleep(0.1)

# Release all
keyboard.release('1')
keyboard.release('alt')
keyboard.release('ctrl')

print("Sent!")
