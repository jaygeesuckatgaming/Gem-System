@echo off
TITLE Audio Player - Auto Playback
cd C:\Users\jayge\Documents\AI\Gem-System
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate mcp_env_1
call python audio_player.py
cmd /k
