"""
Pocket TTS Server with file saving for watcher_to_face
Uses official Pocket TTS server + saves output to server_output.wav
"""
import io
import os
import wave
import numpy as np
import scipy.io.wavfile
from pathlib import Path
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import httpx

app = Flask(__name__)
CORS(app)

# Pocket TTS official server URL
POCKET_TTS_URL = os.environ.get('POCKET_TTS_URL', 'http://127.0.0.1:8000')
DEFAULT_VOICE = os.environ.get('DEFAULT_VOICE', 'alba')

@app.route('/tts', methods=['GET', 'POST'])
def tts():
    """
    Proxy to official Pocket TTS server + save to file
    """
    # Get text from request
    text = request.args.get('text', '')
    voice = request.args.get('voice', None)
    
    if not text and request.is_json:
        text = request.json.get('text', '') or request.json.get('chatmessage', '')
        voice = request.json.get('voice', voice)
    
    if not text:
        return jsonify({'error': 'No text provided'}), 400
    
    # Use default voice if not specified
    if not voice:
        voice = DEFAULT_VOICE
    
    print(f"Pocket TTS Proxy: Generating '{text[:50]}...' with voice '{voice}'")
    
    try:
        # Call official Pocket TTS server
        async def fetch_audio():
            async with httpx.AsyncClient(timeout=30) as client:
                params = {'text': text}
                if voice:
                    params['voice'] = voice
                
                response = await client.post(
                    f"{POCKET_TTS_URL}/tts",
                    data=params
                )
                return response.content
        
        # Get audio from official server
        import asyncio
        audio_data = asyncio.run(fetch_audio())
        
        # Save to file for watcher_to_face
        script_dir = Path(__file__).parent
        output_filepath = script_dir / 'server_output.wav'
        
        # Parse WAV data and save
        wav_buffer = io.BytesIO(audio_data)
        wav_buffer.seek(44)  # Skip WAV header
        audio_np = np.frombuffer(wav_buffer.read(), dtype=np.float32)
        
        # Get sample rate from WAV header
        wav_buffer.seek(0)
        with wave.open(wav_buffer, 'rb') as wf:
            sample_rate = wf.getframerate()
        
        # Resave properly
        scipy.io.wavfile.write(str(output_filepath), sample_rate, audio_np)
        print(f"Saved to: {output_filepath}")
        
        # Return audio to client
        return Response(audio_data, mimetype='audio/wav')
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'ok', 'pocket_tts_server': POCKET_TTS_URL})

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Pocket TTS Proxy Server')
    parser.add_argument('--host', default='127.0.0.1', help='Host to bind to')
    parser.add_argument('--port', type=int, default=13301, help='Port to listen on')
    parser.add_argument('--pocket-tts-url', default='http://127.0.0.1:8000', help='Official Pocket TTS server URL')
    parser.add_argument('--voice', default='alba', help='Default voice to use')
    
    args = parser.parse_args()
    
    POCKET_TTS_URL = args.pocket_tts_url
    DEFAULT_VOICE = args.voice
    
    print(f"Starting Pocket TTS Proxy on {args.host}:{args.port}")
    print(f"Official server: {POCKET_TTS_URL}")
    print(f"Default voice: {DEFAULT_VOICE}")
    print(f"Output file: server_output.wav")
    
    app.run(host=args.host, port=args.port, debug=False)
