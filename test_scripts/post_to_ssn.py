import requests
import json

# --- Configuration ---
# 1. Get your Session ID from the Social Stream Ninja app settings under "Server API".
session_id = "Jt52wHCv2j" 

# 2. Specify the target platform (e.g., "discord", "youtube", "twitch").
target_platform = "discord" 

# 3. The message you want to send.
message_to_send = "This is a test message to inspect the raw request."

# --- API Request Preparation ---

# Construct the full API endpoint URL.
url = f"https://io.socialstream.ninja/{session_id}"

# Create the JSON payload.
payload = {
    "action": "sendChat",
    "value": message_to_send,
    "target": target_platform
}

# The requests library automatically adds some headers (like Host, User-Agent, etc.).
# We'll explicitly define the one we are setting.
headers = {
    "Content-Type": "application/json"
}

# --- What is being sent ---
# This section prints a representation of the raw HTTP request.
print("--- Preparing to send the following HTTP POST request ---")

# 1. Print the Request Line (Method, URL, HTTP Version)
print(f"POST /{session_id} HTTP/1.1")

# 2. Print the Host Header (derived from the URL)
host = url.split('//')[1].split('/')[0]
print(f"Host: {host}")

# 3. Print the headers we are defining
for key, value in headers.items():
    print(f"{key}: {value}")

# The `requests` library will also add its own User-Agent and other headers automatically.
# This printout shows the most critical parts you are controlling.

# 4. Print a blank line to separate headers from the body
print()

# 5. Print the JSON body, nicely formatted
# Use json.dumps to convert the Python dictionary to a JSON formatted string
body_as_string = json.dumps(payload, indent=2)
print(body_as_string)

print("------------------------------------------------------\n")


# --- Sending the Request ---
print("Executing the request...")
try:
    # Send the POST request with the JSON payload.
    response = requests.post(url, json=payload, headers=headers)

    # Raise an exception if the request returned an unsuccessful status code (4xx or 5xx).
    response.raise_for_status()

    # If the request was successful
    print("\n--- Success! ---")
    print(f"Status Code: {response.status_code}")
    print("Response Body:")
    print(response.text if response.text else "[No content in response body]")

except requests.exceptions.HTTPError as http_err:
    print(f"\n--- HTTP Error Occurred ---")
    print(f"Status Code: {http_err.response.status_code}")
    print(f"Response Body: {http_err.response.text}")
    print("\nTroubleshooting: Is your Session ID correct? Is the Social Stream Ninja app running and the API enabled?")
except requests.exceptions.RequestException as err:
    print(f"\n--- A Network or Connection Error Occurred ---")
    print(f"Error: {err}")