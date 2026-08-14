"""
Needle + Chrome DevTools Direct CDP Integration
Uses Chrome DevTools Protocol directly via websocket
"""

import needle
import asyncio
import json

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Global driver for browser control
driver = None

def get_driver():
    """Get or create Chrome WebDriver instance"""
    global driver
    if driver is None and SELENIUM_AVAILABLE:
        chrome_options = Options()
        chrome_options.add_argument("--remote-debugging-port=9222")
        driver = webdriver.Chrome(options=chrome_options)
    return driver


@needle.tool
def browser_navigate(url: str):
    """Open a website by navigating the browser to a URL. Use this to visit any webpage.
    
    Args:
        url: The complete URL (e.g., "https://google.com")
    """
    print(f"[BROWSER] Navigating to: {url}")
    if SELENIUM_AVAILABLE:
        d = get_driver()
        d.get(url)
        return {"status": "success", "url": d.current_url, "title": d.title}
    else:
        return {"status": "error", "message": "Selenium not installed"}


@needle.tool
def browser_click(selector: str):
    """Click an element on the page using CSS selector.
    
    Args:
        selector: CSS selector (e.g., "button.search", "a.result")
    """
    print(f"[BROWSER] Clicking: {selector}")
    if SELENIUM_AVAILABLE:
        try:
            d = get_driver()
            element = d.find_element("css selector", selector)
            element.click()
            return {"status": "success", "clicked": selector}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Selenium not installed"}


@needle.tool
def browser_fill(selector: str, value: str):
    """Fill text into an input field.
    
    Args:
        selector: CSS selector for the input field
        value: Text to type
    """
    print(f"[BROWSER] Filling {selector} with: {value}")
    if SELENIUM_AVAILABLE:
        try:
            d = get_driver()
            element = d.find_element("css selector", selector)
            element.clear()
            element.send_keys(value)
            return {"status": "success", "filled": selector, "value": value}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Selenium not installed"}


@needle.tool
def browser_screenshot():
    """Take a screenshot of the current page. Returns base64 encoded image."""
    print("[BROWSER] Taking screenshot...")
    if SELENIUM_AVAILABLE:
        try:
            d = get_driver()
            screenshot = d.get_screenshot_as_base64()
            return {"status": "success", "format": "png", "size": len(screenshot)}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Selenium not installed"}


@needle.tool
def browser_get_text():
    """Get the visible text content of the current page."""
    print("[BROWSER] Getting page text...")
    if SELENIUM_AVAILABLE:
        try:
            d = get_driver()
            text = d.find_element("tag name", "body").text
            return {"status": "success", "text_length": len(text), "preview": text[:200]}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Selenium not installed"}


if __name__ == "__main__":
    print("=" * 70)
    print("Needle + Chrome Direct CDP Test")
    print("=" * 70)
    
    if not SELENIUM_AVAILABLE:
        print("\n⚠️  Selenium not installed. Install with:")
        print("   pip install selenium webdriver-manager")
        print("\nRunning in mock mode...")
    
    print("\nInitializing Needle agent...")
    agent = needle.Needle(
        tools=[
            browser_navigate,
            browser_click,
            browser_fill,
            browser_screenshot,
            browser_get_text,
        ]
    )
    print("✓ Agent initialized\n")
    
    # Test queries
    test_queries = [
        "Open Google homepage",
        "Search for Python tutorials",
        "What's on the page?",
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}: {query}")
        print(f"{'='*70}")
        
        try:
            agent.reset()
            response = agent.complete(query)
            
            print(f"\nResponse type: {response['type']}")
            print(f"Confidence: {response['confidence']:.4f}")
            
            if response.get("function_calls"):
                print(f"\nFunction calls:")
                for call in response["function_calls"]:
                    print(f"  - {call['name']}: {call['arguments']}")
                    
                    # Execute the tool
                    tool_name = call["name"]
                    args = call["arguments"]
                    
                    if tool_name == "browser_navigate":
                        result = browser_navigate(**args)
                    elif tool_name == "browser_click":
                        result = browser_click(**args)
                    elif tool_name == "browser_fill":
                        result = browser_fill(**args)
                    elif tool_name == "browser_screenshot":
                        result = browser_screenshot()
                    elif tool_name == "browser_get_text":
                        result = browser_get_text()
                    else:
                        result = {"error": f"Unknown tool: {tool_name}"}
                    
                    print(f"  Result: {json.dumps(result, indent=4)}")
            else:
                print(f"Reasoning: {response.get('reasoning', 'N/A')}")
            
        except Exception as e:
            print(f"ERROR: {e}")
    
    print(f"\n{'='*70}")
    print("Tests complete!")
    if SELENIUM_AVAILABLE and driver:
        print("Closing browser...")
        driver.quit()
    print(f"{'='*70}\n")
