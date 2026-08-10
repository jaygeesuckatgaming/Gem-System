@echo off
TITLE StyleTTS
cd C:\Users\jayge\Documents\AI\Gem-System\StyleTTS2
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate mcp_env_1
call python watcher.py
cmd /k