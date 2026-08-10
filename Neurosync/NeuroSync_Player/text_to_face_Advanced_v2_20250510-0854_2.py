from flask import Flask, request, jsonify
from threading import Thread
import pygame
import warnings
import time
import os
import re
from pythonosc import udp_client
from flask_cors import CORS
warnings.filterwarnings(
    "ignore",
    message="Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work"
)
from utils.files.file_utils import save_generated_data, initialize_directories
from utils.generated_runners import run_audio_animation
from utils.neurosync.multi_part_return import get_tts_with_blendshapes
from utils.neurosync.neurosync_api_connect import send_audio_to_neurosync
from utils.tts.eleven_labs import get_elevenlabs_audio
from utils.tts.local_tts import call_local_tts
from livelink.connect.livelink_init import create_socket_connection, initialize_py_face
from livelink.animations.default_animation import default_animation_loop, stop_default_animation

from utils.emote_sender.send_emote import EmoteConnect
# -- SETTINGS --
voice_name = 'bf_isabella'  # bf_isabella
use_elevenlabs = False  # select ElevenLabs or Local TTS
use_combined_endpoint = True  # Only set this true if you have the combined realtime API with TTS + blendshape in one call.
ENABLE_EMOTE_CALLS = False

# --- OSC Configuration ---
# Put or POST ??
# It should be a list of strings, or a single string for one method.
OSC_CHAT_ROUTE_METHOD = ["POST"] # Or just "POST" if you prefer, Flask handles it.
                                 # If you wanted to allow GET as well: ["POST", "GET"]
# IP address of the receiving application.
RECEIVER_IP = "127.0.0.1"  # Use '127.0.0.1' for localhost (same machine) . If you are using Unreal Engine, 127.0.0.1 dont work in Unreal Engine so IN Unreal Engine 
# set your reciever ip to 0.0.0.0
# Port the receiving application is listening on
RECEIVER_PORT = 9001
# OSC Address Pattern to send the message to
OSC_ADDRESS = "/chat/message" # 
# -- SETTINGS END --

print(f"--- OSC Sender Config ---")
print(f"Target IP:   {RECEIVER_IP}")
print(f"Target Port: {RECEIVER_PORT}")
print(f"OSC Address: {OSC_ADDRESS}")
print(f"OSC Rout Method: {OSC_CHAT_ROUTE_METHOD}")
print(f"-------------------------")
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize resources outside the route for efficiency
initialize_directories()
py_face = initialize_py_face()
socket_connection = create_socket_connection()
default_animation_thread = Thread(target=default_animation_loop, args=(py_face,))
default_animation_thread.start()

@app.route('/tts', methods=['POST', 'OPTIONS'])
def text_to_speech():
    """Handles POST requests to generate speech and animation."""
    if request.method == 'OPTIONS':
        # Handle OPTIONS request for CORS preflight
        response = app.make_default_options_response()
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response
        
    try:
        # Try to parse as JSON first
        if request.is_json:
            data = request.get_json()
            
            # Handle the new JSON format
            if 'chatmessage' in data:
                # Extract text from the chat message format
                text_input = data.get('chatmessage', '').strip()
                # You can also access other fields if needed
                chat_name = data.get('chatname', '')
                # If there's a request object with more details
                if 'request' in data and isinstance(data['request'], dict):
                    username = data['request'].get('username', '')
                    # Log who sent the message
                    print(f"Message from {username or chat_name}: {text_input}")
            else:
                # Handle the original format for backward compatibility
                text_input = data.get('text', '').strip()
        else:
            # If not JSON, treat the entire body as plain text
            text_input = request.data.decode('utf-8').strip()
            print(f"Received plain text: {text_input}")

        if not text_input:
            return jsonify({'error': 'No text provided'}), 400

        start_time = time.time()
        if use_combined_endpoint:
            audio_bytes, blendshapes = get_tts_with_blendshapes(text_input, voice_name)
            if audio_bytes and blendshapes:
                generation_time = time.time() - start_time
                print(f"Generation took {generation_time:.2f} seconds.")
                if ENABLE_EMOTE_CALLS:
                    EmoteConnect.send_emote("startspeaking")
                try:
                    run_audio_animation(audio_bytes, blendshapes, py_face, socket_connection,
                                        default_animation_thread)
                finally:
                    if ENABLE_EMOTE_CALLS:
                        EmoteConnect.send_emote("stopspeaking")
                save_generated_data(audio_bytes, blendshapes)
            else:
                return jsonify({'error': 'Failed to retrieve audio and blendshapes from the API'}), 500
        else:
            if use_elevenlabs:
                audio_bytes = get_elevenlabs_audio(text_input, voice_name)
            else:
                audio_bytes = call_local_tts(text_input)

            if audio_bytes:
                generated_facial_data = send_audio_to_neurosync(audio_bytes)
                if generated_facial_data is not None:
                    generation_time = time.time() - start_time
                    print(f"Generation took {generation_time:.2f} seconds.")
                    if ENABLE_EMOTE_CALLS:
                        EmoteConnect.send_emote("startspeaking")
                    try:
                        run_audio_animation(audio_bytes, generated_facial_data, py_face,
                                            socket_connection, default_animation_thread)
                    finally:
                        if ENABLE_EMOTE_CALLS:
                            EmoteConnect.send_emote("stopspeaking")
                    save_generated_data(audio_bytes, generated_facial_data)
                else:
                    return jsonify({'error': 'Failed to get blendshapes from the API'}), 500
            else:
                return jsonify({'error': 'Failed to generate audio'}), 500

        return jsonify({'message': 'Speech and animation generated successfully'}), 200

    except Exception as e:
        print(f"Error: {e}")  # Log the error for debugging
        return jsonify({'error': str(e)}), 500

# --- Create the OSC Client ---
# It's generally better to create the client once
try:
    osc_client = udp_client.SimpleUDPClient(RECEIVER_IP, RECEIVER_PORT)
    print(f"OSC client configured to send to {RECEIVER_IP}:{RECEIVER_PORT}")
 #   print(f"OSC messages send only the extracted text within the brackets <> as OSC messages, will be sent to address: {OSC_ADDRESS}")
except Exception as e:
    print(f"!!!!!!!!!!!!!! ERROR creating OSC client: {e} !!!!!!!!!!!!!!")
    print("OSC sending will be disabled.")
    osc_client = None
# --- Regular Expression to find text in < > ---
# <(.*?)> matches:
# < > : Literal angle brackets
# .   : Any character
# *   : Zero or more times
# ?   : Non-greedy (match the shortest possible string)
# (...) : Capturing group (we want the text *inside* the brackets)

# OSC Begin
# --- Load Keywords from keywords.py ---
LOADED_KEYWORDS = [] # Initialize as an empty list
try:
    # Import the list from your keywords.py file
    # Make sure keywords.py is in the same directory or in Python's import path
    from keywords import keyword_list # Assuming your list is named 'keyword_list'
    LOADED_KEYWORDS = keyword_list
    if not LOADED_KEYWORDS:
        print("Warning: The keyword_list from keywords.py is empty.")
    else:
        print(f"Successfully loaded {len(LOADED_KEYWORDS)} keywords from keywords.py.")
except ImportError:
    print("Error: Could not import 'keyword_list' from keywords.py. Make sure the file exists and the list variable is correctly named.")
except Exception as e:
    print(f"An unexpected error occurred while loading keywords from keywords.py: {e}")


@app.route('/receive_chat', methods=OSC_CHAT_ROUTE_METHOD)
def receive_chat_message():
    """
    Receives chat messages, checks for predefined keywords (case-insensitive)
    from keywords.py, and sends the original-cased keyword via OSC if found.
    """
    data = request.get_json()

    if not data or 'chatmessage' not in data:
        print("Received invalid data format.")
        return jsonify({"status": "error", "message": "Missing 'chatmessage' in JSON payload"}), 400

    ai_response = data.get('chatmessage', '')
    sender = data.get('sender', 'Unknown')
    timestamp = data.get('timestamp', time.time())

    print(f"\nReceived from {sender} at {timestamp}: {ai_response}")

    keywords_to_send_via_osc = []
    if LOADED_KEYWORDS: # Only proceed if keywords were loaded
        ai_response_lower = ai_response.lower()
        for keyword_from_list in LOADED_KEYWORDS: # Iterate through the imported list
            if isinstance(keyword_from_list, str): # Ensure the item is a string
                if keyword_from_list.lower() in ai_response_lower:
                    keywords_to_send_via_osc.append(keyword_from_list) # Add original cased keyword
            else:
                print(f"Warning: Non-string item found in LOADED_KEYWORDS: {keyword_from_list}")

    if not keywords_to_send_via_osc:
        print(" -> No predefined OSC keywords found in the message.")
        return jsonify({"status": "success", "message": "Received, no OSC keywords found"})

    if not osc_client:
        print(" -> OSC keywords found, but OSC client is not available. Skipping send.")
        print(f"   (Would have sent: {keywords_to_send_via_osc})")
        return jsonify({"status": "success", "message": "Received, OSC keywords found but client inactive"})

    print(f" -> Found OSC keywords to send: {keywords_to_send_via_osc}")

    sent_count = 0
    errors = []
    for command_text in keywords_to_send_via_osc:
        try:
            osc_client.send_message(OSC_ADDRESS, [command_text, True])
            print(f"    Sent OSC: {OSC_ADDRESS} -> '{command_text}' with True")
           # print(f"   (Simulating) Sent OSC: {OSC_ADDRESS} -> '{command_text}' with True")
            sent_count += 1
        except Exception as e:
            error_msg = f"Failed to send OSC message for keyword '{command_text}': {e}"
            print(f"   !!! ERROR: {error_msg}")
            errors.append(error_msg)

    if errors:
         return jsonify({
            "status": "partial_error",
            "message": f"Received. Attempted to send {len(keywords_to_send_via_osc)} OSC keyword(s). Sent {sent_count} with {len(errors)} errors.",
            "errors": errors
        }), 500
    else:
        return jsonify({
            "status": "success",
            "message": f"Received. Sent {sent_count} OSC keyword message(s)."
        })
    # OSC END

@app.route('/shutdown', methods=['POST', 'OPTIONS'])
def shutdown():
    """Shutdown the Flask server and cleanup resources."""
    if request.method == 'OPTIONS':
        # Handle OPTIONS request for CORS preflight
        response = app.make_default_options_response()
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        return response
        
    try:
        stop_default_animation.set()
        if default_animation_thread:
            default_animation_thread.join()
        pygame.quit()
        socket_connection.close()
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            raise RuntimeError('Not running with the Werkzeug Server')
        func()
        return jsonify({'message': 'Server shutting down'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}, 500)

# Add a simple interactive mode if running directly
def interactive_mode():
    try:
        while True:
            text_input = input("Enter the text to generate speech (or 'q' to quit): ").strip()
            if text_input.lower() == 'q':
                break
            elif text_input:
                start_time = time.time()
                if use_combined_endpoint:
                    audio_bytes, blendshapes = get_tts_with_blendshapes(text_input, voice_name)
                    if audio_bytes and blendshapes:
                        generation_time = time.time() - start_time
                        print(f"Generation took {generation_time:.2f} seconds.")
                        if ENABLE_EMOTE_CALLS:
                            EmoteConnect.send_emote("startspeaking")
                        try:
                            run_audio_animation(audio_bytes, blendshapes, py_face, socket_connection,
                                                default_animation_thread)
                        finally:
                            if ENABLE_EMOTE_CALLS:
                                EmoteConnect.send_emote("stopspeaking")
                        save_generated_data(audio_bytes, blendshapes)
                    else:
                        print("❌ Failed to retrieve audio and blendshapes from the API.")
                else:
                    if use_elevenlabs:
                        audio_bytes = get_elevenlabs_audio(text_input, voice_name)
                    else:
                        audio_bytes = call_local_tts(text_input)

                    if audio_bytes:
                        generated_facial_data = send_audio_to_neurosync(audio_bytes)
                        if generated_facial_data is not None:
                            generation_time = time.time() - start_time
                            print(f"Generation took {generation_time:.2f} seconds.")
                            if ENABLE_EMOTE_CALLS:
                                EmoteConnect.send_emote("startspeaking")
                            try:
                                run_audio_animation(audio_bytes, generated_facial_data, py_face,
                                                    socket_connection, default_animation_thread)
                            finally:
                                if ENABLE_EMOTE_CALLS:
                                    EmoteConnect.send_emote("stopspeaking")
                            save_generated_data(audio_bytes, generated_facial_data)
                        else:
                            print("❌ Failed to get blendshapes from the API.")
                    else:
                        print("❌ Failed to generate audio.")
            else:
                print("⚠️ No text provided.")
    finally:
        stop_default_animation.set()
        if default_animation_thread:
            default_animation_thread.join()
        pygame.quit()
        socket_connection.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the TTS and animation system.")
    group = parser.add_mutually_exclusive_group(required=True)  # Ensure only one mode is selected
    group.add_argument("--web", action="store_true", help="Run in web server mode (Flask).")
    group.add_argument("--interactive", action="store_true", help="Run in interactive command-line mode.")
    args = parser.parse_args()

    if args.web:
        app.run(debug=False, port=13000)  # Run Flask in web mode
    elif args.interactive:
        interactive_mode()  # Run in interactive/command line mode