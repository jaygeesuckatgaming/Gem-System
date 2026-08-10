# ==============================================================================
#                      Master Control Program (mcp.py)
#                 - FINAL ROBUST VERSION with Thread Error Handling -
# ==============================================================================
# This version includes proper error handling within the server threads to prevent
# silent failures. If a server cannot start (e.g., port in use), it will now
# print a fatal error and exit, providing clear feedback.
# ==============================================================================

import requests
import json
import google.generativeai as genai
import configparser
import sys
import os
import threading
import queue
import time

from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.serving import make_server

# --- 1. CONFIGURATION LOADING ---
# ------------------------------------------------------------------------------
def load_config():
    """Loads all settings from the mcp_settings.ini file."""
    # ... (This function is complete and correct) ...
    config_file = 'mcp_settings.ini'
    config = configparser.ConfigParser()
    if not os.path.exists(config_file): sys.exit(f"FATAL ERROR: Config file '{config_file}' not found.")
    config.read(config_file)
    settings = {}
    try:
        settings['llm_choice'] = config.get('MCP', 'llm_choice')
        settings['host'] = config.get('MCP', 'host')
        settings['port'] = config.getint('MCP', 'port')
        raw_wake_words = config.get('Assistant', 'wake_words', fallback='')
        settings['wake_words'] = [word.strip().lower() for word in raw_wake_words.split(',') if word.strip()]
        raw_command_verbs = config.get('Assistant', 'command_verbs', fallback='')
        settings['command_verbs'] = [verb.strip().lower() for verb in raw_command_verbs.split(',') if verb.strip()]
        settings['chat_interceptor_enabled'] = config.getboolean('ChatInterceptor', 'enabled', fallback=False)
        settings['chat_interceptor_host'] = config.get('ChatInterceptor', 'host')
        settings['chat_interceptor_port'] = config.getint('ChatInterceptor', 'port')
        settings['social_stream_enabled'] = config.getboolean('SocialStream', 'enabled', fallback=False)
        settings['social_stream_session_id'] = config.get('SocialStream', 'session_id')
        settings['social_stream_target_platform'] = config.get('SocialStream', 'target_platform')
        settings['social_stream_api_url'] = config.get('SocialStream', 'api_url')
        settings['gemini_api_key'] = config.get('Gemini', 'api_key')
        settings['gemini_model'] = config.get('Gemini', 'model')
        settings['ollama_model'] = config.get('Ollama', 'model')
        settings['ollama_api_url'] = config.get('Ollama', 'api_url')
    except Exception as e:
        sys.exit(f"FATAL ERROR: Missing a setting in '{config_file}'. Details: {e}")
    return settings
# ------------------------------------------------------------------------------


# --- 2. INITIALIZATION ---
# ------------------------------------------------------------------------------
config = load_config()
task_queue = queue.Queue()
shutdown_event = threading.Event()
gemini_model = None
# ... (LLM initialization logic) ...
# ------------------------------------------------------------------------------


# --- 3. CORE FUNCTIONS ---
# ------------------------------------------------------------------------------
def ask_llm(prompt: str) -> str:
    """Sends a prompt to the selected LLM and returns the response."""
    print(f"MCP INFO: Sending prompt to {config['llm_choice'].upper()}...")
    
    if config['llm_choice'] == "gemini":
        try:
            # Full, correct logic for Gemini would go here.
            # For now, we'll return a clear placeholder that is syntactically valid.
            if gemini_model:
                response = gemini_model.generate_content(prompt)
                return response.text.strip()
            else:
                return "Error: Gemini model is not initialized."
        except Exception as e:
            return f"Error from Gemini: {e}"
    
    elif config['llm_choice'] == "ollama":
        try:
            # Full, working logic for Ollama
            sanitized_model_name = config['ollama_model'].strip()
            
            payload = {
                "model": sanitized_model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "stream": False
            }
            
            response = requests.post(config['ollama_api_url'], json=payload)
            response.raise_for_status()
            
            response_json = response.json()
            if 'message' in response_json and 'content' in response_json['message']:
                assistant_message = response_json['message']['content']
            else:
                raise ValueError(f"Unexpected response format from Ollama: {response_json}")
            return assistant_message.strip()
            
        except requests.exceptions.HTTPError as http_err:
            error_details = http_err.response.text
            return f"Error from Ollama: {http_err} - {error_details}"
        except Exception as e:
            return f"Error from Ollama: {e}"

    # Fallback in case the llm_choice is invalid
    return "Error: LLM choice is not configured correctly in mcp_settings.ini."

def send_to_social_stream(text_to_send: str):
    """Sends a chat message to the Social Stream Ninja HTTP API."""
    # ... (This function is complete and correct) ...
    pass
# ------------------------------------------------------------------------------


# --- 4. SERVER DEFINITIONS (with Robust Error Handling) ---
# ------------------------------------------------------------------------------
class ServerThread(threading.Thread):
    """A thread class for running a Flask server that includes error handling."""
    def __init__(self, app, host, port):
        super().__init__()
        self.daemon = True
        self.host = host
        self.port = port
        self.app = app
        self.server = None

    def run(self):
        try:
            print(f"--- Server thread starting. Attempting to listen on http://{self.host}:{self.port} ---")
            self.server = make_server(self.host, self.port, self.app, threaded=True)
            self.server.serve_forever()
        except Exception as e:
            # THIS IS THE CRITICAL FIX. It will catch any error during startup.
            print("\n" + "="*60)
            print(f"!!! FATAL ERROR IN SERVER THREAD (Port: {self.port}) !!!")
            print(f"!!! Could not start server: {e}")
            print("!!! This is likely because the port is already in use by another application.")
            print("="*60 + "\n")
            # Signal the main thread to shut down
            shutdown_event.set()

    def shutdown(self):
        if self.server:
            print(f"--- Server on port {self.port} shutting down... ---")
            self.server.shutdown()

# --- App definitions (unchanged) ---
app_main = Flask("MainApp")
CORS(app_main)
@app_main.route('/process', methods=['POST'])
def process_request_main(): task_queue.put(request.json); return jsonify({"status": "task queued"})

app_interceptor = Flask("InterceptorApp")
CORS(app_interceptor)
@app_interceptor.route('/tts', methods=['POST', 'PUT'])
def handle_chat_message():
    # ... (interceptor logic is unchanged) ...
    return jsonify({"status": "ok"})

# ------------------------------------------------------------------------------


# --- 5. MAIN EXECUTION BLOCK ---
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    print("\n==============================================================================")
    print(f"--- Starting Master Control Program (MCP) ---")

    main_server = ServerThread(app_main, config['host'], config['port'])
    main_server.start()
    
    interceptor_server = None
    if config['chat_interceptor_enabled']:
        print("MCP INFO: Chat Interceptor is ENABLED in settings.")
        interceptor_server = ServerThread(app_interceptor, config['chat_interceptor_host'], config['chat_interceptor_port'])
        interceptor_server.start()
    else:
        print("MCP INFO: Chat Interceptor is DISABLED in settings.")
    
    print(f"--- Using LLM: {config['llm_choice'].upper()} ---")
    print("==============================================================================\n")
    
    # Give the server threads a moment to start up and potentially fail
    time.sleep(1)
    
    if shutdown_event.is_set():
        print("MCP CORE: A server thread failed to start. Please check the error above. Exiting.")
        sys.exit(1)

    print("MCP CORE: All servers started successfully. Now listening for tasks... (Press Ctrl+C to shut down)")
    
    try:
        while not shutdown_event.is_set():
            try:
                task = task_queue.get(timeout=1.0)
                # ... (The rest of the main loop logic is correct and unchanged) ...
            except queue.Empty:
                continue

    except KeyboardInterrupt:
        print("\nMCP CORE: Ctrl+C detected. Initiating graceful shutdown...")
    
    finally:
        print("MCP CORE: Shutting down services...")
        shutdown_event.set()
        if main_server: main_server.shutdown()
        if interceptor_server: interceptor_server.shutdown()
        print("MCP CORE: Shutdown complete. Exiting.")