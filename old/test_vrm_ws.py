import asyncio
import websockets
import json

async def test():
    print("Load VRM, then press Enter...")
    input()
    
    async with websockets.connect("ws://localhost:8765") as ws:
        print("Sending lookAt test...")
        
        # Look left to right
        for i in range(10):
            yaw = (i / 5.0) - 1.0  # -1 to 1
            await ws.send(json.dumps({
                "lookAt": {"yaw": yaw, "pitch": 0}
            }))
            print(f"  Yaw: {yaw:.2f}")
            await asyncio.sleep(0.3)
        
        # Look up and down
        for i in range(10):
            pitch = (i / 5.0) - 1.0
            await ws.send(json.dumps({
                "lookAt": {"yaw": 0, "pitch": pitch}
            }))
            print(f"  Pitch: {pitch:.2f}")
            await asyncio.sleep(0.3)
        
        print("Done! Did the model's eyes/head move?")

asyncio.run(test())
