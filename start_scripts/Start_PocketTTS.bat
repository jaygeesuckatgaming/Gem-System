@echo off
TITLE Pocket TTS Server
cd C:\Users\jayge\Documents\AI\Gem-System\pocket-tts
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate pocket-tts
call python server.py --port 13301 --voice alba
cmd /k