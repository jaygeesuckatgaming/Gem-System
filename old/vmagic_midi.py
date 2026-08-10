"""
VMagicMirror MIDI Controller
Sends MIDI notes to trigger motions in VMagicMirror
"""
import mido
import time
import threading

# VMagicMirror motion mapping (customize these!)
MOTIONS = {
    'a': 60,   # Middle C - Motion 1
    's': 62,   # D - Motion 2
    'd': 64,   # E - Motion 3
    'f': 65,   # F - Motion 4
    'g': 67,   # G - Motion 5
    'h': 69,   # A - Motion 6
    'j': 71,   # B - Motion 7
    'k': 72,   # High C - Motion 8
}

print("="*60)
print("VMagicMirror MIDI Controller")
print("="*60)

# List all MIDI ports
ports = mido.get_output_names()
print(f"\nAvailable MIDI output ports ({len(ports)}):")
for i, port_name in enumerate(ports):
    print(f"  [{i+1}] {port_name}")

if not ports:
    print("\nNo MIDI ports found!")
    print("Install loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html")
    input("\nPress Enter to exit...")
    exit()

# Ask which port to use
print("\nVMagicMirror should be listening on one of these ports.")
print("If you created a loopMIDI port, select that one.")
choice = input(f"\nChoose port (1-{len(ports)}, or Enter for first): ").strip()

if choice:
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(ports):
            selected_port = ports[idx]
        else:
            print("Invalid choice, using first port")
            selected_port = ports[0]
    except:
        print("Invalid input, using first port")
        selected_port = ports[0]
else:
    selected_port = ports[0]

# Open the port
port = mido.open_output(selected_port)
print(f"\n✓ CONNECTED TO: {selected_port}")
print(f"  Port handle: {port}")

print("\n" + "="*60)
print("Controls:")
print("="*60)
for key, note in MOTIONS.items():
    print(f"  Press '{key.upper()}' -> Note {note}")
print("\nPress Ctrl+C to exit")
print("="*60)

# Simple keyboard input (no external module needed)
import msvcrt

print("\nReady! Press keys to trigger motions...\n")

try:
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('ascii').lower()
            
            if key in MOTIONS:
                note = MOTIONS[key]
                
                # Send Note ON
                port.send(mido.Message('note_on', note=note, velocity=64))
                print(f"► Note ON:  {note} (key: {key.upper()})")
                
                # Send Note OFF after short delay
                time.sleep(0.1)
                port.send(mido.Message('note_off', note=note, velocity=0))
                print(f"◄ Note OFF: {note}")
            
            elif key == 'q':
                print("\nQuitting...")
                break
                
except KeyboardInterrupt:
    print("\n\nInterrupted!")
finally:
    port.close()
    print("MIDI port closed.")
