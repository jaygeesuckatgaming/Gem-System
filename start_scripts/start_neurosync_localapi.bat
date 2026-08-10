@echo off
TITLE Neuro LocalAPI
cd C:\Users\jayge\Documents\AI\Gem-System\Neurosync\NeuroSync_Local_API
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate mcp_env_1
python neurosync_local_api.py
cmd /k