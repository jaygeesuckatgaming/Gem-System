# OpenCode Integration - Setup Guide

## What Was Implemented

Your Gem-System MCP now has full OpenCode integration! You can chat with OpenCode through your existing chat system.

## How It Works

### Chat Flow:
```
You: "opencode, look at gem_mcp.py and make a summary"
  ↓
MCP: Detects "opencode," prefix
  ↓
MCP: Sends task to OpenCode server (port 4096)
  ↓
OpenCode: Analyzes code, generates summary
  ↓
OpenCode: Calls send_results tool automatically
  ↓
send_results: POSTs to MCP webhook (/opencode/webhook)
  ↓
MCP: Broadcasts to Social Stream Ninja
  ↓
Everyone sees: "🤖 OpenCode: [summary here]"
```

## Files Added/Modified

### 1. `mcp_v2.py` - Added:
- OpenCode configuration loading
- `ask_opencode()` function - sends tasks to OpenCode
- `/opencode/webhook` route - receives results
- OpenCode command detection (`is_opencode`)
- Session tracking (`opencode_sessions` dict)

### 2. `.opencode/tools/send_results.ts` - Created:
- Custom OpenCode tool
- Automatically called when OpenCode finishes a task
- POSTs results back to MCP webhook

### 3. `mcp_settings.ini` - Added section:
```ini
[OpenCode]
enabled = false
api_url = http://localhost:4096
workspace = C:\Users\jayge\Documents\AI\Gem-System
```

## Setup Instructions

### Step 1: Enable OpenCode Integration
Edit `mcp_settings.ini`:
```ini
[OpenCode]
enabled = true
api_url = http://localhost:4096
workspace = C:\Users\jayge\Documents\AI\Gem-System
```

### Step 2: Start OpenCode Server
In a separate terminal, navigate to your project directory and run:
```bash
opencode serve --port 4096
```

### Step 3: Restart MCP Server
Restart your MCP server to load the new configuration.

### Step 4: Test It!
Send a chat message like:
- "opencode, look at gem_mcp.py and make a summary"
- "opencode, check for bugs in control_panel.py"
- "opencode, refactor the download function"

## Example Chat Commands

```
✅ "opencode, analyze the queue system in control_panel.py"
✅ "opencode, what does the twitch_music_checker do?"
✅ "opencode, find all TODO comments in mcp_v2.py"
✅ "opencode, suggest improvements for the download logic"
```

## How OpenCode Knows to Call send_results

When MCP sends a task to OpenCode, it automatically appends this instruction:
```
IMPORTANT: When you have completed this task, call the 'send_results' tool 
with session_id='...', status='success' or 'failed', and your output summary.
```

OpenCode's LLM will automatically invoke the tool when it's done working.

## Troubleshooting

### OpenCode server not responding?
```bash
# Check if server is running
curl http://localhost:4096/health

# Or list sessions
curl http://localhost:4096/session
```

### Results not appearing in chat?
1. Check MCP console for "MCP OPENCODE: Received results" message
2. Verify Social Stream is enabled and session_id is correct
3. Check that OpenCode tool is in correct location: `.opencode/tools/send_results.ts`

### Session errors?
The MCP tracks sessions in memory. If you restart MCP, old sessions are cleared (this is normal).

## What's Next?

You can now:
- Delegate coding tasks to OpenCode via chat
- Get AI analysis of your codebase
- Have OpenCode refactor code, find bugs, write documentation
- All results appear in your social stream for viewers to see!

🎉 Your AI system can now "talk" with OpenCode!
