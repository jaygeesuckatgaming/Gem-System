"""
Needle + MCP - YouTube Test (Stable Version)
Keeps MCP server running throughout the session
"""

import needle
import json
import subprocess
import time
import sys
from threading import Thread

class MCPClient:
    """MCP client that keeps server running"""
    
    def __init__(self):
        self.process = None
        self.running = False
        self.output_queue = []
    
    def start(self):
        """Start MCP server"""
        if self.process is None:
            print("[MCP] Starting chrome-devtools-mcp (visible browser)...")
            try:
                self.process = subprocess.Popen(
                    ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=0,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                self.running = True
                
                # Start stderr reader thread (prevents blocking)
                Thread(target=self._read_stderr, daemon=True).start()
                
                # Wait for server initialization
                time.sleep(5)
                print("[MCP] Server started!")
            except Exception as e:
                print(f"[MCP] Failed to start: {e}")
                self.running = False
    
    def _read_stderr(self):
        """Read stderr in background to prevent blocking"""
        while self.running and self.process:
            try:
                line = self.process.stderr.readline()
                if line:
                    print(f"[MCP stderr] {line.strip()}")
            except:
                break
    
    def call_tool(self, tool_name: str, **params):
        """Call MCP tool"""
        if not self.running or not self.process:
            self.start()
        
        if not self.running:
            return {"error": "MCP not running"}
        
        # JSON-RPC 2.0 request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": params
            }
        }
        
        try:
            # Send request
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            # Read response with timeout
            self.process.stdout.flush()
            start = time.time()
            while time.time() - start < 30:  # 30 second timeout
                line = self.process.stdout.readline()
                if line:
                    try:
                        response = json.loads(line.strip())
                        return response.get("result", {})
                    except:
                        continue
            
            return {"error": "Timeout waiting for response"}
        except Exception as e:
            return {"error": str(e)}
    
    def stop(self):
        """Stop MCP server"""
        self.running = False
        if self.process:
            try:
                self.process.terminate()
            except:
                pass


# Global client
mcp = MCPClient()


def mcp_call(tool: str, **kwargs):
    """Helper to call MCP tools"""
    return mcp.call_tool(tool, **kwargs)


@needle.tool
def browser_navigate(url: str):
    """Navigate browser to any URL like youtube.com, google.com
    Args:
        url: Complete URL with https://
    """
    print(f"[NAVIGATE] {url}")
    return mcp_call("navigate_page", url=url, type="url")


@needle.tool
def browser_fill(uid: str, value: str):
    """Type text into input field
    Args:
        uid: Element UID
        value: Text to type
    """
    print(f"[FILL] {uid} = {value}")
    return mcp_call("fill", uid=uid, value=value)


@needle.tool
def browser_click(uid: str):
    """Click element
    Args:
        uid: Element UID
    """
    print(f"[CLICK] {uid}")
    return mcp_call("click", uid=uid)


@needle.tool
def browser_snapshot():
    """Get page snapshot with all elements"""
    print(f"[SNAPSHOT]")
    return mcp_call("take_snapshot", verbose=False)


@needle.tool
def browser_screenshot():
    """Take screenshot"""
    print(f"[SCREENSHOT]")
    return mcp_call("take_screenshot", format="png")


if __name__ == "__main__":
    print("="*70)
    print("Needle + MCP - YouTube (Stable)")
    print("="*70)
    
    # Start MCP
    mcp.start()
    time.sleep(2)
    
    print("\nInitializing agent...")
    agent = needle.Needle(tools=[
        browser_navigate,
        browser_fill,
        browser_click,
        browser_snapshot,
        browser_screenshot,
    ])
    print("✓ Ready\n")
    
    # Execute multi-step task
    print("="*70)
    print("TASK: YouTube → Search 'capio78' → Open channel")
    print("="*70)
    
    try:
        # Step 1: Go to YouTube
        print("\n[1/4] Opening YouTube...")
        agent.reset()
        resp = agent.complete("Navigate to https://www.youtube.com")
        
        if resp.get("function_calls"):
            for call in resp["function_calls"]:
                if call["name"] == "browser_navigate":
                    result = browser_navigate(**call["arguments"])
                    print(f"    → {str(result)[:100]}")
        
        time.sleep(5)  # Wait for page load
        
        # Step 2: Get snapshot
        print("\n[2/4] Getting page elements...")
        resp = agent.complete("Get a snapshot of the page to see available elements")
        
        if resp.get("function_calls"):
            for call in resp["function_calls"]:
                if call["name"] == "browser_snapshot":
                    snapshot = browser_snapshot()
                    content = str(snapshot.get("content", []))[:500]
                    print(f"    → Found elements")
        
        time.sleep(2)
        
        # Step 3: Search
        print("\n[3/4] Searching for 'capio78'...")
        resp = agent.complete("Type 'capio78' in the YouTube search box and press enter")
        
        if resp.get("function_calls"):
            for call in resp["function_calls"]:
                tool = call["name"]
                args = call["arguments"]
                if tool == "browser_fill":
                    browser_fill(**args)
                elif tool == "browser_click":
                    browser_click(**args)
        
        time.sleep(5)  # Wait for search results
        
        # Step 4: Click channel
        print("\n[4/4] Opening capio78 channel...")
        resp = agent.complete("Click on the capio78 channel from the search results")
        
        if resp.get("function_calls"):
            for call in resp["function_calls"]:
                if call["name"] == "browser_click":
                    result = browser_click(**call["arguments"])
                    print(f"    → Clicked")
        
        time.sleep(3)
        
        # Verify
        print("\n[DONE] Check browser - should be on capio78 channel!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nStopping MCP...")
        mcp.stop()
        print("Done!")
