from flask import Flask, request, jsonify
from threading import Thread
import pygame
import warnings
import time
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

voice_name = 'bf_isabella'  # bf_isabella
use_elevenlabs = False  # select ElevenLabs or Local TTS
use_combined_endpoint = True  # Only set this true if you have the combined realtime API with TTS + blendshape in one call.
ENABLE_EMOTE_CALLS = False

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
        print("Reached start of /tts route handler")
        # Try to parse as JSON first
        if request.is_json:
            data = request.get_json()
            print("Request is JSON")
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
        print("text_input is not empty. Proceeding to timing and generation...")

        start_time = time.time()
        print("start_time captured.")
        if use_combined_endpoint:
            print("use_combined_endpoint is True. Calling get_tts_with_blendshapes...")
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
        app.run(debug=False, port=13000)  # Change the port to 8000 # Run Flask in web mode
    elif args.interactive:
        interactive_mode()  # Run in interactive/command line mode