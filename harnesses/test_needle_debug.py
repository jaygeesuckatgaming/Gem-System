"""
Needle 2 Debug Test
See the raw model output with agent.complete()
"""

import needle
import json

@needle.tool
def get_weather(city: str):
    """Get the current weather for a city."""
    return {"city": city, "temp_c": 27}

@needle.tool  
def set_alarm(time: str):
    """Set an alarm at a specific time."""
    return {"success": True, "time": time}

if __name__ == "__main__":
    print("Creating agent...")
    agent = needle.Needle(tools=[get_weather, set_alarm])
    
    print("\n" + "="*70)
    print("Test 1: Using agent.run() (full loop)")
    print("="*70)
    result = agent.run("What's the weather in Tokyo?")
    print(json.dumps(result, indent=2))
    
    print("\n" + "="*70)
    print("Test 2: Using agent.complete() (raw model output)")
    print("="*70)
    raw = agent.complete("What's the weather in Tokyo?")
    print(json.dumps(raw, indent=2))
    
    print("\n" + "="*70)
    print("Test 3: Manual loop with complete()")
    print("="*70)
    
    # Reset agent state
    agent.reset()
    
    query = "Set an alarm for 7 AM"
    print(f"Query: {query}\n")
    
    response = agent.complete(query)
    print(f"Step 1 - Raw response: {json.dumps(response, indent=2)}")
    
    calls = response.get("function_calls", [])
    if calls:
        print(f"\nFunction calls detected: {calls}")
        for call in calls:
            if call["name"] == "set_alarm":
                result = set_alarm(**call["arguments"])
                print(f"Executed: {result}")
                
                # Feed result back
                response2 = agent.complete(json.dumps(result))
                print(f"\nStep 2 - After feeding result: {json.dumps(response2, indent=2)}")
    else:
        print("No function calls - model refused or responded directly")
