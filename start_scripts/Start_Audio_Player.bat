@echo off
TITLE Audio Player - Auto Playback
cd /d "%~dp0.."
call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
call conda activate mcp_env_1
python audio_player.py
pause
