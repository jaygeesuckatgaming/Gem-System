@echo off
TITLE OpenCode Server
cd /d "%~dp0.."

:: Activate conda environment
call "%USERPROFILE%\miniconda3\Scripts\activate.bat"
call conda activate mcp_env_1

echo Starting OpenCode Server...
echo Server URL: http://localhost:4096
echo Press Ctrl+C to stop
echo.

opencode serve
pause
