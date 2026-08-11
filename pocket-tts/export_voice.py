#!/usr/bin/env python
"""
Export a voice to .safetensors format for fast loading
Usage: python export_voice.py <input_wav> <output_safetensors>
"""
import sys
from pathlib import Path
from pocket_tts import TTSModel, export_model_state

def export_voice(input_wav: str, output_safetensors: str):
    """Export voice from WAV to safetensors format"""
    print(f"Loading Pocket TTS model...")
    model = TTSModel.load_model()
    
    print(f"Processing voice file: {input_wav}")
    # Use truncate=True to handle long files properly
    voice_state = model.get_state_for_audio_prompt(input_wav, truncate=True)
    
    print(f"Exporting to: {output_safetensors}")
    export_model_state(voice_state, output_safetensors)
    
    print(f"✅ Voice exported successfully!")
    print(f"   Update your config to use: {output_safetensors}")

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        export_voice(sys.argv[1], sys.argv[2])
    else:
        # Default: export earn_lucky voice
        script_dir = Path(__file__).parent
        input_wav = script_dir.parent / "StyleTTS2/voices/earn_lucky_pitch_minus_one_samplerate_24000_short_mono.wav"
        output_safetensors = script_dir.parent / "StyleTTS2/voices/earn_lucky.safetensors"
        
        if input_wav.exists():
            export_voice(str(input_wav), str(output_safetensors))
        else:
            print(f"Error: Input file not found: {input_wav}")
            print("Usage: python export_voice.py <input.wav> <output.safetensors>")
            sys.exit(1)
