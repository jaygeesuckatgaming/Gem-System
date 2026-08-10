from flask import Flask, request, jsonify

# Use a port that we are absolutely sure is free.
# We will use 9999 for this test.
TEST_PORT = 9999

app = Flask(__name__)

@app.route('/tts', methods=['POST', 'PUT'])
def handle_chat_message():
    """
    This is the only function. It receives a message and prints it.
    """
    
    # --- This print statement is the key. ---
    # If we see this, the server is working.
    print("\n==============================================")
    print("--- MINIMAL INTERCEPTOR RECEIVED A REQUEST ---")
    
    try:
        data = request.json
        chat_message = data.get('chatmessage', 'No chatmessage field found')
        print(f"--- Message Content: '{chat_message}'")
    except Exception as e:
        print(f"--- Error parsing JSON: {e}")
        
    print("==============================================\n")

    # Return a simple success message.
    return jsonify({"status": "ok from minimal interceptor"}), 200

if __name__ == '__main__':
    print(f"--- Starting Minimal Test Interceptor on http://127.0.0.1:{TEST_PORT} ---")
    print("--- Send a message from Discord to this server to test. ---")
    app.run(host='127.0.0.1', port=TEST_PORT, debug=True)