from flask import Flask, request, jsonify

# 1. Create the Flask application instance
app = Flask(__name__)

# 2. Define a simple "Hello World" route for the root URL
@app.route('/', methods=['GET'])
def index():
    """This route should be accessible from a web browser."""
    print("--- SERVER LOG: Root URL ('/') was accessed. ---")
    return "Hello, the server is running!"

# 3. Define the '/process' route that our vision script needs
@app.route('/process', methods=['POST'])
def process():
    """This route handles the data from the vision and listen scripts."""
    print("--- SERVER LOG: The '/process' endpoint was accessed. ---")
    
    # Get the JSON data sent by the client
    data = request.json
    print(f"--- SERVER LOG: Received data: {data} ---")
    
    # Send a simple success response back
    response_data = {
        "response": f"MCP received your message: '{data.get('text')}'"
    }
    return jsonify(response_data)

# 4. The main block to run the server
if __name__ == '__main__':
    print("\n=======================================================")
    print("--- Starting Minimal Test Server ---")
    print("--- Listening on http://127.0.0.1:5000 ---")
    print("=======================================================\n")
    
    # Run the app. `debug=True` gives us more helpful error messages.
    app.run(host='127.0.0.1', port=5000, debug=True)