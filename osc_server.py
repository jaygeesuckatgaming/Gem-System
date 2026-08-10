from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

def osc_handler(address, *args):
    print(f"OSC RECEIVED: Address={address}, Args={args}")

dispatcher = Dispatcher()
dispatcher.map("/*", osc_handler)

print("OSC Server listening on 127.0.0.1:10000")
print("Press Ctrl+C to stop")

with BlockingOSCUDPServer(("127.0.0.1", 10000), dispatcher) as server:
    server.serve_forever()
