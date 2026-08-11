@echo off
TITLE Pocket TTS Server (Official)
cd C:\Users\jayge\Documents\AI\Gem-System\pocket-tts
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate pocket-tts
call python -m pocket_tts serve --host 127.0.0.1 --port 8000
cmd /k