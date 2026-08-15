@echo off
TITLE Dual Audio Player
cd /d "%~dp0.."
call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
call conda activate mcp_env_1
python dual_audio_player.py
pause
