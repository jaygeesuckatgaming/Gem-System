import requests

OPENCODE_URL = "http://localhost:4096"

def test_opencode_connection():
    print(f"Connecting to OpenCode server at: {OPENCODE_URL}...")
    
    # 1. Test basic connectivity (Health / API check)
    try:
        # Check the health endpoint first
        response = requests.get(f"{OPENCODE_URL}/health", timeout=5)
        
        # Fallback to session listing if /health is not implemented or acts differently
        if response.status_code == 404:
            response = requests.get(f"{OPENCODE_URL}/session", timeout=5)
            
        response.raise_for_status()
        print("✅ Connection Successful: OpenCode server is running and reachable!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to OpenCode.")
        print("👉 Did you start the server? Run this in your terminal first:")
        print("   opencode serve --port 4096")
        return
        
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error: The server was reached but returned an HTTP error status: {e}")
        return
        
    except Exception as e:
        print(f"❌ Error: An unexpected issue occurred: {e}")
        return

    # 2. Query and display active sessions
    try:
        session_list_resp = requests.get(f"{OPENCODE_URL}/session", timeout=5)
        session_list_resp.raise_for_status()
        sessions = session_list_resp.json()
        
        print(f"\n📂 Active Sessions: {len(sessions)}")
        if sessions:
            for idx, session in enumerate(sessions):
                dir_path = session.get("location", {}).get("directory", "Unknown path")
                print(f"   [{idx + 1}] Session ID: {session.get('id')} | Directory: {dir_path}")
        else:
            print("   (No active sessions found. The server is ready to accept new jobs.)")
            
    except Exception as e:
        print(f"⚠️ Warning: Reached the server, but could not parse the session list: {e}")

if __name__ == "__main__":
    test_opencode_connection()