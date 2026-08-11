@echo off
TITLE Pocket TTS Server
cd C:\Users\jayge\Documents\AI\Gem-System\pocket-tts
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate mcp_env_1
call python server.py --port 13301 --voice alba
cmd /k