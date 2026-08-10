# ==============================================================================
#                      Audio Client for MCP
# ==============================================================================
# This script acts as the "ears" of the system. Its sole purpose is to listen
# via the microphone, use a local Whisper model to transcribe speech, and send
# the resulting text to the MCP for filtering and reasoning.
#
# This version automatically reads the selected input device from the central
# mcp_settings.ini file.
# ==============================================================================

import collections
import queue
import sys
import wave
import os
import requests
import configparser

import numpy as np
import sounddevice as sd
import webrtcvad
import torch
from transformers import WhisperProcessor, WhisperForConditionalGeneration
from scipy.io.wavfile import read as read_wav

# --- Configuration (static values) ---
VAD_AGGRESSIVENESS = 3
SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20
FRAMES_PER_BUFFER = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)
SILENCE_THRESHOLD_S = 1.5
PRE_BUFFER_S = 0.5
WAV_FILE_NAME = "temp_audio_chunk.wav"

# --- Global State ---
audio_queue = queue.Queue()
is_recording = False
pre_buffer_frames = collections.deque(maxlen=int(PRE_BUFFER_S * SAMPLE_RATE / FRAMES_PER_BUFFER))
recorded_frames = []
silent_frames_count = 0

# --- CORE FUNCTIONS ---

def load_settings_from_ini():
    """
    Loads MCP URL and the selected audio device ID from mcp_settings.ini.
    """
    ini_path = 'mcp_settings.ini'
    print(f"AUDIO INFO: Reading configuration from {ini_path}...")
    
    if not os.path.exists(ini_path):
        sys.exit(f"FATAL ERROR: The main configuration file '{ini_path}' was not found.")
        
    config = configparser.ConfigParser()
    config.read(ini_path)
    
    settings = {}
    
    try:
        # Get the MCP URL from the [MCP] section
        host = config.get('MCP', 'host')
        port = config.get('MCP', 'port')
        # NOTE: Adjust the '/process' endpoint if your MCP server uses a different one
        settings['mcp_url'] = f"http://{host}:{port}/process"
        print(f"AUDIO INFO: MCP URL set to -> {settings['mcp_url']}")

        # Get the audio input device string from the [Audio] section
        device_string = config.get('Audio', 'selected_input')
        if not device_string or device_string.lower() == 'none':
            raise ValueError("No input device is selected in the INI file. Please run the main MCP GUI to select one.")
        
        print(f"AUDIO INFO: Found saved input device -> '{device_string}'")

        # Parse the device ID from the string format "[ID] Device Name"
        if not device_string.startswith('[') or ']' not in device_string:
            raise ValueError(f"The device string '{device_string}' is not in the expected format '[ID] Name'.")
        
        device_id_str = device_string.split(']')[0][1:]
        settings['device_id'] = int(device_id_str)

        # --- Device Validation (Crucial!) ---
        # Verify that the saved device ID is actually available on this machine
        devices = sd.query_devices()
        input_device_ids = [d['index'] for d in devices if d['max_input_channels'] > 0]
        if settings['device_id'] not in input_device_ids:
            raise ValueError(f"Saved device ID {settings['device_id']} ('{device_string}') is not a valid input device on this system.")
        
        print(f"AUDIO INFO: Successfully parsed and validated device ID -> {settings['device_id']}")

    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        sys.exit(f"FATAL ERROR: A required setting is missing from {ini_path}. Details: {e}")
    except ValueError as e:
        sys.exit(f"FATAL ERROR: Problem with the audio device setting. Details: {e}")
        
    return settings

def send_to_mcp(transcribed_text: str, mcp_url: str):
    """Packages the transcribed text and sends it to the MCP."""
    print(f"AUDIO INFO: Sending to MCP -> '{transcribed_text}'")
    payload = {
        "source": "microphone",
        "text": transcribed_text,
        "vision_context": "" # Audio client has no vision context
    }
    try:
        response = requests.post(mcp_url, json=payload, timeout=5)
        response.raise_for_status()
        print("AUDIO INFO: MCP received the task.")
    except requests.exceptions.RequestException as e:
        print(f"MCP CONNECTION ERROR: Could not connect. Is MCP running? Details: {e}")

def audio_callback(indata, frames, time, status):
    if status: print(f"Audio callback status: {status}", file=sys.stderr)
    audio_queue.put(bytes(indata))

def main():
    global is_recording, recorded_frames, silent_frames_count

    # Load all settings from the central INI file
    settings = load_settings_from_ini()
    mcp_url = settings['mcp_url']
    selected_device = settings['device_id']

    print("\nInitializing services...")
    try:
        vad = webrtcvad.Vad(VAD_AGGRESSIVENESS); print("- VAD initialized.")
        print("- Loading Whisper model...")
        model_name = "openai/whisper-base.en"
        processor = WhisperProcessor.from_pretrained(model_name)
        model = WhisperForConditionalGeneration.from_pretrained(model_name)
        print("- Whisper loaded.")
    except Exception as e:
        sys.exit(f"An error occurred during initialization: {e}")

    max_silent_frames = int(SILENCE_THRESHOLD_S * SAMPLE_RATE / FRAMES_PER_BUFFER)
    
    # Get the device name for a user-friendly startup message
    device_name = sd.query_devices(selected_device)['name']
    print(f"\n--- Audio Client Listening on '{device_name}' ---")

    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=FRAMES_PER_BUFFER, device=selected_device, dtype="int16", channels=1, callback=audio_callback):
            while True:
                frame = audio_queue.get()
                is_speech = vad.is_speech(frame, SAMPLE_RATE)

                if is_recording:
                    recorded_frames.append(frame)
                    if not is_speech and len(recorded_frames) > 10: # Check for silence after some speech
                        silent_frames_count += 1
                        if silent_frames_count > max_silent_frames:
                            print("Silence detected, processing...")
                            all_frames = list(pre_buffer_frames) + recorded_frames
                            with wave.open(WAV_FILE_NAME, 'wb') as wf:
                                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE); wf.writeframes(b''.join(all_frames))
                            
                            try:
                                sr, audio_data = read_wav(WAV_FILE_NAME)
                                audio_data = audio_data.astype(np.float32) / 32768.0
                                input_features = processor(audio_data, sampling_rate=sr, return_tensors="pt").input_features
                                predicted_ids = model.generate(input_features)
                                transcribed_text = processor.batch_decode(predicted_ids, skip_special_tokens=True)[0].strip()
                            except Exception as e:
                                print(f"Whisper transcription error: {e}")
                                transcribed_text = ""
                            
                            if transcribed_text:
                                print(f"Transcribed: '{transcribed_text}'")
                                send_to_mcp(transcribed_text, mcp_url)

                            # Reset for next utterance
                            is_recording = False
                            recorded_frames.clear()
                            pre_buffer_frames.clear()
                            silent_frames_count = 0
                            print(f"\n--- Audio Client Listening on '{device_name}' ---")
                    else:
                        silent_frames_count = 0 # Reset silence counter if speech is detected
                else:
                    pre_buffer_frames.append(frame)
                    if is_speech:
                        print("Speech detected, recording...")
                        is_recording = True
                        recorded_frames.extend(pre_buffer_frames)
    except KeyboardInterrupt:
        print("\nStopping the script.")
    except Exception as e:
        print(f"A critical error occurred: {e}")

if __name__ == "__main__":
    main()