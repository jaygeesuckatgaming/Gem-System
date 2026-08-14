"""
Needle + Chrome DevTools MCP - Direct Integration
Uses MCP protocol to communicate with chrome-devtools-mcp server
"""

import needle
import subprocess
import json
import sys

# MCP subprocess handle
mcp_process = None

def start_mcp():
    """Start chrome-devtools-mcp server as subprocess"""
    global mcp_process
    if mcp_process is None:
        print("[MCP] Starting chrome-devtools-mcp server...")
        # Use cmd.exe to run npx (Windows compatibility)
        mcp_process = subprocess.Popen(
            ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest", "--headless", "--isolated"],
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
    """Open a website or web page by navigating the browser to any URL. Use this to visit websites like google.com, github.com, etc.
    
    Args:
        url: Complete URL including https:// (e.g., "https://google.com", "https://github.com")
    """
    print(f"[BROWSER] Navigating to: {url}")
    result = call_mcp_tool("navigate_page", url=url, type="url")
    return result


@needle.tool
def browser_click(uid: str):
    """Click an element by its UID.
    
    Args:
        uid: Element UID from snapshot
    """
    print(f"[BROWSER] Clicking element: {uid}")
    result = call_mcp_tool("click", uid=uid)
    return result


@needle.tool
def browser_fill(uid: str, value: str):
    """Fill text into an input field.
    
    Args:
        uid: Element UID
        value: Text to type
    """
    print(f"[BROWSER] Filling {uid} with: {value}")
    result = call_mcp_tool("fill", uid=uid, value=value)
    return result


@needle.tool
def browser_screenshot():
    """Take a screenshot of the current page."""
    print("[BROWSER] Taking screenshot...")
    result = call_mcp_tool("take_screenshot", format="png")
    return result


@needle.tool
def browser_snapshot():
    """Get a list of all clickable elements, buttons, links, and text on the current page. Returns the page structure with element UIDs. Use this to see what's on the page."""
    print("[BROWSER] Getting page snapshot...")
    result = call_mcp_tool("take_snapshot", verbose=False)
    return result


@needle.tool
def get_page_content():
    """Get all text content and element descriptions from the current page. Returns visible text, links, buttons. Use this to read what's on the page."""
    print("[BROWSER] Getting page content...")
    # Get snapshot which contains all text and elements
    result = call_mcp_tool("take_snapshot", verbose=True)
    return result


@needle.tool
def browser_evaluate(function: str):
    """Execute JavaScript in the browser.
    
    Args:
        function: JavaScript function as string
    """
    print(f"[BROWSER] Evaluating: {function[:50]}...")
    result = call_mcp_tool("evaluate_script", function=function)
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("Needle + Chrome DevTools MCP - Direct Integration")
    print("=" * 70)
    
    print("\nInitializing agent with MCP browser tools...")
    agent = needle.Needle(
        tools=[
            browser_navigate,
            browser_click,
            browser_fill,
            browser_screenshot,
            browser_snapshot,
            get_page_content,
            browser_evaluate,
        ]
    )
    print("✓ Agent initialized\n")
    
    # Test queries
    test_queries = [
        "Open Google homepage",
        "Take a screenshot",
        "What's on this page?",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}: {query}")
        print(f"{'='*70}")
        
        try:
            agent.reset()
            response = agent.complete(query)
            
            print(f"\nType: {response['type']}")
            print(f"Confidence: {response['confidence']:.4f}")
            
            if response.get("function_calls"):
                for call in response["function_calls"]:
                    tool_name = call["name"]
                    args = call["arguments"]
                    
                    print(f"\n→ Calling: {tool_name}({json.dumps(args)})")
                    
                    # Execute via MCP
                    if tool_name == "browser_navigate":
                        result = browser_navigate(**args)
                    elif tool_name == "browser_click":
                        result = browser_click(**args)
                    elif tool_name == "browser_fill":
                        result = browser_fill(**args)
                    elif tool_name == "browser_screenshot":
                        result = browser_screenshot()
                    elif tool_name == "browser_snapshot":
                        result = browser_snapshot()
                    elif tool_name == "get_page_content":
                        result = get_page_content()
                    elif tool_name == "browser_evaluate":
                        result = browser_evaluate(**args)
                    else:
                        result = {"error": f"Unknown: {tool_name}"}
                    
                    print(f"← Result: {json.dumps(result, indent=2)[:500]}")
            else:
                print(f"Reasoning: {response.get('reasoning', 'N/A')}")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("Tests complete!")
    if mcp_process:
        print("Stopping MCP server...")
        mcp_process.terminate()
    print(f"{'='*70}\n")
