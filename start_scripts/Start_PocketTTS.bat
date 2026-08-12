@echo off
TITLE Pocket TTS Server (Official)
cd /d "%~dp0..\tts\pocket-tts"
call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
call conda activate pocket-tts
call python -m pocket_tts serve --host 127.0.0.1 --port 13301
cmd /k