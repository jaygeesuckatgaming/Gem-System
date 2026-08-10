# OpenCode API Integration for Gem-System MCP
# This module handles OpenCode API communication with tools & skills support

import httpx
import asyncio
import json
import re
from datetime import datetime


class OpenCodeIntegration:
    def __init__(self, api_url: str = "http://localhost:4096", workspace: str = None):
        self.api_url = api_url.rstrip("/")
        self.workspace = workspace or "."
        self.active_sessions = {}
        self.session_outputs = {}
    
    async def create_session(self) -> str:
        """Create a new OpenCode session."""
        async with httpx.AsyncClient(timeout=30) as client:
            # API format: { parentID?, title? }
            resp = await client.post(
                f"{self.api_url}/session",
                json={"title": f"Gem-System Task: {datetime.now().strftime('%H:%M')}"}
            )
            resp.raise_for_status()
            data = resp.json()
            session_id = data.get("id")
            print(f"OPENCODE: Created session {session_id}")
            return session_id
    
    async def send_prompt(self, session_id: str, prompt: str) -> str:
        """Send prompt as a message and wait for response."""
        print(f"OPENCODE: Sending message to session {session_id}...")
        
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{self.api_url}/session/{session_id}/message",
                json={
                    "parts": [{"type": "text", "text": prompt}]
                },
                timeout=300
            )
            resp.raise_for_status()
            data = resp.json()
            
            print(f"OPENCODE: Raw response: {json.dumps(data, indent=2)[:2000]}")
            
            # Extract output from ALL parts
            parts = data.get("parts", [])
            output_parts = []
            for part in parts:
                print(f"OPENCODE: Processing part: {json.dumps(part, indent=2)[:500]}")
                part_type = part.get("type", "")
                
                # Try to get text from various fields
                text = part.get("text", "")
                if not text:
                    text = part.get("content", "")
                if not text:
                    text = part.get("value", "")
                if not text:
                    # For tool results
                    text = json.dumps(part.get("args", part.get("result", "")))
                
                if text:
                    output_parts.append(str(text))
            
            full_output = ' '.join(output_parts).strip()
            
            # Clean up ANSI codes
            full_output = re.sub(r'\x1b\[[0-9;]*m', '', full_output)
            full_output = re.sub(r'\[0m', '', full_output)
            
            # Fix formatting - add newlines between filenames
            # Split on spaces and add newline after each item
            items = full_output.split()
            if len(items) > 1:
                full_output = '\n'.join(items)
            
            print(f"OPENCODE: Final output: {len(full_output)} chars")
            return full_output if full_output else "Task completed"
    
    async def execute_task(self, prompt: str) -> str:
        """Execute task using OpenCode API."""
        session_id = await self.create_session()
        self.active_sessions[session_id] = {
            "created": datetime.now(),
            "prompt": prompt
        }
        
        try:
            # For file listing, modify prompt to get raw output
            if "list" in prompt.lower() and ("file" in prompt.lower() or "dir" in prompt.lower()):
                enhanced_prompt = f"{prompt}\n\nShow the RAW output only. Do not summarize. List each file on a separate line."
            else:
                enhanced_prompt = prompt
            
            output = await self.send_prompt(session_id, enhanced_prompt)
            self.session_outputs[session_id] = output
            return output
        except Exception as e:
            return f"Error: {str(e)}"
        finally:
            # Clean up old sessions (keep last 10)
            if len(self.active_sessions) > 10:
                oldest = sorted(self.active_sessions.keys())[0]
                del self.active_sessions[oldest]


# Example usage for testing
async def test_opencode():
    integration = OpenCodeIntegration(
        api_url="http://localhost:4096",
        workspace="C:\\Users\\jayge\\Documents\\AI\\Gem-System"
    )
    
    print("Testing OpenCode API integration...")
    result = await integration.execute_task("list the files in this directory")
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(test_opencode())
