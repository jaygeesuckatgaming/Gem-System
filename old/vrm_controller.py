"""VRM Controller - WebSocket server for VRM animation"""
import asyncio,websockets,json,time

class VRMController:
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
    
    async def handler(self, websocket):
        self.clients.add(websocket)
        print(f"[VRM] Client connected")
        try:
            await websocket.send(json.dumps({"type": "connected"}))
            async for msg in websocket:
                pass
        except:
            print("[VRM] Client disconnected")
        finally:
            self.clients.discard(websocket)
    
    async def send(self, data):
        if self.clients:
            await asyncio.gather(*[c.send(json.dumps(data)) for c in self.clients], return_exceptions=True)
    
    def expressions(self, **kwargs):
        return {"expressions": kwargs, "time": time.time()}
    
    def look(self, yaw=0, pitch=0):
        return {"lookAt": {"yaw": yaw, "pitch": pitch}, "time": time.time()}
    
    async def run(self):
        print(f"[VRM] Server started on ws://{self.host}:{self.port}")
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()

async def test():
    ctrl = VRMController()
    task = asyncio.create_task(ctrl.run())
    await asyncio.sleep(2)
    print("[VRM] Testing blink...")
    await ctrl.send(ctrl.expressions(blinkL=1.0, blinkR=1.0))
    await asyncio.sleep(1)
    await ctrl.send(ctrl.expressions(blinkL=0.0, blinkR=0.0))
    print("[VRM] Testing lookat...")
    for i in range(20):
        await ctrl.send(ctrl.look(yaw=(i/10)-1, pitch=0))
        await asyncio.sleep(0.1)
    print("[VRM] Done - press Ctrl+C to exit")
    try:
        await task
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    asyncio.run(test())
