"""
Needle 2 Test Script
Test the Needle framework without touching the main codebase
"""

import needle
import json

# ============================================================================
# Define some simple test tools
# ============================================================================

@needle.tool
def get_weather(city: str):
    """Get the current weather for a city.
    
    Args:
        city: name of the city
    """
    print(f"[TOOL CALLED] get_weather for {city}")
    return {"city": city, "temp_c": 27, "sky": "clear", "humidity": 65}


@needle.tool
def set_alarm(time: str, label: str = ""):
    """Set an alarm.
    
    Args:
        time: time in HH:MM format
        label: optional label for the alarm
    """
    print(f"[TOOL CALLED] set_alarm for {time} (label: {label})")
    return {"success": True, "time": time, "label": label or "Alarm"}


@needle.tool
def search_web(query: str):
    """Search the web for information.
    
    Args:
        query: search query
    """
    print(f"[TOOL CALLED] search_web for '{query}'")
    # Mock search results
    return {
        "query": query,
        "results": [
            {"title": f"Result 1 for {query}", "url": "https://example.com/1"},
            {"title": f"Result 2 for {query}", "url": "https://example.com/2"},
        ]
    }


# ============================================================================
# Test the Needle agent
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("Needle 2 Test Script")
    print("=" * 70)
    
    # Create the agent with our tools
    print("\nInitializing Needle agent with 3 tools...")
    agent = needle.Needle(tools=[get_weather, set_alarm, search_web])
    print("✓ Agent initialized\n")
    
    # Test queries
    test_queries = [
        "What's the weather like in Tokyo?",
        "Wake me up at 7:30 AM",
        "Search for Python tutorials",
        "Turn on the lights",  # Should return empty (unsupported)
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}: {query}")
        print(f"{'='*70}")
        
        try:
            # Run the query
            result = agent.run(query)
            
            # Print the response
            print(f"\nResponse type: {result.get('type', 'unknown')}")
            print(f"Confidence: {result.get('confidence', 'N/A')}")
            print(f"Function calls: {json.dumps(result.get('function_calls', []), indent=2)}")
            print(f"Results: {json.dumps(result.get('results', []), indent=2)}")
            
            if result.get('function_calls') and len(result['function_calls']) == 0:
                print("→ REFUSAL: Empty function_calls (tool not supported)")
            
        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"\n{'='*70}")
    print("Tests complete!")
    print(f"{'='*70}\n")
