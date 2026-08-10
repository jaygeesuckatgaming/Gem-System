import os
import sys
import io
import random
from threading import Lock

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import soundfile as sf
import numpy as np
import torch
import pygame
import phonemizer

# --- Core StyleTTS 2 Imports ---
import styletts2importable
from txtsplit import txtsplit

# --- Configuration (Hardcoded for simplicity, can be moved to a file later) ---
# TTS Parameters
DIFFUSION_STEPS = 20
EMBEDDING_SCALE = 1.0
ALPHA = 0.3
BETA = 0.7
SAMPLE_RATE = 24000
SEED = 42
REFERENCE_VOICE = "voices/f-us-1.wav"

# Audio Processing Parameters
TRIM_THRESHOLD = 0.01
FADE_DURATION = 0.05

# Server Parameters
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 13000
SERVER_DEBUG = False

# --- Helper Function for Reproducibility ---
def set_seed(seed):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- StyleTTS 2 Phonemizer Initialization ---
print("Initializing StyleTTS 2 phonemizer with stress...")
global_phonemizer = phonemizer.backend.EspeakBackend(
    language='en-us', preserve_punctuation=True, with_stress=True
)
print("Phonemizer initialized.")

# --- Global variables for StyleTTS 2 ---
global_target_style = None
styletts_lock = Lock() # Use a lock for thread-safe access

# --- Initialization Function for StyleTTS 2 ---
def initialize_styletts2(reference_voice_path):
    global global_target_style
    print("--- Initializing StyleTTS 2 ---")
    try:
        if not os.path.exists(reference_voice_path):
            raise FileNotFoundError(f"Reference voice file not found at '{reference_voice_path}'")
        print(f"Computing StyleTTS 2 voice style from '{reference_voice_path}'...")
        global_target_style = styletts2importable.compute_style(reference_voice_path)
        print("StyleTTS 2 instance initialized successfully.")
    except Exception as e:
        print(f"FATAL ERROR: Failed to initialize StyleTTS 2: {e}")
        sys.exit(1)

# --- Audio Processing Function (from Neurosync script) ---
def trim_and_fade(audio, sample_rate, threshold, fade_duration):
    above_threshold = np.where(np.abs(audio) > threshold)[0]
    if above_threshold.size == 0: return audio
    start_idx, end_idx = above_threshold[0], above_threshold[-1] + 1
    trimmed_audio = audio[start_idx:end_idx]
    fade_samples = min(int(fade_duration * sample_rate), len(trimmed_audio) // 2)
    if fade_samples > 0:
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        trimmed_audio[:fade_samples] *= fade_in
        trimmed_audio[-fade_samples:] *= fade_out
    return trimmed_audio

# --- The Main TTS API Endpoint ---
@app.route('/generate_speech', methods=['POST'])
def generate_speech_endpoint():
    print("\n--- New StyleTTS 2 Request Received ---")

    # Release the lock on the previous audio file at the start of a new request.
    try:
        if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
    except Exception as e:
        print(f"Warning: Could not unload previous audio. Error: {e}")

    text_to_speak = request.json.get('text', '')
    if not text_to_speak.strip():
        return jsonify({"error": "Input text is empty"}), 400

    print(f"Synthesizing: '{text_to_speak[:100]}...'")

    try:
        with styletts_lock: # Ensure only one synthesis happens at a time
            set_seed(SEED)
            texts = txtsplit(text_to_speak)
            audios = [styletts2importable.inference(t, global_target_style, alpha=ALPHA, beta=BETA, diffusion_steps=DIFFUSION_STEPS, embedding_scale=EMBEDDING_SCALE) for t in texts]
            full_audio = np.concatenate(audios)

        # Apply the post-processing from the Neurosync script
        processed_audio = trim_and_fade(
            full_audio,
            sample_rate=SAMPLE_RATE,
            threshold=TRIM_THRESHOLD,
            fade_duration=FADE_DURATION
        )
        print("Synthesis and processing complete.")

        # Save and play the audio (optional, but kept from our previous script)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_filepath = os.path.join(script_dir, "server_output.wav")
        sf.write(output_filepath, processed_audio, SAMPLE_RATE)
        print(f"Saved audio to: {output_filepath}")
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.load(output_filepath)
                pygame.mixer.music.play()
                print("Playing audio on server.")
        except Exception as e:
            print(f"Warning: Could not play audio. Error: {e}")

        # Return the audio file in the response
        buffer = io.BytesIO()
        sf.write(buffer, processed_audio, SAMPLE_RATE, format='WAV')
        buffer.seek(0)
        return Response(buffer.getvalue(), mimetype='audio/wav')

    except Exception as e:
        print(f"Error during synthesis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error during generation"}), 500

# --- Main Function to Start the Server ---
if __name__ == '__main__':
    try:
        pygame.mixer.init()
        print("Pygame mixer initialized successfully.")
    except Exception as e:
        print(f"Warning: Could not initialize Pygame mixer: {e}")
    
    initialize_styletts2(reference_voice_path=REFERENCE_VOICE)
    
    print(f"\n--- Starting StyleTTS 2 Server on http://{SERVER_HOST}:{SERVER_PORT} ---")
    print(f" -> Endpoint: /generate_speech (expects JSON {{'text': '...'}})")
    
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=SERVER_DEBUG)