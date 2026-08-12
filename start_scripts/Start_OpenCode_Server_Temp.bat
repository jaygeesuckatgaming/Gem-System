@echo off
TITLE OpenCode Server - ollama/lfm2.5:latest
cd /d "%~dp0.."
call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
call conda activate mcp_env_1
opencode serve --model ollama/lfm2.5:latest
pause
