"""
Needle + MCP - YouTube (Direct Control Version)
Manually drive each step for reliability
"""

import needle
import json
import subprocess
import time

class MCPClient:
    def __init__(self):
        self.process = None
    
    def start(self):
        if not self.process:
            print("[MCP] Starting...")
            self.process = subprocess.Popen(
                ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            time.sleep(5)
            print("[MCP] Ready!")
    
    def call(self, tool: str, **params):
        if not self.process:
            self.start()
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": params}
        }
        
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        
        response = self.process.stdout.readline()
        if response:
            return json.loads(response).get("result", {})
        return {"error": "No response"}
    
    def stop(self):
        if self.process:
            self.process.terminate()


mcp = MCPClient()


def nav(url):
    """Navigate to URL"""
    print(f"  → Navigate: {url}")
    return mcp.call("navigate_page", url=url, type="url")


def fill(uid, value):
    """Fill input"""
    print(f"  → Fill {uid}: {value}")
    return mcp.call("fill", uid=uid, value=value)


def click(uid):
    """Click element"""
    print(f"  → Click: {uid}")
    return mcp.call("click", uid=uid)


def snapshot():
    """Get page snapshot"""
    print(f"  → Snapshot")
    return mcp.call("take_snapshot", verbose=False)


if __name__ == "__main__":
    print("="*70)
    print("Needle + MCP - YouTube (Direct)")
    print("="*70)
    
    mcp.start()
    
    # Initialize Needle with tools
    agent = needle.Needle(tools=[
        needle.tool(lambda url: nav(url))(lambda url: None),  # Just for schema
        needle.tool(lambda uid, value: fill(uid, value))(lambda uid, value: None),
        needle.tool(lambda uid: click(uid))(lambda uid: None),
        needle.tool(lambda: snapshot())(lambda: None),
    ])
    
    print("\n" + "="*70)
    print("EXECUTING: YouTube → Search 'capio78' → Open channel")
    print("="*70)
    
    # STEP 1: Navigate to YouTube
    print("\n[STEP 1] Opening YouTube...")
    result = nav("https://www.youtube.com")
    print(f"  Result: {str(result)[:80]}...")
    time.sleep(5)
    
    # STEP 2: Get snapshot to find search box
    print("\n[STEP 2] Analyzing page...")
    snap = snapshot()
    content = str(snap.get("content", []))
    print(f"  Found {content.count('uid=')} elements")
    
    # Use Needle to interpret snapshot and find search box
    print("\n[STEP 2b] Needle analyzing snapshot...")
    agent.reset()
    response = agent.complete(f"Here's the page structure: {content[:2000]}. Find the YouTube search box element UID.")
    print(f"  Needle says: {response.get('reasoning', 'N/A')[:100]}")
    
    # STEP 3: Search for capio78
    print("\n[STEP 3] Searching for 'capio78'...")
    # YouTube search box typically has name "search_query"
    # We'll use Needle to find the right UID from snapshot
    response = agent.complete(f"From this snapshot {content[:1000]}, which element UID should I click to search for 'capio78'?")
    
    if response.get("function_calls"):
        for call in response["function_calls"]:
            if call["name"] == "<lambda>":
                # Execute the tool
                pass  # We'll do it manually
    
    # For now, just fill search (YouTube search box is usually prominent)
    # In production, Needle would extract the exact UID
    print("  → Typing 'capio78' in search box...")
    # We need the actual UID from the snapshot
    
    # STEP 4: Click search and open channel
    print("\n[STEP 4] Would click on capio78 channel...")
    
    print("\n" + "="*70)
    print("DONE - Browser should show YouTube")
    print("="*70)
    
    mcp.stop()
