"""
Pocket TTS HTTP Server with Voice Cloning Support
Works like StyleTTS2 server - provides TTS endpoint for MCP
Supports custom reference voice files for voice cloning
"""
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
import os
import io
import wave
import numpy as np
from pocket_tts import TTSModel
import torch
import configparser
from pathlib import Path

app = Flask(__name__)
CORS(app)

# Global model instance (loaded once)
tts_model = None
voice_state = None
voice_cache = {}  # Cache for multiple voices

# Load configuration
config = configparser.ConfigParser()
config_path = Path(__file__).parent / 'server_settings.ini'

print(f"Looking for config at: {config_path}")
print(f"Config file exists: {config_path.exists()}")

if config_path.exists():
    config.read(config_path)
    print(f"Loaded config from {config_path}")
    # Show all sections and keys
    for section in config.sections():
        print(f"  Section: [{section}]")
        for key, value in config.items(section):
            print(f"    {key} = {value}")
else:
    print(f"WARNING: Config file not found at {config_path}")
    print("Using default values")

def get_config_value(section, key, fallback=None):
    """Get value from config with fallback"""
    try:
        return config.get(section, key, fallback=fallback)
    except:
        return fallback

def load_model():
    """Load the TTS model (only once)"""
    global tts_model
    if tts_model is None:
        print("Loading Pocket TTS model...")
        tts_model = TTSModel.load_model()
        print("Pocket TTS model loaded!")
    return tts_model

def get_voice_state(voice_identifier):
    """
    Get or create voice state for a voice identifier.
    voice_identifier can be:
    - Pre-made voice name (e.g., 'alba', 'anna')
    - Path to .wav file for voice cloning
    - Path to .safetensors file for fast voice loading
    """
    global voice_cache
    
    # Return cached voice if available
    if voice_identifier in voice_cache:
        return voice_cache[voice_identifier]
    
    model = load_model()
    
    # Check if it's a file path
    voice_path = Path(voice_identifier)
    if voice_path.exists():
        print(f"Loading voice from file: {voice_path}")
        voice_state = model.get_state_for_audio_prompt(str(voice_path))
        print(f"Voice cloned from: {voice_path.name}")
    else:
        # Try as pre-made voice name
        print(f"Loading pre-made voice: {voice_identifier}")
        voice_state = model.get_state_for_audio_prompt(voice_identifier)
        print(f"Voice loaded: {voice_identifier}")
    
    # Cache the voice state
    voice_cache[voice_identifier] = voice_state
    return voice_state

@app.route('/tts', methods=['POST', 'GET'])
def tts():
    """
    Generate speech from text
    Supports:
    - text: The text to synthesize
    - voice: Optional voice identifier (pre-made name or file path)
    Saves output to server_output.wav for watcher_to_face.py
    """
    try:
        model = load_model()
        
        # Get parameters from request
        text = request.args.get('text', '')
        voice = request.args.get('voice', None)
        
        # Also check POST JSON body (MCP sends {"chatmessage": "..."})
        if not text and request.is_json:
            text = request.json.get('text', '') or request.json.get('chatmessage', '')
            voice = request.json.get('voice', None)
        
        # Check form data
        if not text and request.form:
            text = request.form.get('text', '') or request.form.get('chatmessage', '')
            voice = request.form.get('voice', None)
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Use default voice from config if not specified
        if not voice:
            voice = get_config_value('TTS', 'reference_voice', 'alba')
            print(f"Using default voice from config: {voice}")
        else:
            print(f"Using voice from request: {voice}")
        
        print(f"Pocket TTS: Generating speech for '{text[:50]}...' with voice '{voice}'")
        
        # Get voice state (with caching)
        voice_state = get_voice_state(voice)
        
        # Generate audio
        audio = model.generate_audio(voice_state, text)
        
        # Convert to WAV format
        audio_np = audio.numpy()
        sample_rate = model.sample_rate
        
        # Save to file for watcher_to_face.py (like StyleTTS2)
        script_dir = Path(__file__).parent
        output_filepath = script_dir / 'server_output.wav'
        
        import soundfile as sf
        # Ensure audio is in correct format (float32 in range [-1, 1])
        audio_np = audio_np.astype(np.float32)
        # Normalize to prevent clipping
        max_val = np.max(np.abs(audio_np))
        if max_val > 0:
            audio_np = audio_np / max_val * 0.95
        sf.write(str(output_filepath), audio_np, sample_rate)
        print(f"Pocket TTS: Saved audio to: {output_filepath} (sample_rate={sample_rate}, duration={len(audio_np)/sample_rate:.2f}s)")
        
        # Also return in response
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            # Convert float32 to int16
            audio_int16 = (audio_np * 32767).astype(np.int16)
            wav_file.writeframes(audio_int16.tobytes())
        
        wav_buffer.seek(0)
        print(f"Pocket TTS: Generated {len(audio_int16)/sample_rate:.2f}s of audio")
        
        return send_file(
            wav_buffer,
            mimetype='audio/wav',
            as_attachment=False,
            download_name='speech.wav'
        )
        
    except Exception as e:
        print(f"Pocket TTS Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/tts/stream', methods=['POST'])
def tts_stream():
    """Stream TTS generation (returns audio chunks)"""
    try:
        model = load_model()
        
        text = request.json.get('text', '')
        voice = request.json.get('voice', None)
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        # Use default voice from config if not specified
        if not voice:
            voice = get_config_value('TTS', 'reference_voice', 'alba')
        
        print(f"Pocket TTS: Streaming speech for '{text[:50]}...' with voice '{voice}'")
        
        # Get voice state
        voice_state = get_voice_state(voice)
        
        from flask import Response
        
        def generate():
            for chunk in model.generate_audio_stream(voice_state, text):
                audio_np = chunk.numpy()
                audio_int16 = (audio_np * 32767).astype(np.int16)
                yield audio_int16.tobytes()
        
        return Response(
            generate(),
            mimetype='audio/pcm',
            headers={
                'Content-Disposition': 'attachment; filename=speech.pcm',
                'X-Sample-Rate': str(model.sample_rate)
            }
        )
        
    except Exception as e:
        print(f"Pocket TTS Stream Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'model': 'pocket-tts'})

@app.route('/voices', methods=['GET'])
def list_voices():
    """List available pre-made voices"""
    voices = [
        'alba', 'anna', 'azelma', 'bill_boerst', 'caro_davy', 'charles',
        'cosette', 'eponine', 'eve', 'fantine', 'george', 'jane', 'jean',
        'javert', 'marius', 'mary', 'michael', 'paul', 'peter_yearsley',
        'stuart_bell', 'vera', 'giovanni', 'lola', 'juergen', 'rafael', 'estelle'
    ]
    return jsonify({'voices': voices, 'voice_cloning': True})

@app.route('/clone-voice', methods=['POST'])
def clone_voice():
    """
    Clone a voice from an uploaded audio file
    Returns voice identifier that can be used in /tts endpoint
    """
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        # Save the file temporarily
        temp_dir = Path(__file__).parent / 'temp_voices'
        temp_dir.mkdir(exist_ok=True)
        
        temp_path = temp_dir / audio_file.filename
        audio_file.save(str(temp_path))
        
        print(f"Voice cloning: Saved {audio_file.filename} to {temp_path}")
        
        # Return the path as voice identifier
        return jsonify({
            'voice': str(temp_path),
            'message': f'Voice cloned from {audio_file.filename}'
        })
        
    except Exception as e:
        print(f"Voice cloning error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Pocket TTS Server with Voice Cloning')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=13301, help='Port to listen on')
    parser.add_argument('--voice', default=None, help='Default reference voice file or pre-made voice name')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Override config voice if specified in args
    if args.voice:
        if not config.has_section('TTS'):
            config.add_section('TTS')
        config.set('TTS', 'reference_voice', args.voice)
    
    print(f"Starting Pocket TTS server on {args.host}:{args.port}")
    
    default_voice = get_config_value('TTS', 'reference_voice', 'alba')
    print(f"=" * 60)
    print(f"Default reference voice: {default_voice}")
    print(f"Config file: {config_path}")
    print(f"Voice cloning enabled: You can use any .wav file path as voice identifier")
    print(f"=" * 60)
    print("Endpoints:")
    print("  GET/POST /tts?text=...&voice=... - Generate speech (voice optional)")
    print("  POST /tts/stream - Stream speech")
    print("  POST /clone-voice - Upload audio file for voice cloning")
    print("  GET /health - Health check")
    print("  GET /voices - List available pre-made voices")
    
    # Pre-load model
    load_model()
    
    app.run(host=args.host, port=args.port, debug=args.debug)
