"""
Send Ctrl+Alt+1 (or any hotkey) repeatedly
"""
import keyboard
import time

print("="*60)
print("Hotkey Sender")
print("="*60)
print("\nThis will send: Ctrl+Alt+1")
print("\nOptions:")
print("  1. Send once")
print("  2. Send 10 times (1 second apart)")
print("  3. Send continuously (press Ctrl+C to stop)")
print("  4. Send when you press a specific key")
print("\nPress Ctrl+C anytime to exit")
print("="*60)

choice = input("\nChoose (1-4): ").strip()

def send_hotkey():
    keyboard.press('ctrl')
    keyboard.press('alt')
    keyboard.press('1')
    time.sleep(0.05)
    keyboard.release('1')
    keyboard.release('alt')
    keyboard.release('ctrl')

if choice == '1':
    send_hotkey()
    print("Sent once!")

elif choice == '2':
    print("Sending 10 times...")
    for i in range(10):
        send_hotkey()
        print(f"  {i+1}/10")
        time.sleep(1)
    print("Done!")

elif choice == '3':
    print("Sending continuously... (Ctrl+C to stop)")
    try:
        count = 0
        while True:
            send_hotkey()
            count += 1
            print(f"Sent: {count}")
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\nStopped after {count} times")

elif choice == '4':
    trigger = input("What key should trigger it? (e.g., space, f1, z): ").strip().lower()
    print(f"Press '{trigger}' to send Ctrl+Alt+1")
    
    def on_press(event):
        if event.name.lower() == trigger:
            send_hotkey()
            print("Sent!")
    
    keyboard.on_press(on_press)
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped")

else:
    print("Invalid choice")
