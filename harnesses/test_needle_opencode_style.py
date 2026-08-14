"""
Needle + Chrome DevTools MCP - Like OpenCode
Properly connects to MCP and shows browser window
"""

import needle
import json
import sys
from typing import Optional, Dict, Any
import subprocess

class MCPClient:
    """Proper MCP client that connects to chrome-devtools-mcp"""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.connected = False
    
    def connect(self):
        """Start MCP server and connect"""
        if self.process is None:
            print("[MCP] Starting chrome-devtools-mcp (visible browser)...")
            self.process = subprocess.Popen(
                ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            # Wait for server to start
            import time
            time.sleep(3)
            self.connected = True
            print("[MCP] Connected!")
    
    def call_tool(self, tool_name: str, **params) -> Dict[str, Any]:
        """Call an MCP tool"""
        if not self.connected:
            self.connect()
        
        # MCP uses JSON-RPC 2.0
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
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            response_line = self.process.stdout.readline()
            if response_line:
                response = json.loads(response_line)
                return response.get("result", {})
        except Exception as e:
            return {"error": str(e)}
        
        return {"error": "No response"}
    
    def close(self):
        """Close MCP connection"""
        if self.process:
            self.process.terminate()
            self.connected = False


# Global MCP client
mcp = MCPClient()


def call_mcp(tool_name: str, **params):
    """Helper to call MCP tools"""
    return mcp.call_tool(tool_name, **params)


@needle.tool
def browser_navigate(url: str):
    """Navigate browser to any website URL like youtube.com, google.com, etc.
    
    Args:
        url: Complete URL with https:// (e.g., "https://youtube.com")
    """
    print(f"[BROWSER] Navigate to: {url}")
    result = call_mcp("navigate_page", url=url, type="url")
    return result


@needle.tool
def browser_fill(uid: str, value: str):
    """Type text into input fields, search boxes, forms.
    
    Args:
        uid: Element UID from snapshot (e.g., "1_20")
        value: Text to type
    """
    print(f"[BROWSER] Fill {uid} with: {value}")
    result = call_mcp("fill", uid=uid, value=value)
    return result


@needle.tool
def browser_click(uid: str):
    """Click buttons, links, or any clickable element.
    
    Args:
        uid: Element UID from snapshot
    """
    print(f"[BROWSER] Click: {uid}")
    result = call_mcp("click", uid=uid)
    return result


@needle.tool
def browser_snapshot():
    """Get page snapshot showing all elements, buttons, links with their UIDs."""
    print("[BROWSER] Get snapshot...")
    result = call_mcp("take_snapshot", verbose=False)
    return result


@needle.tool
def browser_screenshot():
    """Take screenshot of current page."""
    print("[BROWSER] Screenshot...")
    result = call_mcp("take_screenshot", format="png")
    return result


@needle.tool
def browser_wait_for(text: str, timeout: int = 10000):
    """Wait for text to appear on page.
    
    Args:
        text: Text to wait for
        timeout: Max wait time in milliseconds
    """
    print(f"[BROWSER] Wait for: {text}")
    result = call_mcp("wait_for", text=[text], timeout=timeout)
    return result


@needle.tool
def browser_evaluate(function: str):
    """Execute JavaScript code in browser.
    
    Args:
        function: JavaScript code as string
    """
    print(f"[BROWSER] Evaluate JS...")
    result = call_mcp("evaluate_script", function=function)
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("Needle + MCP - YouTube Test (Like OpenCode)")
    print("=" * 70)
    
    print("\nInitializing agent with browser tools...")
    agent = needle.Needle(
        tools=[
            browser_navigate,
            browser_fill,
            browser_click,
            browser_snapshot,
            browser_screenshot,
            browser_wait_for,
            browser_evaluate,
        ]
    )
    print("✓ Agent initialized\n")
    
    # Multi-step YouTube task
    print("=" * 70)
    print("TASK: Go to YouTube and open channel 'capio78'")
    print("=" * 70)
    
    try:
        # Step 1: Navigate to YouTube
        print("\n[STEP 1] Opening YouTube...")
        agent.reset()
        response = agent.complete("Open YouTube.com in the browser")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                if call["name"] == "browser_navigate":
                    result = browser_navigate(**call["arguments"])
                    print(f"Result: {str(result)[:200]}")
        
        # Wait for page to load
        import time
        time.sleep(3)
        
        # Step 2: Get snapshot to find search box
        print("\n[STEP 2] Finding search box...")
        response = agent.complete("Get the page snapshot to see what elements are available")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                if call["name"] == "browser_snapshot":
                    snapshot = browser_snapshot()
                    content = str(snapshot.get("content", []))
                    print(f"Snapshot: {content[:500]}...")
        
        # Step 3: Search for capio78
        print("\n[STEP 3] Searching for 'capio78'...")
        response = agent.complete("Search for 'capio78' in the YouTube search box")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                tool = call["name"]
                args = call["arguments"]
                
                if tool == "browser_fill":
                    result = browser_fill(**args)
                    print(f"Filled search box")
                elif tool == "browser_click":
                    result = browser_click(**args)
                    print(f"Clicked search button")
        
        time.sleep(3)
        
        # Step 4: Click on capio78 channel
        print("\n[STEP 4] Opening capio78 channel...")
        response = agent.complete("Click on the capio78 channel from search results")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                if call["name"] == "browser_click":
                    result = browser_click(**call["arguments"])
                    print(f"Clicked channel")
        
        time.sleep(2)
        
        # Step 5: Verify
        print("\n[STEP 5] Verifying we're on the channel...")
        response = agent.complete("What page is this? What channel name do you see?")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                if call["name"] == "browser_snapshot":
                    result = browser_snapshot()
                    content = str(result.get("content", []))
                    if "capio78" in content.lower():
                        print("✓ SUCCESS: On capio78 channel!")
                    else:
                        print("? Checking page content...")
        
        print("\n" + "=" * 70)
        print("TASK COMPLETE - Check your browser window!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nClosing MCP connection...")
        mcp.close()
