"""Simple MIDI Note Sender for Windows"""
import mido
import time

print("Available MIDI ports:")
ports = mido.get_output_names()
for i, port in enumerate(ports):
    print(f"  {i+1}. {port}")

if not ports:
    print("No MIDI ports found!")
    print("Install a virtual MIDI cable like loopMIDI:")
    print("https://www.tobias-erichsen.de/software/loopmidi.html")
    exit()

choice = input(f"\nChoose port (1-{len(ports)}) or Enter for first: ").strip()
idx = int(choice) - 1 if choice else 0
port = mido.open_output(ports[idx])
print(f"Connected to: {ports[idx]}")

print("\nSending test notes (Ctrl+C to stop)...")
try:
    for note in range(60, 72):  # One octave
        port.send(mido.Message('note_on', note=note, velocity=64))
        print(f"Note ON: {note}")
        time.sleep(0.3)
        port.send(mido.Message('note_off', note=note, velocity=0))
        print(f"Note OFF: {note}")
        time.sleep(0.2)
    print("Done!")
except KeyboardInterrupt:
    print("\nStopped")
finally:
    port.close()
