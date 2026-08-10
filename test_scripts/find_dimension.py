import requests
import json

# --- CONFIGURATION ---
# Make sure this model name is exactly as it appears in `ollama list`
MODEL_NAME = "llava:7b"
OLLAMA_URL = "http://localhost:11434/api/embeddings"

print(f"Attempting to get embedding dimension for model: '{MODEL_NAME}'...")

# A simple text prompt is all we need
payload = {
  "model": MODEL_NAME,
  "prompt": "hello"
}

try:
    # Make the request to Ollama's embedding endpoint
    response = requests.post(OLLAMA_URL, json=payload, timeout=60)
    response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

    response_json = response.json()
    
    # The JSON response should contain a key named 'embedding'
    embedding_vector = response_json.get('embedding')

    if embedding_vector and isinstance(embedding_vector, list):
        dimension = len(embedding_vector)
        print("\n" + "="*50)
        print(f"✅ SUCCESS!")
        print(f"   The vector dimension for model '{MODEL_NAME}' is: {dimension}")
        print(f"   You should set VECTOR_DIMENSIONS = {dimension} in mcp.py")
        print("="*50 + "\n")
    else:
        print("\n" + "!"*50)
        print("❌ ERROR: Could not find the embedding vector in the response from Ollama.")
        print(f"   Full response: {response_json}")
        print("!"*50 + "\n")

except requests.exceptions.RequestException as e:
    print("\n" + "!"*50)
    print(f"❌ FATAL ERROR: Could not connect to the Ollama server at {OLLAMA_URL}.")
    print(f"   Please make sure Ollama is running. Details: {e}")
    print("!"*50 + "\n")
except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")