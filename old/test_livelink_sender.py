"""
Test LiveLink Sender - Simulates watcher_to_face sending blendshapes
"""
import socket
import struct
import time
import math

def create_livelink_frame(blendshapes):
    """Create binary LiveLink frame"""
    # Header (24 bytes) + 51 floats
    header = b'\x00' * 24
    data = header
    
    # 51 blendshape values (floats)
    for i in range(51):
        value = blendshapes.get(i, 0.0)
        data += struct.pack('f', value)
    
    return data

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server = ("127.0.0.1", 11111)

print("Sending test LiveLink data to bridge...")
print("Watch the VRM viewer!")

frame = 0
while True:
    frame += 1
    
    # Create animated blendshapes
    t = time.time()
    blendshapes = {
        0: abs(math.sin(t * 2)),  # Jaw open/close
        4: 1.0 if int(t * 3) % 2 == 0 else 0.0,  # Blink left
        5: 1.0 if int(t * 3) % 2 == 0 else 0.0,  # Blink right
    }
    
    data = create_livelink_frame(blendshapes)
    sock.sendto(data, server)
    
    if frame % 30 == 0:
        print(f"Sent {frame} frames - jaw={blendshapes[0]:.2f}, blink={blendshapes[4]:.1f}")
    
    time.sleep(0.033)  # 30 FPS
