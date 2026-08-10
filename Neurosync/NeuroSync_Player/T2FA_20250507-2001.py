# This software is licensed under a **dual-license model**
# For individuals and businesses earning **under $1M per year**, this software is licensed under the **MIT License**
# Businesses or organizations with **annual revenue of $1,000,000 or more** must obtain permission to use this software commercially.

from threading import Thread, Event # Added Event for clarity
import pygame
import warnings
import time
warnings.filterwarnings(
    "ignore",
    message="Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work"
)
from flask import Flask, request, jsonify # <<< ADDED FLASK IMPORTS

from utils.files.file_utils import save_generated_data, initialize_directories
from utils.generated_runners import run_audio_animation
from utils.neurosync.multi_part_return import get_tts_with_blendshapes
from utils.neurosync.neurosync_api_connect import send_audio_to_neurosync
from utils.tts.eleven_labs import get_elevenlabs_audio
from utils.tts.local_tts import call_local_tts
from livelink.connect.livelink_init import create_socket_connection, initialize_py_face
from livelink.animations.default_animation import default_animation_loop # stop_default_animation is an Event here
# It's better if stop_default_animation is explicitly an Event defined here or imported
# Assuming stop_default_animation is an Event object from default_animation module, or we create one.
# Let's assume it's an Event object we need to create if not directly provided by the module
# from livelink.animations.default_animation import stop_default_animation # If it's an object
stop_default_animation_event = Event() # <<< CREATE THE EVENT OBJECT

from utils.emote_sender.send_emote import EmoteConnect

# --- Configuration ---
voice_name = 'Sarah' # bf_isabella
use_elevenlabs = True  # select ElevenLabs or Local TTS
use_combined_endpoint = False  # Only set this true if you have the combined realtime API with TTS + blendshape in one call.
ENABLE_EMOTE_CALLS = False
FLASK_PORT = 13000 # Port for the Flask app

# --- Global Variables for shared resources ---
# These will be initialized once and used by the processing function
py_face_global = None
socket_connection_global = None
default_animation_thread_global = None

# --- Flask App Definition ---
app = Flask(__name__)

def process_text_and_animate(text_input, py_face, socket_connection, default_animation_thread_ref):
    """
    Core logic to process text, generate audio/blendshapes, and run animation.
    This function can be called from the console input or a Flask route.
    Returns a tuple: (success_boolean, message_string)
    """
    if not text_input:
        print("⚠️ No text provided.")
        return False, "No text provided."

    start_time = time.time()
    audio_bytes = None
    blendshapes_data = None
    error_message = None

    if use_combined_endpoint:
        print(f"Processing with combined endpoint for: '{text_input}'")
        audio_bytes, blendshapes_data = get_tts_with_blendshapes(text_input, voice_name)
        if not (audio_bytes and blendshapes_data):
            error_message = "❌ Failed to retrieve audio and blendshapes from the combined API."
    else:
        print(f"Processing with separate TTS/Neurosync for: '{text_input}'")
        if use_elevenlabs:
            print("Using ElevenLabs for TTS...")
            audio_bytes = get_elevenlabs_audio(text_input, voice_name)
        else:
            print("Using local TTS...")
            audio_bytes = call_local_tts(text_input)

        if audio_bytes:
            print("Audio generated, sending to Neurosync for blendshapes...")
            blendshapes_data = send_audio_to_neurosync(audio_bytes)
            if blendshapes_data is None:
                error_message = "❌ Failed to get blendshapes from the Neurosync API."
        else:
            error_message = "❌ Failed to generate audio."

    if error_message:
        print(error_message)
        return False, error_message

    if audio_bytes and blendshapes_data:
        generation_time = time.time() - start_time
        print(f"Generation took {generation_time:.2f} seconds.")

        if ENABLE_EMOTE_CALLS:
            EmoteConnect.send_emote("startspeaking")
        try:
            print("Running audio animation...")
            # Pass the event object to run_audio_animation if it needs to signal the default animation
            run_audio_animation(audio_bytes, blendshapes_data, py_face, socket_connection, stop_default_animation_event)
            # Note: The original 'default_animation_thread' was passed. If run_audio_animation
            # needs the thread object itself, this needs adjustment. More likely it needs an Event
            # to signal the default loop, or the default loop checks a shared state.
            # For now, I'm assuming stop_default_animation_event is the mechanism.
        finally:
            if ENABLE_EMOTE_CALLS:
                EmoteConnect.send_emote("stopspeaking")

        save_generated_data(audio_bytes, blendshapes_data)
        print(f"Successfully processed and animated: '{text_input}'")
        return True, f"Successfully processed and animated: '{text_input}', generation took {generation_time:.2f}s"
    else:
        # This case should be caught by error_message logic above, but as a fallback:
        final_error = "❌ Unknown error during processing."
        print(final_error)
        return False, final_error


@app.route('/generate', methods=['POST'])
def generate_speech_api():
    global py_face_global, socket_connection_global, default_animation_thread_global
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    text_input = data.get('text')

    if not text_input:
        return jsonify({"error": "Missing 'text' in JSON payload"}), 400

    print(f"\nReceived API request for text: '{text_input}'")
    success, message = process_text_and_animate(
        text_input,
        py_face_global,
        socket_connection_global,
        default_animation_thread_global # Pass the thread reference if needed by process_text_and_animate
    )

    if success:
        return jsonify({"status": "success", "message": message}), 200
    else:
        return jsonify({"status": "error", "message": message}), 500

def run_console_input_loop():
    """Optional: Keep the console input loop if desired."""
    global py_face_global, socket_connection_global, default_animation_thread_global
    print("\nConsole input enabled. Type text and press Enter, or 'q' to quit console mode (Flask server will keep running).")
    try:
        while True:
            text_input_console = input("Enter the text to generate speech (or 'q' to quit console input): ").strip()
            if text_input_console.lower() == 'q':
                print("Exiting console input mode. Flask server continues to run.")
                break
            elif text_input_console:
                process_text_and_animate(
                    text_input_console,
                    py_face_global,
                    socket_connection_global,
                    default_animation_thread_global
                )
    except KeyboardInterrupt:
        print("\nConsole input interrupted.")
    except EOFError: # Handles Ctrl+D
        print("\nConsole input ended (EOF).")


if __name__ == "__main__":
    initialize_directories()
    py_face_global = initialize_py_face()
    socket_connection_global = create_socket_connection()

    # Ensure default_animation_loop uses the stop_default_animation_event
    default_animation_thread_global = Thread(
        target=default_animation_loop,
        args=(py_face_global, stop_default_animation_event) # Pass the event
    )
    default_animation_thread_global.daemon = True # So it exits when main thread exits
    default_animation_thread_global.start()

    # Start Flask app in a separate thread so it doesn't block the main thread
    # (which might be used for console input or other tasks, and for clean shutdown)
    # Use use_reloader=False to prevent issues with threads when developing
    flask_thread = Thread(target=lambda: app.run(host='0.0.0.0', port=FLASK_PORT, debug=True, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    print(f"🚀 Flask server started on http://0.0.0.0:{FLASK_PORT}")
    print(f"📝 Send POST requests to http://0.0.0.0:{FLASK_PORT}/generate with JSON payload: {{ \"text\": \"your message\" }}")


    # --- Option 1: Keep main thread for console input (or just to keep alive) ---
    # run_console_input_loop() # Uncomment to enable console input alongside Flask

    # --- Option 2: Main thread just waits for Flask/default animation (or other signals) to finish ---
    # If you don't run console_input_loop, the main thread might exit if flask_thread is a daemon
    # and there's nothing else to keep it alive. So, we can join the flask_thread
    # or use a loop with a sleep to keep the main thread alive for handling Ctrl+C.

    print("\nApplication started. Press Ctrl+C to exit.")
    try:
        # Keep the main thread alive to catch Ctrl+C for cleanup
        # If flask_thread is not a daemon, flask_thread.join() would block here until Flask exits.
        # If it is a daemon, we need another way to keep alive.
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        print("Stopping default animation...")
        stop_default_animation_event.set()
        if default_animation_thread_global and default_animation_thread_global.is_alive():
            default_animation_thread_global.join(timeout=5)
            if default_animation_thread_global.is_alive():
                print("⚠️ Default animation thread did not stop in time.")

        if py_face_global and hasattr(py_face_global, 'close'): # If PyFace has a close method
             py_face_global.close()
        if socket_connection_global:
            print("Closing socket connection...")
            socket_connection_global.close()

        print("Quitting Pygame...")
        pygame.quit()
        print("Application finished.")