import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Thread
import pygame
import warnings
import time
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

# --- Your existing script's core logic (modified) ---
# We'll move the main loop into a function that can be called by Flask

voice_name = 'Sarah'  # bf_isabella
use_elevenlabs = False  # select ElevenLabs or Local TTS
use_combined_endpoint = True  # Only set this true if you have the combined realtime API with TTS + blendshape in one call.
ENABLE_EMOTE_CALLS = False

# Global variables to manage threads and Pygame
py_face = None
socket_connection = None
default_animation_thread = None
stop_default_animation_event = None # Use an event for signaling stop

def initialize_app_resources():
    """Initializes resources needed by the script."""
    global py_face, socket_connection, default_animation_thread, stop_default_animation_event
    initialize_directories()
    py_face = initialize_py_face()
    socket_connection = create_socket_connection()
    stop_default_animation_event = threading.Event() # Initialize the event
    default_animation_thread = Thread(target=default_animation_loop, args=(py_face, stop_default_animation_event))
    default_animation_thread.start()
    print("App resources initialized.")

def process_text(text_input):
    """Processes the input text and generates audio/animation."""
    if not text_input:
        return {"status": "error", "message": "No text provided."}

    start_time = time.time()
    try:
        if use_combined_endpoint:
            audio_bytes, blendshapes = get_tts_with_blendshapes(text_input, voice_name)
            if audio_bytes and blendshapes:
                generation_time = time.time() - start_time
                print(f"Generation took {generation_time:.2f} seconds.")
                if ENABLE_EMOTE_CALLS:
                    EmoteConnect.send_emote("startspeaking")
                try:
                    # Ensure run_audio_animation is non-blocking or handled appropriately
                    # For simplicity, we'll assume it runs and completes, or you might need to run it in another thread
                    run_audio_animation(audio_bytes, blendshapes, py_face, socket_connection, default_animation_thread)
                finally:
                    if ENABLE_EMOTE_CALLS:
                        EmoteConnect.send_emote("stopspeaking")
                save_generated_data(audio_bytes, blendshapes)
                return {"status": "success", "message": "Audio and blendshapes generated and processed."}
            else:
                return {"status": "error", "message": "Failed to retrieve audio and blendshapes from the API."}
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
                        run_audio_animation(audio_bytes, generated_facial_data, py_face, socket_connection, default_animation_thread)
                    finally:
                        if ENABLE_EMOTE_CALLS:
                            EmoteConnect.send_emote("stopspeaking")
                    save_generated_data(audio_bytes, generated_facial_data)
                    return {"status": "success", "message": "Audio and blendshapes generated and processed."}
                else:
                    return {"status": "error", "message": "Failed to get blendshapes from the API."}
            else:
                return {"status": "error", "message": "Failed to generate audio."}
    except Exception as e:
        print(f"An error occurred during processing: {e}")
        return {"status": "error", "message": f"An unexpected error occurred: {e}"}

# --- Flask App Setup ---
app = Flask(__name__)
CORS(app)
@app.route('/receive_chat', methods=['POST'])
def handle_process_text():
    """
    Handles POST requests to the /process endpoint.
    Expects JSON data with a 'text' key.
    """
    if not request.is_json:
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    text_to_process = data.get('text')

    if not text_to_process:
        return jsonify({"status": "error", "message": "Missing 'text' in JSON payload"}), 400

    print(f"Received text: '{text_to_process}'")
    result = process_text(text_to_process)
    return jsonify(result)

@app.route('/start', methods=['GET'])
def start_server_components():
    """
    Endpoint to initialize the necessary components (like Pygame, LiveLink).
    Call this before sending text to process.
    """
    if py_face is None or socket_connection is None or default_animation_thread is None or stop_default_animation_event is None:
        initialize_app_resources()
        return jsonify({"status": "success", "message": "Application resources initialized."})
    else:
        return jsonify({"status": "info", "message": "Application resources already initialized."})

@app.route('/stop', methods=['GET'])
def stop_server_components():
    """
    Endpoint to gracefully shut down the application components.
    """
    global py_face, socket_connection, default_animation_thread, stop_default_animation_event
    if stop_default_animation_event and not stop_default_animation_event.is_set():
        stop_default_animation_event.set() # Signal the default animation thread to stop
        if default_animation_thread:
            default_animation_thread.join(timeout=5) # Wait for the thread to finish

    if socket_connection:
        socket_connection.close()
        socket_connection = None
        print("Socket connection closed.")

    if py_face:
        # Pygame needs to be quit properly. If py_face is just an object,
        # you might need a specific method to clean it up.
        # For now, assuming pygame.quit() is sufficient.
        pygame.quit()
        py_face = None
        print("Pygame quit.")

    py_face = None
    socket_connection = None
    default_animation_thread = None
    stop_default_animation_event = None
    print("Application resources stopped.")
    return jsonify({"status": "success", "message": "Application resources stopped."})


if __name__ == '__main__':
    # Initialize resources when the script is run directly
    initialize_app_resources()

    # Run the Flask development server
    # Use host='0.0.0.0' to make it accessible from other machines on your network
    # Set debug=True for development to get live reloads and error messages
    # http://127.0.0.1:13000/receive_chat
    app.run(host='127.0.0.1', port=13000, debug=True, threaded=True)
    # When Flask server stops, ensure cleanup happens
    # Note: The stop_server_components function should ideally be called via its endpoint
    # or through a signal handler if you need a more robust shutdown.