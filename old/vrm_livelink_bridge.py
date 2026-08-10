"""LiveLink to VRM Bridge"""
import socket
import struct
import json
import threading
import websockets
import asyncio

ws_clients = set()

def udp_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', 11111))
    print("[Bridge] UDP listening on port 11111")
    
    while True:
        data, addr = sock.recvfrom(65535)
        if len(data) >= 228:
            try:
                blendshapes = [struct.unpack('f', data[i:i+4])[0] for i in range(24, 228, 4)]
                expr = {}
                if blendshapes[0] > 0.01: expr['aa'] = blendshapes[0]
                if blendshapes[4] > 0.01: expr['blinkL'] = blendshapes[4]
                if blendshapes[5] > 0.01: expr['blinkR'] = blendshapes[5]
                
                if expr and ws_clients:
                    msg = json.dumps({"expressions": expr})
                    print(f"[Bridge] Sending: {expr}")
                    for client in list(ws_clients):
                        try:
                            client.send(msg)
                        except:
                            ws_clients.discard(client)
            except Exception as e:
                print(f"[Bridge] Error: {e}")

async def ws_handler(ws, path):
    ws_clients.add(ws)
    print("[Bridge] VRM viewer connected")
    try:
        await ws.send(json.dumps({"type": "connected"}))
        async for _ in ws: pass
    except:
        print("[Bridge] VRM viewer disconnected")
    finally:
        ws_clients.discard(ws)

print("="*60)
print("LiveLink to VRM Bridge")
print("="*60)

threading.Thread(target=udp_server, daemon=True).start()
print("[Bridge] Forwarding to ws://localhost:8765")
print("[Bridge] Ready!")

start_server = websockets.serve(ws_handler, "localhost", 8765)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
