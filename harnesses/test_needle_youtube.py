"""
Needle + Chrome DevTools MCP - YouTube Test
Navigate to YouTube and open a specific channel
"""

import needle
import subprocess
import json

# MCP subprocess handle
mcp_process = None

def start_mcp():
    """Start chrome-devtools-mcp server as subprocess"""
    global mcp_process
    if mcp_process is None:
        print("[MCP] Starting chrome-devtools-mcp server...")
        mcp_process = subprocess.Popen(
            ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        print("[MCP] Server started")
    return mcp_process


def call_mcp_tool(tool_name, **params):
    """Call a Chrome DevTools MCP tool via stdio"""
    proc = start_mcp()
    
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
    
    # Send request
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    
    # Read response
    response_line = proc.stdout.readline()
    if response_line:
        response = json.loads(response_line)
        return response.get("result", {})
    return {"error": "No response"}


@needle.tool
def browser_navigate(url: str):
    """Open a website or web page by navigating the browser to any URL. Use this to visit websites like google.com, github.com, youtube.com, etc.
    
    Args:
        url: Complete URL including https:// (e.g., "https://google.com", "https://youtube.com")
    """
    print(f"[BROWSER] Navigating to: {url}")
    result = call_mcp_tool("navigate_page", url=url, type="url")
    
    # Wait a bit for page to load
    import time
    time.sleep(2)
    
    # Try to auto-accept any consent popups
    try:
        snapshot = call_mcp_tool("take_snapshot", verbose=False)
        content = str(snapshot.get("content", []))
        
        # Look for consent/cookie buttons
        if "accept" in content.lower() or "cookie" in content.lower() or "consent" in content.lower():
            print("[AUTO] Detected consent popup, finding accept button...")
            # Needle would need to click the accept button here
            # For now, we'll just note it exists
    except:
        pass
    
    return result


@needle.tool
def browser_fill(uid: str, value: str):
    """Type text into an input field like search boxes, forms, etc.
    
    Args:
        uid: Element UID from snapshot (e.g., "1_20")
        value: Text to type into the field
    """
    print(f"[BROWSER] Filling element {uid} with: {value}")
    result = call_mcp_tool("fill", uid=uid, value=value)
    return result


@needle.tool
def browser_click(uid: str):
    """Click on a button, link, or any clickable element.
    
    Args:
        uid: Element UID from snapshot (e.g., "1_25")
    """
    print(f"[BROWSER] Clicking element: {uid}")
    result = call_mcp_tool("click", uid=uid)
    return result


@needle.tool
def browser_snapshot():
    """Get a list of all clickable elements, buttons, links, and text on the current page. Returns the page structure with element UIDs. Use this to see what's on the page and find elements to interact with."""
    print("[BROWSER] Getting page snapshot...")
    result = call_mcp_tool("take_snapshot", verbose=False)
    return result


@needle.tool
def get_page_content():
    """Get all text content and element descriptions from the current page. Returns visible text, links, buttons. Use this to read what's on the page."""
    print("[BROWSER] Getting page content...")
    result = call_mcp_tool("take_snapshot", verbose=True)
    return result


@needle.tool
def browser_wait_for(text: str):
    """Wait for specific text to appear on the page (useful for dynamic content loading).
    
    Args:
        text: Text to wait for
    """
    print(f"[BROWSER] Waiting for text: {text}")
    result = call_mcp_tool("wait_for", text=[text], timeout=10000)
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("Needle + Chrome DevTools MCP - YouTube Channel Test")
    print("=" * 70)
    
    print("\nInitializing agent with YouTube automation tools...")
    agent = needle.Needle(
        tools=[
            browser_navigate,
            browser_fill,
            browser_click,
            browser_snapshot,
            get_page_content,
            browser_wait_for,
        ]
    )
    print("✓ Agent initialized\n")
    
    # Multi-step YouTube task
    print("=" * 70)
    print("TASK: Go to YouTube and open channel capio78")
    print("=" * 70)
    
    try:
        # Step 1: Navigate to YouTube
        print("\n[STEP 1] Navigating to YouTube...")
        agent.reset()
        response = agent.complete("Go to YouTube.com")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                if call["name"] == "browser_navigate":
                    result = browser_navigate(**call["arguments"])
                    print(f"Result: {json.dumps(result, indent=2)[:300]}")
        
        # Step 2: Search for the channel
        print("\n[STEP 2] Searching for capio78 channel...")
        response = agent.complete("Search for 'capio78' in the YouTube search box")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                tool_name = call["name"]
                args = call["arguments"]
                
                if tool_name == "browser_snapshot":
                    snapshot = browser_snapshot()
                    print(f"Got snapshot, analyzing elements...")
                    # Parse snapshot to find search box
                    # In real implementation, Needle would extract the UID
                elif tool_name == "browser_fill":
                    result = browser_fill(**args)
                    print(f"Filled search box")
        
        # Step 3: Click on the channel
        print("\n[STEP 3] Opening the capio78 channel...")
        response = agent.complete("Click on the capio78 channel from the search results")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                if call["name"] == "browser_click":
                    result = browser_click(**call["arguments"])
                    print(f"Clicked on channel")
        
        # Step 4: Verify we're on the channel
        print("\n[STEP 4] Verifying channel page...")
        response = agent.complete("What channel is this? Confirm you're on capio78's channel")
        
        if response.get("function_calls"):
            for call in response["function_calls"]:
                if call["name"] == "get_page_content":
                    result = get_page_content()
                    content = str(result.get("content", []))
                    if "capio78" in content.lower():
                        print("✓ SUCCESS: On capio78 channel!")
                    else:
                        print("? Need to verify channel name")
        
        print("\n" + "=" * 70)
        print("TASK COMPLETE!")
        print("=" * 70)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    if mcp_process:
        print("\nStopping MCP server...")
        mcp_process.terminate()
