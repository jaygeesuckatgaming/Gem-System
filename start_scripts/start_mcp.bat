@echo off
TITLE MCP
cd C:\Users\jayge\Documents\AI\Gem-System
call C:\Users\jayge\miniconda3\Scripts\activate.bat
call conda activate mcp_env_1
call Python mcp_v2.py
cmd /k
