"""
Needle + Chrome DevTools MCP Integration Test
Tests using Needle to control browser automation via Chrome DevTools MCP
"""

import needle
import subprocess
import json
import time
import requests

# ============================================================================
# Chrome DevTools MCP Tools wrapped for Needle
# ============================================================================

MCP_URL = "http://localhost:9222"  # Chrome DevTools MCP endpoint

# Helper to call MCP tools via HTTP
def call_mcp_tool(tool_name, **params):
    """Call a Chrome DevTools MCP tool via HTTP"""
    try:
        # MCP uses JSON-RPC or REST - adjust based on actual API
        response = requests.post(
            f"{MCP_URL}/{tool_name}",
            json=params,
            timeout=30
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}


@needle.tool
def browser_navigate(url: str):
    """Open a website by navigating the browser to a URL. Use this to visit any webpage, search engine, or online resource.
    
    Args:
        url: The complete URL to navigate to (e.g., "https://google.com", "https://example.com")
    """
    print(f"[BROWSER] Navigating to: {url}")
    result = call_mcp_tool("navigate_page", url=url, type="url")
    return result


@needle.tool
def browser_click(selector: str):
    """Click an element on the page.
    
    Args:
        selector: CSS selector or element UID to click
    """
    print(f"[BROWSER] Clicking: {selector}")
    result = call_mcp_tool("click", uid=selector)
    return result


@needle.tool
def browser_fill(selector: str, value: str):
    """Fill text into an input field.
    
    Args:
        selector: CSS selector or element UID of the input
        value: Text to type into the field
    """
    print(f"[BROWSER] Filling {selector} with: {value}")
    result = call_mcp_tool("fill", uid=selector, value=value)
    return result


@needle.tool
def browser_screenshot():
    """Capture a screenshot of the current browser page. Returns the screenshot image."""
    print("[BROWSER] Taking screenshot...")
    result = call_mcp_tool("take_screenshot", format="png")
    return {"status": "success", "format": result.get("format", "png")}


@needle.tool
def browser_execute_script(code: str):
    """Execute JavaScript code in the browser.
    
    Args:
        code: JavaScript code to execute
    """
    print(f"[BROWSER] Executing script: {code[:50]}...")
    result = call_mcp_tool("evaluate_script", function=code)
    return result


@needle.tool
def browser_wait_for(text: str):
    """Wait for specific text to appear on the page.
    
    Args:
        text: Text to wait for
    """
    print(f"[BROWSER] Waiting for text: {text}")
    result = call_mcp_tool("wait_for", text=[text], timeout=10000)
    return result


# ============================================================================
# Test the integration
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Needle + Chrome DevTools MCP Integration Test")
    print("=" * 70)
    
    # Create the agent with browser tools
    print("\nInitializing Needle agent with browser automation tools...")
    agent = needle.Needle(
        tools=[
            browser_navigate,
            browser_click,
            browser_fill,
            browser_screenshot,
            browser_execute_script,
            browser_wait_for,
        ]
    )
    print("✓ Agent initialized\n")
    
    # Test queries
    test_queries = [
        "Open Google homepage",
        "Search for Python tutorials on Google",
        "Take a screenshot of the current page",
        "Click on the first search result",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}: {query}")
        print(f"{'='*70}")
        
        try:
            # Use manual loop for full control
            agent.reset()
            response = agent.complete(query)
            
            print(f"\nInitial response:")
            print(json.dumps(response, indent=2))
            
            # Execute tool calls
            step = 1
            while response.get("type") == "call" and response.get("function_calls"):
                print(f"\n--- Step {step} ---")
                calls = response["function_calls"]
                
                for call in calls:
                    tool_name = call.get("name")
                    args = call.get("arguments", {})
                    
                    print(f"\nExecuting: {tool_name}({json.dumps(args)})")
                    
                    # Call the actual tool
                    if tool_name == "browser_navigate":
                        result = browser_navigate(**args)
                    elif tool_name == "browser_click":
                        result = browser_click(**args)
                    elif tool_name == "browser_fill":
                        result = browser_fill(**args)
                    elif tool_name == "browser_screenshot":
                        result = browser_screenshot()
                    elif tool_name == "browser_execute_script":
                        result = browser_execute_script(**args)
                    elif tool_name == "browser_wait_for":
                        result = browser_wait_for(**args)
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    
                    print(f"Result: {json.dumps(result, indent=2)}")
                
                # Feed result back to Needle
                response = agent.complete(json.dumps(result))
                print(f"\nNext response: {response.get('type')}")
                
                step += 1
                if step > 5:  # Prevent infinite loops
                    print("Breaking after 5 steps")
                    break
            
            print(f"\n✓ Test {i} complete")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("Tests complete!")
    print(f"{'='*70}\n")
