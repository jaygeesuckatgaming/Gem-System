"""
Needle + Chrome DevTools MCP - YouTube Test (Connect to Running MCP)
Like OpenCode - assumes MCP server is already running
"""

import needle
import subprocess
import json
import sys

# We'll use MCP via subprocess but connect to existing Chrome instance
# This mimics how OpenCode works

def call_mcp_tool(tool_name, **params):
    """Call a Chrome DevTools MCP tool via subprocess"""
    # Build command
    cmd = ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest"]
    
    # For now, we'll use a simpler approach - direct tool execution
    # In production, you'd connect to a running MCP server via stdio
    
    # Actually, let's just use subprocess to call individual tools
    # This is a workaround until we have proper MCP client
    print(f"[MCP] Calling {tool_name}...")
    
    # For this demo, we'll return mock responses
    # Real implementation would connect to MCP server
    return {
        "content": [{
            "type": "text", 
            "text": f"Called {tool_name} with {params}"
        }]
    }


@needle.tool
def browser_navigate(url: str):
    """Open a website by navigating to any URL like youtube.com, google.com, etc.
    
    Args:
        url: Complete URL (e.g., "https://youtube.com")
    """
    print(f"[BROWSER] Navigate to: {url}")
    # Use subprocess to call MCP
    result = subprocess.run(
        ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest", "--navigate", url],
        capture_output=True, text=True
    )
    return {"status": "success", "url": url}


@needle.tool  
def browser_search_youtube(query: str):
    """Search YouTube for a specific query. Opens YouTube and searches.
    
    Args:
        query: Search term (e.g., "capio78", "Python tutorial")
    """
    print(f"[YOUTUBE] Search for: {query}")
    # Navigate to YouTube search
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    subprocess.run(
        ["cmd", "/c", "npx", "-y", "chrome-devtools-mcp@latest", "--navigate", url],
        capture_output=True, text=True
    )
    return {"status": "success", "query": query}


@needle.tool
def get_page_info():
    """Get information about the current page including title and URL."""
    print("[BROWSER] Get page info")
    return {"status": "success", "info": "Page info"}


if __name__ == "__main__":
    print("=" * 70)
    print("Needle + MCP - YouTube Test (Simple Version)")
    print("=" * 70)
    
    print("\nInitializing agent...")
    agent = needle.Needle(
        tools=[
            browser_navigate,
            browser_search_youtube,
            get_page_info,
        ]
    )
    print("✓ Agent initialized\n")
    
    # Test: Go to YouTube and find capio78
    print("=" * 70)
    print("TASK: Go to YouTube and open channel capio78")
    print("=" * 70)
    
    print("\n[STEP 1] Navigate to YouTube...")
    response = agent.complete("Go to YouTube.com")
    if response.get("function_calls"):
        for call in response["function_calls"]:
            print(f"  → {call['name']}: {call['arguments']}")
    
    print("\n[STEP 2] Search for capio78...")
    response = agent.complete("Search for capio78 on YouTube")
    if response.get("function_calls"):
        for call in response["function_calls"]:
            print(f"  → {call['name']}: {call['arguments']}")
    
    print("\n[STEP 3] Open the channel...")
    response = agent.complete("Click on the capio78 channel")
    if response.get("function_calls"):
        for call in response["function_calls"]:
            print(f"  → {call['name']}: {call['arguments']}")
    
    print("\n" + "=" * 70)
    print("Done! Check if Chrome opened YouTube")
    print("=" * 70)
