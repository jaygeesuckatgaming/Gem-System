@echo off
TITLE Control Panel
cd C:\Users\jayge\Documents\AI\Gem-System
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate mcp_env_1
python control_panel.py
cmd /k