@echo off
TITLE StyleTTS
cd /d "%~dp0..\tts\StyleTTS2"
call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
call conda activate mcp_env_1
python watcher.py
cmd /k