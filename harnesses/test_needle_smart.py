"""
Needle + Chrome - Smart Browser Automation
With Google search optimized
"""

import needle
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json

# Global driver
driver = None

def get_driver():
    global driver
    if driver is None:
        chrome_options = Options()
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-features=TranslateUI")
        chrome_options.add_argument("--user-data-dir=C:\\temp\\chrome-needle")
        driver = webdriver.Chrome(options=chrome_options)
    return driver


@needle.tool
def google_search(query: str):
    """Search Google for a query. Opens Google, types the query, and presses Enter.
    
    Args:
        query: Search query (e.g., "Python tutorials", "weather today")
    """
    print(f"[GOOGLE] Searching for: {query}")
    try:
        d = get_driver()
        d.get("https://google.com")
        
        # Auto-accept any consent dialogs
        from chrome_helper import accept_chrome_consent
        accept_chrome_consent(d)
        
        # Find search box and type
        search_box = WebDriverWait(d, 10).until(
            EC.presence_of_element_located((By.NAME, "q"))
        )
        search_box.clear()
        search_box.send_keys(query)
        search_box.send_keys(Keys.RETURN)
        
        # Wait for results
        WebDriverWait(d, 10).until(
            EC.presence_of_element_located((By.ID, "search"))
        )
        
        return {
            "status": "success",
            "query": query,
            "url": d.current_url,
            "title": d.title
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@needle.tool
def browser_navigate(url: str):
    """Navigate to any URL.
    
    Args:
        url: Complete URL (e.g., "https://example.com")
    """
    print(f"[BROWSER] Navigating to: {url}")
    try:
        d = get_driver()
        d.get(url)
        return {"status": "success", "url": d.current_url, "title": d.title}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@needle.tool
def click_first_result():
    """Click the first search result on Google. Use after google_search."""
    print("[GOOGLE] Clicking first result...")
    try:
        d = get_driver()
        # Google search results use specific selectors
        first_result = WebDriverWait(d, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#search .g a"))
        )
        first_result.click()
        return {"status": "success", "url": d.current_url, "title": d.title}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@needle.tool
def get_page_content():
    """Get the main text content of the current page."""
    print("[BROWSER] Getting page content...")
    try:
        d = get_driver()
        # Try to get main content area
        try:
            content = d.find_element(By.TAG_NAME, "main").text
        except:
            content = d.find_element(By.TAG_NAME, "body").text
        
        return {
            "status": "success",
            "text_length": len(content),
            "preview": content[:300]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@needle.tool
def take_screenshot():
    """Take a screenshot of the current page."""
    print("[BROWSER] Taking screenshot...")
    try:
        d = get_driver()
        screenshot = d.get_screenshot_as_base64()
        return {"status": "success", "format": "png", "size_kb": len(screenshot) // 1024}
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    print("=" * 70)
    print("Needle + Chrome - Smart Automation")
    print("=" * 70)
    
    print("\nInitializing agent with smart browser tools...")
    agent = needle.Needle(
        tools=[
            google_search,
            browser_navigate,
            click_first_result,
            get_page_content,
            take_screenshot,
        ]
    )
    print("✓ Agent initialized\n")
    
    # Real-world test queries
    test_queries = [
        "Search for Python tutorials for beginners",
        "Open GitHub homepage",
        "Click the first result",
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
                    
                    # Execute tool
                    if tool_name == "google_search":
                        result = google_search(**args)
                    elif tool_name == "browser_navigate":
                        result = browser_navigate(**args)
                    elif tool_name == "click_first_result":
                        result = click_first_result()
                    elif tool_name == "get_page_content":
                        result = get_page_content()
                    elif tool_name == "take_screenshot":
                        result = take_screenshot()
                    else:
                        result = {"error": f"Unknown: {tool_name}"}
                    
                    print(f"← Result: {json.dumps(result, indent=2)}")
            else:
                print(f"Reasoning: {response.get('reasoning', 'N/A')}")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("Tests complete!")
    if driver:
        print("Closing browser...")
        driver.quit()
    print(f"{'='*70}\n")
