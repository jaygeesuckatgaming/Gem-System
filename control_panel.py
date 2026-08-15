import tkinter as tk
from tkinter import ttk
from collections import deque
import sounddevice as sd
import numpy as np
import queue
import threading
import time
import math
import os
import configparser
import cv2
from PIL import Image, ImageTk
import traceback
import subprocess
from tkinter import messagebox
import sys
import pygame
import requests

# --- Configuration ---
MIN_DB = -60.0
MAX_DB = 0.0
SMOOTHING_FACTOR = 0.85
PEAK_HOLD_DURATION = 1.5
TEST_TONE_FREQUENCY = 440
INI_FILE_PATH = "mcp_settings.ini"
DROPDOWN_SECTION = "MCP"
DROPDOWN_KEY = "llm_choice"
DROPDOWN_OPTIONS = ["gemini", "ollama", "ollama_vision", "ollama_cloud", "minitron"]
SENSITIVE_KEYS = ["api_key", "session_id"]

class AudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Master Control Panel")
        self.geometry("1400x950")

        # Configure pygame/SDL to use the selected output device
        try:
            config = configparser.ConfigParser()
            config.read(INI_FILE_PATH)
            output_device = config.get('Audio', 'selected_output', fallback='None')
            if output_device and output_device != 'None':
                # Extract device name from "[ID] Name" format
                if ']' in output_device:
                    device_name = output_device.split('] ', 1)[1]
                    # Set SDL to use DirectSound on Windows
                    os.environ['SDL_AUDIODRIVER'] = 'directsound'
                    # Note: SDL doesn't support device selection by name easily,
                    # so we rely on Windows default device or user setting it manually
                    print(f"CONTROL PANEL: Audio output configured for: {device_name}")
        except Exception as e:
            print(f"CONTROL PANEL: Could not configure audio device: {e}")
        
        pygame.mixer.init()

        self.config = configparser.ConfigParser(interpolation=None)
        self.ini_entries = {}
        self.sensitive_values = {}
        self.input_audio_queue = queue.Queue()
        self.output_audio_queue = queue.Queue()
        self.video_frame_queue = queue.Queue()

        self.currently_playing_path = None
        self.is_paused = False
        self.song_length_seconds = 0
        self.autoplay_var = tk.BooleanVar(value=True)
        self.autodelete_var = tk.BooleanVar(value=False)
        
        self.max_queue_length = 20
        self.max_queue_var = tk.StringVar(value=str(self.max_queue_length))
        self.autoplay_queue = deque(maxlen=self.max_queue_length)
        
        self.background_song_path = None
        self.background_song_is_paused = False
        self.is_starting_new_song = False
        self.background_resume_time = 0.0
        
        self.max_duration_var = tk.StringVar(value="10") # Variable for song duration UI

        self.input_stream = None
        self.output_stream = None
        self.is_testing_output = False
        self.output_start_idx = 0
        self.input_smoothed_db = MIN_DB
        self.input_peak_db = MIN_DB
        self.input_peak_hold_time = 0
        self.output_smoothed_db = MIN_DB
        self.output_peak_db = MIN_DB
        self.output_peak_hold_time = 0
        self.vision_thread = None
        self.stop_vision_thread = False
        
        self.music_downloader_enabled_var = tk.BooleanVar(value=True)
        self.send_to_social_stream_var = tk.BooleanVar(value=True)
        self.streaming_platform_var = tk.StringVar(value="youtube")
        
        # Audio ducking settings
        self.ducking_enabled_var = tk.BooleanVar(value=False)
        self.ducking_amount_var = tk.StringVar(value="-15")
        self.ducking_attack_var = tk.StringVar(value="100")
        self.ducking_release_var = tk.StringVar(value="500")
        self.ducking_active = False
        self.last_ducking_check = 0

        self.create_widgets()
        self.populate_device_lists()
        self.populate_camera_list()
        self.load_tts_settings()
        self.load_ducking_settings()
        self.reload_ini_ui()
        self.process_audio_queues()
        self.process_video_queue()
        self.update_song_progress()
        self.check_for_autoplay()
        self.check_ducking_signal()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        audio_ini_tab = ttk.Frame(notebook)
        notebook.add(audio_ini_tab, text="Audio & General Settings")

        vision_tab = ttk.Frame(notebook)
        notebook.add(vision_tab, text="Vision Settings")

        neurosync_tab = ttk.Frame(notebook)
        notebook.add(neurosync_tab, text="Neurosync Settings")

        tts_tab = ttk.Frame(notebook)
        notebook.add(tts_tab, text="TTS Settings")

        music_requests_tab = ttk.Frame(notebook)
        notebook.add(music_requests_tab, text="Music Requests")

        # Add new placeholder tabs
        memory_tab = ttk.Frame(notebook)
        notebook.add(memory_tab, text="Memory")

        osc_tab = ttk.Frame(notebook)
        notebook.add(osc_tab, text="OSC")

        opencode_tab = ttk.Frame(notebook)
        notebook.add(opencode_tab, text="OpenCode")

        # Tab 9: LLM Settings
        llm_tab = ttk.Frame(notebook)
        notebook.add(llm_tab, text="LLM")

        main_paned_window = tk.PanedWindow(audio_ini_tab, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bd=2)
        main_paned_window.pack(fill="both", expand=True)
        left_panel = ttk.Frame(main_paned_window)
        right_panel = ttk.Frame(main_paned_window)
        main_paned_window.add(left_panel, width=450, minsize=400)
        main_paned_window.add(right_panel, minsize=500)
        input_frame = ttk.LabelFrame(left_panel, text="Microphone Input (AI Hearing)", padding=(10, 5))
        input_frame.pack(fill="x", expand=False)
        output_frame = ttk.LabelFrame(left_panel, text="Audio Output (AI Speech)", padding=(10, 5))
        output_frame.pack(pady=10, fill="x", expand=False)

        self.setup_input_widgets(input_frame)
        self.setup_output_widgets(output_frame)
        self.setup_ini_widgets(right_panel)
        self.setup_vision_widgets(vision_tab)
        self.setup_neurosync_widgets(neurosync_tab)
        self.setup_tts_widgets(tts_tab)
        self.setup_music_requests_widgets(music_requests_tab)
        self.setup_memory_widgets(memory_tab)
        self.setup_osc_widgets(osc_tab)
        self.setup_opencode_widgets(opencode_tab)
        self.setup_llm_widgets(llm_tab)

    def setup_memory_widgets(self, parent_frame):
        """Setup Memory tab with RAG, Database, and memory configuration"""
        # RAG Settings frame
        rag_frame = ttk.LabelFrame(parent_frame, text="RAG (Retrieval-Augmented Generation)", padding=15)
        rag_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(rag_frame, text="RAG Trigger Words:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.rag_trigger_words_var = tk.StringVar(value="remember, what did, what was, who did, tell me about, search for")
        rag_entry = ttk.Entry(rag_frame, textvariable=self.rag_trigger_words_var, width=60)
        rag_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(rag_frame, text="Comma-separated phrases that trigger memory search").grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        # Database Settings frame
        db_frame = ttk.LabelFrame(parent_frame, text="Database Configuration", padding=15)
        db_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(db_frame, text="Vector Extension Filename:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.vec_extension_var = tk.StringVar(value="vec0.dll")
        db_entry = ttk.Entry(db_frame, textvariable=self.vec_extension_var, width=40)
        db_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(db_frame, text="SQLite vector extension file (e.g., vec0.dll)").grid(row=1, column=1, sticky="w", padx=5, pady=2)
        
        # Cognee/Memory Settings frame
        memory_frame = ttk.LabelFrame(parent_frame, text="Memory System", padding=15)
        memory_frame.pack(fill="x", padx=20, pady=10)
        
        self.cognee_enabled_var = tk.BooleanVar(value=False)
        cognee_check = ttk.Checkbutton(memory_frame, text="Enable Cognee Memory System", variable=self.cognee_enabled_var)
        cognee_check.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        # Save button
        save_btn = ttk.Button(parent_frame, text="Save Memory & Database Settings", command=self.save_memory_settings)
        save_btn.pack(pady=15)
        
        # Info text
        info_text = """
Memory Features:
• RAG - Retrieves memories based on trigger words
• Database - SQLite with vector extension for similarity search
• Cognee - Advanced memory graph system (optional)
• ChromaDB - Vector database for memory storage

RAG Trigger Words Examples:
"remember when...", "what did I say about...", "tell me about..."
"""
        ttk.Label(parent_frame, text=info_text, justify="left", font=('TkDefaultFont', 9)).pack(pady=10, padx=20)
        
        # Load initial values
        self.load_memory_settings()
    
    def setup_osc_widgets(self, parent_frame):
        """Setup OSC tab with OSC configuration"""
        # OSC Settings frame
        osc_frame = ttk.LabelFrame(parent_frame, text="OSC Configuration", padding=15)
        osc_frame.pack(fill="x", padx=20, pady=10)
        
        # OSC Enabled
        self.osc_enabled_var = tk.BooleanVar(value=False)
        osc_check = ttk.Checkbutton(osc_frame, text="Enable OSC", variable=self.osc_enabled_var)
        osc_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        
        # OSC IP
        ttk.Label(osc_frame, text="OSC IP Address:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.osc_ip_var = tk.StringVar(value="127.0.0.1")
        osc_ip_entry = ttk.Entry(osc_frame, textvariable=self.osc_ip_var, width=30)
        osc_ip_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # OSC Port
        ttk.Label(osc_frame, text="OSC Port:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.osc_port_var = tk.StringVar(value="10000")
        osc_port_entry = ttk.Entry(osc_frame, textvariable=self.osc_port_var, width=10)
        osc_port_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        # OSC Address
        ttk.Label(osc_frame, text="OSC Address:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.osc_address_var = tk.StringVar(value="/chat/message")
        osc_address_entry = ttk.Entry(osc_frame, textvariable=self.osc_address_var, width=30)
        osc_address_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        # VMagicMirror integration
        vm_frame = ttk.LabelFrame(parent_frame, text="VMagicMirror Integration", padding=15)
        vm_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(vm_frame, text="OSC sends blendshape data to VMagicMirror for lip-sync.",
                 font=('TkDefaultFont', 9)).pack(pady=5)
        
        # Save button
        save_btn = ttk.Button(parent_frame, text="Save OSC Settings", command=self.save_osc_settings)
        save_btn.pack(pady=10)
        
        # Load initial values
        self.load_osc_settings()
    
    def setup_opencode_widgets(self, parent_frame):
        """Setup OpenCode tab with server controls"""
        # OpenCode Server Control frame
        server_frame = ttk.LabelFrame(parent_frame, text="OpenCode Server Control", padding=15)
        server_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(server_frame, text="OpenCode Server Status:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.opencode_status_var = tk.StringVar(value="Not Running")
        status_label = ttk.Label(server_frame, textvariable=self.opencode_status_var, foreground="gray")
        status_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(server_frame, text="Server URL:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.opencode_url_var = tk.StringVar(value="http://localhost:4096")
        url_entry = ttk.Entry(server_frame, textvariable=self.opencode_url_var, width=40)
        url_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # LLM Model selection
        ttk.Label(server_frame, text="LLM Model:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.opencode_model_var = tk.StringVar(value="ollama/gemma3:4b-it-qat")
        model_entry = ttk.Entry(server_frame, textvariable=self.opencode_model_var, width=40)
        model_entry.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(server_frame, text="Format: provider/model (e.g., ollama/gemma3:4b-it-qat)", 
                 font=('TkDefaultFont', 8), foreground="gray").grid(row=3, column=1, sticky="w", padx=5, pady=2)
        
        # Launch button
        launch_btn = ttk.Button(server_frame, text="Start OpenCode Server", command=self.run_opencode_server)
        launch_btn.grid(row=4, column=1, sticky="w", padx=5, pady=10)
        
        # Save button
        save_btn = ttk.Button(server_frame, text="Save Model Settings", command=self.save_opencode_settings)
        save_btn.grid(row=4, column=0, sticky="w", padx=5, pady=10)
        
        self.opencode_model_var.trace_add("write", lambda *args: self.save_opencode_settings())
        
        # Configuration frame
        config_frame = ttk.LabelFrame(parent_frame, text="OpenCode Configuration", padding=15)
        config_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Info text
        info_text = """
OpenCode Integration:
• Browser automation via Chrome DevTools MCP
• Web navigation and interaction
• Content extraction and analysis
• Used for research and data gathering

Server Info:
• Default URL: http://localhost:4096
• Uses Chrome DevTools MCP protocol
• Requires Chrome browser running

Model Options:
• ollama/gemma3:4b-it-qat - Local Ollama
• ollama/llama3:70b - Local Ollama Llama 3
• opencode/gpt-5.1-codex - OpenCode Zen
• anthropic/claude-sonnet-4-5-20250929 - Anthropic
"""
        ttk.Label(parent_frame, text=info_text, justify="left", font=('TkDefaultFont', 9)).pack(pady=10, padx=20)
        
        # Load settings
        self.load_opencode_settings()
    
    def setup_llm_widgets(self, parent_frame):
        """Setup LLM tab with LLM model selection and configuration"""
        # LLM Selection frame
        llm_select_frame = ttk.LabelFrame(parent_frame, text="LLM Model Selection", padding=15)
        llm_select_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(llm_select_frame, text="Select LLM Provider:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        self.llm_choice_var = tk.StringVar(value="ollama")
        llm_options = ["gemini", "ollama", "ollama_vision", "ollama_cloud", "minitron"]
        llm_combo = ttk.Combobox(llm_select_frame, textvariable=self.llm_choice_var, values=llm_options, state="readonly", width=20)
        llm_combo.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        llm_combo.bind("<<ComboboxSelected>>", lambda e: self.save_llm_settings())
        
        # API Keys frame
        api_frame = ttk.LabelFrame(parent_frame, text="API Keys", padding=15)
        api_frame.pack(fill="x", padx=20, pady=10)
        
        # Gemini API Key
        ttk.Label(api_frame, text="Gemini API Key:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.gemini_api_key_var = tk.StringVar()
        gemini_entry = ttk.Entry(api_frame, textvariable=self.gemini_api_key_var, show="*", width=40)
        gemini_entry.grid(row=0, column=1, padx=5, pady=5)
        
        # Ollama Cloud API Key
        ttk.Label(api_frame, text="Ollama Cloud API Key:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.ollama_cloud_api_key_var = tk.StringVar()
        ollama_cloud_entry = ttk.Entry(api_frame, textvariable=self.ollama_cloud_api_key_var, show="*", width=40)
        ollama_cloud_entry.grid(row=1, column=1, padx=5, pady=5)
        
        # Model URLs frame
        url_frame = ttk.LabelFrame(parent_frame, text="Model URLs", padding=15)
        url_frame.pack(fill="x", padx=20, pady=10)
        
        # Ollama API URL and Model
        ttk.Label(url_frame, text="Ollama API URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.ollama_api_url_var = tk.StringVar(value="http://localhost:11434/api/chat")
        ollama_url_entry = ttk.Entry(url_frame, textvariable=self.ollama_api_url_var, width=50)
        ollama_url_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(url_frame, text="Local Ollama Model:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.ollama_model_var = tk.StringVar(value="gemma3:4b-it-qat")
        ollama_model_entry = ttk.Entry(url_frame, textvariable=self.ollama_model_var, width=30)
        ollama_model_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Ollama Cloud API URL and Model
        ttk.Label(url_frame, text="Ollama Cloud API URL:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.ollama_cloud_api_url_var = tk.StringVar(value="https://ollama.com/api/chat")
        ollama_cloud_url_entry = ttk.Entry(url_frame, textvariable=self.ollama_cloud_api_url_var, width=50)
        ollama_cloud_url_entry.grid(row=2, column=1, padx=5, pady=5)
        
        ttk.Label(url_frame, text="Ollama Cloud Model:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.ollama_cloud_model_var = tk.StringVar(value="gemma4:31b-cloud")
        ollama_cloud_model_entry = ttk.Entry(url_frame, textvariable=self.ollama_cloud_model_var, width=30)
        ollama_cloud_model_entry.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        # MCP Configuration section
        mcp_frame = ttk.LabelFrame(parent_frame, text="MCP Server Configuration", padding=15)
        mcp_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(mcp_frame, text="MCP Host:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.mcp_host_var = tk.StringVar(value="127.0.0.1")
        mcp_host_entry = ttk.Entry(mcp_frame, textvariable=self.mcp_host_var, width=20)
        mcp_host_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(mcp_frame, text="MCP Port:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.mcp_port_var = tk.StringVar(value="5000")
        mcp_port_entry = ttk.Entry(mcp_frame, textvariable=self.mcp_port_var, width=10)
        mcp_port_entry.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Assistant Configuration section
        assistant_frame = ttk.LabelFrame(parent_frame, text="Assistant Configuration", padding=15)
        assistant_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(assistant_frame, text="Wake Words:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.wake_words_var = tk.StringVar(value="Gem, Jen, Jim, @GemChadee")
        wake_words_entry = ttk.Entry(assistant_frame, textvariable=self.wake_words_var, width=50)
        wake_words_entry.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(assistant_frame, text="Command Verbs:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.command_verbs_var = tk.StringVar(value="go, move, navigate, look, turn, get, grab, put")
        command_verbs_entry = ttk.Entry(assistant_frame, textvariable=self.command_verbs_var, width=50)
        command_verbs_entry.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(assistant_frame, text="Max Response Length:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.max_response_length_var = tk.StringVar(value="2000")
        response_length_spinbox = ttk.Spinbox(assistant_frame, textvariable=self.max_response_length_var, from_=100, to=10000, width=10)
        response_length_spinbox.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        # System Prompt section
        system_prompt_frame = ttk.LabelFrame(parent_frame, text="System Prompt (LLM Persona)", padding=15)
        system_prompt_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        ttk.Label(system_prompt_frame, text="This defines the AI's personality and behavior:").pack(anchor="w", pady=(0, 5))
        self.system_prompt_var = tk.StringVar(value="You are Gem. Your persona is a 35-year-old human woman from Pattaya, Thailand, who is a guest on a YouTube live stream.")
        system_prompt_text = tk.Text(system_prompt_frame, height=20, width=100, wrap=tk.WORD, font=('Consolas', 10))
        system_prompt_text.pack(fill="both", expand=True)
        system_prompt_text.insert("1.0", self.system_prompt_var.get())
        self.system_prompt_widget = system_prompt_text
        
        # Save button
        save_btn = ttk.Button(parent_frame, text="Save LLM, MCP, Assistant & System Prompt Settings", command=self.save_llm_settings)
        save_btn.pack(pady=15)
        
        # Info text
        info_text = """
LLM Providers:
• gemini - Google Gemini API
• ollama - Local Ollama server (configure model in Ollama section below)
• ollama_vision - Ollama with vision capabilities
• ollama_cloud - Ollama cloud service (default: gemma4:31b-cloud)
• minitron - Minitron model

Popular Ollama Cloud Models:
• gemma4:31b-cloud - Google Gemma 4 31B
• llama3:70b - Meta Llama 3 70B
• qwen2.5:72b - Alibaba Qwen 2.5 72B
"""
        ttk.Label(parent_frame, text=info_text, justify="left", font=('TkDefaultFont', 9)).pack(pady=10, padx=20)
        
        # Load initial values
        self.load_llm_settings()
    
    def load_llm_settings(self):
        """Load LLM, MCP, Assistant, and System Prompt settings from mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            
            # Load LLM choice
            if self.config.has_section('MCP'):
                llm_choice = self.config.get('MCP', 'llm_choice', fallback='ollama')
                self.llm_choice_var.set(llm_choice)
                
                # Load MCP settings
                mcp_host = self.config.get('MCP', 'host', fallback='127.0.0.1')
                self.mcp_host_var.set(mcp_host)
                
                mcp_port = self.config.get('MCP', 'port', fallback='5000')
                self.mcp_port_var.set(mcp_port)
            
            # Load Assistant settings
            if self.config.has_section('Assistant'):
                wake_words = self.config.get('Assistant', 'wake_words', fallback='Gem, Jen, Jim, @GemChadee')
                self.wake_words_var.set(wake_words)
                
                command_verbs = self.config.get('Assistant', 'command_verbs', fallback='go, move, navigate, look, turn, get, grab, put')
                self.command_verbs_var.set(command_verbs)
                
                max_response_length = self.config.get('Assistant', 'max_response_length', fallback='2000')
                self.max_response_length_var.set(max_response_length)
            
            # Load System Prompt
            if self.config.has_section('SystemPrompt'):
                system_prompt = self.config.get('SystemPrompt', 'prompt', fallback='You are Gem.')
                self.system_prompt_var.set(system_prompt)
                if hasattr(self, 'system_prompt_widget'):
                    self.system_prompt_widget.delete("1.0", tk.END)
                    self.system_prompt_widget.insert("1.0", system_prompt)
            
            # Load API keys
            if self.config.has_section('Gemini'):
                api_key = self.config.get('Gemini', 'api_key', fallback='')
                self.gemini_api_key_var.set(api_key)
            
            if self.config.has_section('OllamaCloud'):
                api_key = self.config.get('OllamaCloud', 'api_key', fallback='')
                self.ollama_cloud_api_key_var.set(api_key)
            
            # Load API URLs
            if self.config.has_section('Ollama'):
                api_url = self.config.get('Ollama', 'api_url', fallback='http://localhost:11434/api/chat')
                self.ollama_api_url_var.set(api_url)
                
                # Load local Ollama model
                ollama_model = self.config.get('Ollama', 'model', fallback='gemma3:4b-it-qat')
                self.ollama_model_var.set(ollama_model)
            
            if self.config.has_section('OllamaCloud'):
                api_url = self.config.get('OllamaCloud', 'api_url', fallback='https://ollama.com/api/chat')
                self.ollama_cloud_api_url_var.set(api_url)
                
                # Load Ollama Cloud model
                ollama_cloud_model = self.config.get('OllamaCloud', 'model', fallback='gemma4:31b-cloud')
                self.ollama_cloud_model_var.set(ollama_cloud_model)
                
        except Exception as e:
            print(f"CONTROL PANEL: Could not load LLM settings: {e}")
    
    def save_llm_settings(self):
        """Save LLM, MCP, Assistant, and System Prompt settings to mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            
            # Save LLM choice and MCP settings
            if not self.config.has_section('MCP'):
                self.config.add_section('MCP')
            self.config.set('MCP', 'llm_choice', self.llm_choice_var.get())
            self.config.set('MCP', 'host', self.mcp_host_var.get())
            self.config.set('MCP', 'port', self.mcp_port_var.get())
            
            # Save Assistant settings
            if not self.config.has_section('Assistant'):
                self.config.add_section('Assistant')
            self.config.set('Assistant', 'wake_words', self.wake_words_var.get())
            self.config.set('Assistant', 'command_verbs', self.command_verbs_var.get())
            self.config.set('Assistant', 'max_response_length', self.max_response_length_var.get())
            
            # Save System Prompt
            if not self.config.has_section('SystemPrompt'):
                self.config.add_section('SystemPrompt')
            # Get text from Text widget
            system_prompt_text = self.system_prompt_widget.get("1.0", tk.END).strip()
            self.config.set('SystemPrompt', 'prompt', system_prompt_text)
            
            # Save API keys
            if not self.config.has_section('Gemini'):
                self.config.add_section('Gemini')
            self.config.set('Gemini', 'api_key', self.gemini_api_key_var.get())
            
            if not self.config.has_section('OllamaCloud'):
                self.config.add_section('OllamaCloud')
            self.config.set('OllamaCloud', 'api_key', self.ollama_cloud_api_key_var.get())
            
            # Save API URLs and Models
            if not self.config.has_section('Ollama'):
                self.config.add_section('Ollama')
            self.config.set('Ollama', 'api_url', self.ollama_api_url_var.get())
            self.config.set('Ollama', 'model', self.ollama_model_var.get())
            
            if not self.config.has_section('OllamaCloud'):
                self.config.add_section('OllamaCloud')
            self.config.set('OllamaCloud', 'api_url', self.ollama_cloud_api_url_var.get())
            self.config.set('OllamaCloud', 'model', self.ollama_cloud_model_var.get())
            
            with open("mcp_settings.ini", "w") as f:
                self.config.write(f)
            
            messagebox.showinfo("Success", "LLM, MCP, Assistant and System Prompt settings saved to mcp_settings.ini!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save LLM settings:\n{e}")
    
    def load_music_settings(self):
        """Load Music Downloader settings from mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            if self.config.has_section('MusicDownloader'):
                downloader_enabled = self.config.getboolean('MusicDownloader', 'enabled', fallback=True)
                self.music_downloader_enabled_var.set(downloader_enabled)
                
                queue_length_str = self.config.get('MusicDownloader', 'max_queue_length', fallback='20')
                self.max_queue_var.set(queue_length_str)
                
                duration_seconds_str = self.config.get('MusicDownloader', 'max_download_duration_seconds', fallback='600')
                duration_minutes = int(duration_seconds_str) // 60
                self.max_duration_var.set(str(duration_minutes))
            else:
                self.music_downloader_enabled_var.set(True)
                self.max_queue_var.set('20')
                self.max_duration_var.set('10')
        except Exception as e:
            print(f"CONTROL PANEL: Could not load music settings: {e}")
    
    def load_memory_settings(self):
        """Load Memory, RAG, and Database settings from mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            
            # Load RAG settings
            if self.config.has_section('RAG'):
                rag_triggers = self.config.get('RAG', 'rag_trigger_words', fallback='remember, what did, what was, who did, tell me about, search for')
                self.rag_trigger_words_var.set(rag_triggers)
            
            # Load Database settings
            if self.config.has_section('Database'):
                vec_extension = self.config.get('Database', 'vec_extension_filename', fallback='vec0.dll')
                self.vec_extension_var.set(vec_extension)
            
            # Load Cognee settings
            if self.config.has_section('Memory'):
                cognee_enabled = self.config.getboolean('Memory', 'cognee_enabled', fallback=False)
                self.cognee_enabled_var.set(cognee_enabled)
                
        except Exception as e:
            print(f"CONTROL PANEL: Could not load memory settings: {e}")
    
    def save_memory_settings(self):
        """Save Memory, RAG, and Database settings to mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            
            # Save RAG settings
            if not self.config.has_section('RAG'):
                self.config.add_section('RAG')
            self.config.set('RAG', 'rag_trigger_words', self.rag_trigger_words_var.get())
            
            # Save Database settings
            if not self.config.has_section('Database'):
                self.config.add_section('Database')
            self.config.set('Database', 'vec_extension_filename', self.vec_extension_var.get())
            
            # Save Memory/Cognee settings
            if not self.config.has_section('Memory'):
                self.config.add_section('Memory')
            self.config.set('Memory', 'cognee_enabled', str(self.cognee_enabled_var.get()))
            
            with open("mcp_settings.ini", "w") as f:
                self.config.write(f)
            
            messagebox.showinfo("Success", "Memory and Database settings saved to mcp_settings.ini!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save memory settings:\n{e}")
    
    def save_music_settings(self):
        """Save Music Downloader settings to mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            
            if not self.config.has_section('MusicDownloader'):
                self.config.add_section('MusicDownloader')
            
            music_downloader_enabled_state = self.music_downloader_enabled_var.get()
            self.config.set('MusicDownloader', 'enabled', str(music_downloader_enabled_state).lower())
            
            duration_minutes = int(self.max_duration_var.get())
            duration_seconds = duration_minutes * 60
            self.config.set('MusicDownloader', 'max_download_duration_seconds', str(duration_seconds))
            self.config.set('MusicDownloader', 'max_queue_length', self.max_queue_var.get())
            
            with open("mcp_settings.ini", "w") as f:
                self.config.write(f)
            
            messagebox.showinfo("Success", "Music settings saved to mcp_settings.ini!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save music settings:\n{e}")
    
    def setup_music_requests_widgets(self, parent_frame):
        downloader_frame = ttk.LabelFrame(parent_frame, text="Song Requests", padding=10)
        downloader_frame.pack(fill="x", padx=10, pady=10)

        top_row_frame = ttk.Frame(downloader_frame)
        top_row_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        
        streaming_platform_frame = ttk.Frame(top_row_frame)
        streaming_platform_frame.pack(side="left")
        ttk.Label(streaming_platform_frame, text="Streaming Platform:").pack(side="left", padx=(0, 5))
        platform_combobox = ttk.Combobox(
            streaming_platform_frame,
            textvariable=self.streaming_platform_var,
            values=["youtube", "twitch", "both"],
            state="readonly",
            width=10
        )
        platform_combobox.pack(side="left")
        platform_combobox.bind("<<ComboboxSelected>>", self.on_platform_change)
        
        warning_text = "(Use at your own risk, this can break the TOS for your site)"
        warning_label = ttk.Label(top_row_frame, text=warning_text, foreground="red")
        warning_label.pack(side="left", padx=(20, 10))

        top_right_controls_frame = ttk.Frame(top_row_frame)
        top_right_controls_frame.pack(side="right")

        save_music_settings_button = ttk.Button(
            top_right_controls_frame,
            text="Save Music Settings",
            command=self.save_music_settings
        )
        save_music_settings_button.pack(side="left", padx=(0, 10))

        ttk.Label(top_right_controls_frame, text="Max Duration (min):").pack(side="left", padx=(10, 2))
        duration_spinbox = ttk.Spinbox(
            top_right_controls_frame,
            from_=1,
            to=60,
            textvariable=self.max_duration_var,
            width=5
        )
        duration_spinbox.pack(side="left")

        enable_check = ttk.Checkbutton(
            downloader_frame,
            text="Enable Music Request System",
            variable=self.music_downloader_enabled_var
        )
        enable_check.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        
        # Load initial values
        self.load_music_settings()

        ttk.Label(downloader_frame, text="Song Title:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.song_title_entry = ttk.Entry(downloader_frame, width=40)
        self.song_title_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(downloader_frame, text="Artist:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.artist_entry = ttk.Entry(downloader_frame, width=40)
        self.artist_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        downloader_frame.grid_columnconfigure(1, weight=1)

        self.download_button = ttk.Button(downloader_frame, text="Find and Download MP3", command=self.start_music_download)
        self.download_button.grid(row=1, column=2, rowspan=2, padx=10, pady=5, sticky="nsew")

        player_frame = ttk.LabelFrame(parent_frame, text="Music Player", padding=10)
        player_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ttk.Label(player_frame, text="Select Song:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.song_combobox = ttk.Combobox(player_frame, state="readonly", width=50)
        self.song_combobox.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        refresh_button = ttk.Button(player_frame, text="Refresh List", command=self.populate_song_list)
        refresh_button.grid(row=0, column=3, padx=5, pady=5)
        
        controls_frame = ttk.Frame(player_frame)
        controls_frame.grid(row=1, column=0, columnspan=4, pady=5)
        self.play_button = ttk.Button(controls_frame, text="Play", command=self.play_song)
        self.play_button.pack(side="left", padx=5)
        self.pause_button = ttk.Button(controls_frame, text="Pause", command=self.pause_song)
        self.pause_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(controls_frame, text="Stop", command=self.stop_song)
        self.stop_button.pack(side="left", padx=5)
        autoplay_check = ttk.Checkbutton(controls_frame, text="Autoplay after download", variable=self.autoplay_var)
        autoplay_check.pack(side="left", padx=10)
        autodelete_check = ttk.Checkbutton(controls_frame, text="Delete after playing", variable=self.autodelete_var)
        autodelete_check.pack(side="left", padx=5)
        ttk.Label(controls_frame, text="Max Queue Size:").pack(side="left", padx=(15, 5))
        queue_spinbox = ttk.Spinbox(controls_frame, from_=1, to=100, textvariable=self.max_queue_var, width=5)
        queue_spinbox.pack(side="left")
        
        self.now_playing_label = ttk.Label(player_frame, text="Now Playing: None")
        self.now_playing_label.grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=(5,0))
        self.time_label = ttk.Label(player_frame, text="Time Remaining: --:--")
        self.time_label.grid(row=3, column=0, columnspan=4, sticky="w", padx=5)

        ttk.Label(player_frame, text="Background Song:").grid(row=4, column=0, padx=5, pady=(10, 5), sticky="w")
        self.background_song_combobox = ttk.Combobox(player_frame, state="readonly", width=50)
        self.background_song_combobox.grid(row=4, column=1, columnspan=2, padx=5, pady=(10, 5), sticky="ew")
        
        bg_controls_frame = ttk.Frame(player_frame)
        bg_controls_frame.grid(row=4, column=3, padx=5, pady=(10, 5), sticky="w")
        
        bg_refresh_button = ttk.Button(bg_controls_frame, text="Refresh", command=self.populate_background_song_list)
        bg_refresh_button.pack(side="left", padx=5)
        set_bg_button = ttk.Button(bg_controls_frame, text="Set", command=self.set_as_background_song)
        set_bg_button.pack(side="left")
        stop_bg_button = ttk.Button(bg_controls_frame, text="Stop BG", command=self.stop_background_song)
        stop_bg_button.pack(side="left", padx=5)

        player_frame.grid_columnconfigure(1, weight=1)

        log_frame = ttk.LabelFrame(parent_frame, text="Download Log", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.download_log = tk.Text(log_frame, height=10, state="disabled", bg="#f0f0f0")
        self.download_log.pack(fill="both", expand=True)

        self.populate_song_list()
        self.populate_background_song_list()

    def populate_background_song_list(self):
        bg_dir = "background_songs"
        if not os.path.isdir(bg_dir):
            try: os.makedirs(bg_dir)
            except OSError: pass
        
        self.background_song_combobox.set('')
        self.background_song_combobox['values'] = []

        songs = sorted([f for f in os.listdir(bg_dir) if f.endswith('.mp3')])
        
        self.background_song_combobox['values'] = songs
        
        if songs:
            self.background_song_combobox.current(0)
        else:
            self.background_song_combobox.set("No background songs found")

    def set_as_background_song(self):
        selected_song = self.background_song_combobox.get()
        if not selected_song or "No background songs found" in selected_song:
            messagebox.showwarning("No Song Selected", "Please select a song from the background music list to set.")
            return

        self.background_song_path = os.path.join("background_songs", selected_song)
        if not os.path.exists(self.background_song_path):
            messagebox.showerror("File Not Found", f"The song '{selected_song}' could not be found.")
            self.background_song_path = None
            return

        print(f"PLAYER: Set '{selected_song}' as the background track.")

        if not pygame.mixer.music.get_busy():
            self.background_song_is_paused = False
            pygame.mixer.music.load(self.background_song_path)
            pygame.mixer.music.play(loops=-1)
            self.currently_playing_path = self.background_song_path
            self.now_playing_label.config(text=f"Background: {os.path.basename(self.background_song_path)}")
            self.time_label.config(text="Time Remaining: ∞ (Looping)")
            self.is_starting_new_song = True

    def start_music_download(self):
        song = self.song_title_entry.get().strip()
        artist = self.artist_entry.get().strip()
        if not song and not artist:
            messagebox.showwarning("Empty Search", "Please enter at least a song title or an artist.")
            return

        query = " ".join(filter(None, [song, artist]))
        MCP_HOST = self.config.get('MCP', 'host', fallback="127.0.0.1")
        MCP_PORT = self.config.get('MCP', 'port', fallback="5000")
        api_url = f"http://{MCP_HOST}:{MCP_PORT}/add_to_download_queue"

        log_message = f"Sending request to download: '{query}' to {api_url}\n" + "-"*50 + "\n"
        self.download_log.config(state="normal")
        self.download_log.delete("1.0", tk.END)
        self.download_log.insert(tk.END, log_message)
        self.download_log.see(tk.END)
        self.download_log.config(state="disabled")
        self.download_button.config(state="disabled")

        threading.Thread(target=self.send_download_request, args=(api_url, query), daemon=True).start()

    def on_platform_change(self, event=None):
        platform = self.streaming_platform_var.get()
        MCP_HOST = self.config.get('MCP', 'host', fallback="127.0.0.1")
        MCP_PORT = self.config.get('MCP', 'port', fallback="5000")
        api_url = f"http://{MCP_HOST}:{MCP_PORT}/set_streaming_platform"
        
        try:
            payload = {"platform": platform}
            response = requests.post(api_url, json=payload, timeout=3)
            if response.status_code == 200:
                print(f"CONTROL PANEL: Streaming platform set to '{platform}'")
            else:
                print(f"CONTROL PANEL: Failed to set platform. Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"CONTROL PANEL WARNING: Could not set streaming platform. MCP may not be running. Error: {e}")
        except Exception as e:
            print(f"CONTROL PANEL ERROR: {e}")

    def send_download_request(self, url, query):
        try:
            payload = {"query": query}
            response = requests.post(url, json=payload, timeout=10)
            log_update = "Successfully added to the download queue.\n" if response.status_code == 200 else f"Error: Server responded with status {response.status_code}\nResponse: {response.text}\n"
        except requests.exceptions.RequestException as e:
            log_update = f"!!! CRITICAL ERROR: Could not connect to the MCP API.\nMake sure the Flask server is running on {url}\nError details: {e}\n"
        finally:
            self.after(0, self.update_log_and_button, log_update)

    def update_log_and_button(self, log_message):
        self.download_log.config(state="normal")
        self.download_log.insert(tk.END, log_message)
        self.download_log.see(tk.END)
        self.download_log.config(state="disabled")
        self.download_button.config(state="normal")

    def populate_song_list(self):
        requests_dir = "requests"
        if not os.path.isdir(requests_dir):
            try: os.makedirs(requests_dir)
            except OSError: pass

        self.song_combobox.set('')
        self.song_combobox['values'] = []

        songs = sorted([f for f in os.listdir(requests_dir) if f.endswith('.mp3')])

        self.song_combobox['values'] = songs
        
        if songs:
            self.song_combobox.current(0)
        else:
            self.song_combobox.set("No songs found")

    def play_song(self):
        selected_song = self.song_combobox.get()
        if not selected_song or "No songs found" in selected_song: return
        
        song_path = os.path.join("requests", selected_song)
        if not os.path.exists(song_path):
            messagebox.showerror("File Not Found", f"The song '{selected_song}' could not be found.")
            self.populate_song_list()
            return

        if self.is_paused and song_path == self.currently_playing_path:
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.play_button.config(text="Play")
        else:
            try:
                pygame.mixer.music.load(song_path)
                pygame.mixer.music.play()
                self.currently_playing_path = song_path
                self.is_paused = False
                sound = pygame.mixer.Sound(song_path)
                self.song_length_seconds = sound.get_length()
                self.now_playing_label.config(text=f"Now Playing: {selected_song}")
                
                # Write to state file for overlay
                with open("now_playing_state.txt", "w", encoding="utf-8") as f:
                    f.write(selected_song)
            except pygame.error as e:
                messagebox.showerror("Player Error", f"Could not play song: {e}")

    def pause_song(self):
        if pygame.mixer.music.get_busy() and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.play_button.config(text="Unpause")

    def stop_song(self):
        self.background_song_is_paused = False
        self.background_resume_time = 0.0
        pygame.mixer.music.stop()
        self.currently_playing_path = None
        self.is_paused = False
        self.now_playing_label.config(text="Now Playing: None")
        self.time_label.config(text="Time Remaining: --:--")
        self.play_button.config(text="Play")
    
    def stop_background_song(self):
        print("PLAYER: Stop background music command received.")
        if pygame.mixer.music.get_busy() and self.currently_playing_path == self.background_song_path:
            self.stop_song()
        self.background_song_path = None
        self.background_song_is_paused = False
        self.background_resume_time = 0.0
        self.background_song_combobox.set("No background songs found")

    def _format_time(self, seconds):
        if seconds < 0: seconds = 0
        minutes, sec = divmod(int(seconds), 60)
        return f"{minutes:02d}:{sec:02d}"

    def update_song_progress(self):
        is_currently_busy = pygame.mixer.music.get_busy()

        if self.is_starting_new_song:
            if is_currently_busy:
                print("PLAYER: Lock released. New song is confirmed playing.")
                self.is_starting_new_song = False
            self.after(500, self.update_song_progress)
            return

        if self.autoplay_queue and self.autoplay_var.get():
            if not is_currently_busy or self.currently_playing_path == self.background_song_path:
                if is_currently_busy:
                    print("PLAYER: Pausing background music for a request.")
                    self.background_resume_time = pygame.mixer.music.get_pos() / 1000.0
                    pygame.mixer.music.stop()
                    self.background_song_is_paused = True
                
                next_song = self.autoplay_queue.popleft()
                print(f"QUEUE: Playing next song: '{next_song}'. ({len(self.autoplay_queue)} remaining).")
                if next_song in self.song_combobox['values']:
                    self.song_combobox.set(next_song)
                    self.play_song()
                    self.is_starting_new_song = True
                else:
                    print(f"QUEUE ERROR: Song '{next_song}' not found. Skipping.")
        
        elif is_currently_busy and not self.is_paused:
            if self.currently_playing_path != self.background_song_path:
                current_pos_ms = pygame.mixer.music.get_pos()
                time_left = self.song_length_seconds - (current_pos_ms / 1000.0)
                self.time_label.config(text=f"Time Remaining: {self._format_time(time_left)}")
            else:
                self.time_label.config(text="Time Remaining: ∞ (Looping)")

        elif not is_currently_busy and self.currently_playing_path is not None:
            if self.currently_playing_path != self.background_song_path:
                print(f"PLAYER: Request song finished - {os.path.basename(self.currently_playing_path or '')}")
                song_path_to_delete = self.currently_playing_path
                self.currently_playing_path = None
                self.now_playing_label.config(text="Now Playing: None")
                self.time_label.config(text="Time Remaining: --:--")
                if self.autodelete_var.get() and song_path_to_delete:
                    try:
                        os.remove(song_path_to_delete)
                        print(f"AUTODELETE: Deleted '{os.path.basename(song_path_to_delete)}'")
                        self.populate_song_list()
                    except Exception as e:
                        print(f"AUTODELETE ERROR: {e}")
                
                # Check if there are songs in autoplay queue before resuming background
                if self.autoplay_queue and self.autoplay_var.get():
                    next_song = self.autoplay_queue.popleft()
                    print(f"QUEUE: Playing next queued song: '{next_song}'. ({len(self.autoplay_queue)} remaining).")
                    if next_song in self.song_combobox['values']:
                        self.song_combobox.set(next_song)
                        self.play_song()
                        self.is_starting_new_song = True
                        self.after(500, self.update_song_progress)
                        return
                    else:
                        print(f"QUEUE ERROR: Song '{next_song}' not found. Skipping.")
            elif self.currently_playing_path == self.background_song_path:
                 self.currently_playing_path = None

        elif not is_currently_busy and self.background_song_path:
            # Check queue first before resuming background music
            if self.autoplay_queue and self.autoplay_var.get():
                next_song = self.autoplay_queue.popleft()
                print(f"QUEUE: Playing next queued song: '{next_song}'. ({len(self.autoplay_queue)} remaining).")
                if next_song in self.song_combobox['values']:
                    self.song_combobox.set(next_song)
                    self.play_song()
                    self.is_starting_new_song = True
                    self.after(500, self.update_song_progress)
                    return
                else:
                    print(f"QUEUE ERROR: Song '{next_song}' not found. Skipping.")
            
            # No songs in queue, resume background music
            if self.background_song_is_paused:
                print(f"PLAYER: Resuming background music from {self.background_resume_time:.2f} seconds.")
                pygame.mixer.music.load(self.background_song_path)
                pygame.mixer.music.play(loops=-1, start=self.background_resume_time)
                self.background_song_is_paused = False
                self.currently_playing_path = self.background_song_path
            else:
                print("PLAYER: Starting background music from beginning.")
                pygame.mixer.music.load(self.background_song_path)
                pygame.mixer.music.play(loops=-1)
                self.currently_playing_path = self.background_song_path
                self.background_resume_time = 0.0
            
            self.now_playing_label.config(text=f"Background: {os.path.basename(self.background_song_path)}")
            self.is_starting_new_song = True

        self.after(500, self.update_song_progress)
    
    def check_for_autoplay(self):
        autoplay_file = "autoplay.txt"
        skip_file = "skip_signal.txt"
        pause_play_file = "pause_play_signal.txt"
        resume_file = "resume_signal.txt"
        
        # Check for resume signal first
        if os.path.exists(resume_file):
            try:
                os.remove(resume_file)
                print("QUEUE: Resume signal detected! Resuming paused song.")
                self.resume_paused_song()
            except Exception as e:
                print(f"AUTOPLAY ERROR: Could not process resume signal: {e}")
        
        # Check for pause and play signal
        if os.path.exists(pause_play_file):
            try:
                with open(pause_play_file, 'r', encoding='utf-8') as f:
                    song_to_play = f.read().strip()
                os.remove(pause_play_file)
                if song_to_play:
                    print(f"QUEUE: Pause and play signal detected: '{song_to_play}'")
                    self.pause_and_play_song(song_to_play)
            except Exception as e:
                print(f"AUTOPLAY ERROR: Could not process pause signal: {e}")
        
        # Check for skip signal
        if os.path.exists(skip_file):
            try:
                os.remove(skip_file)
                print("QUEUE: Skip signal detected! Skipping to next song.")
                self.skip_current_song()
            except Exception as e:
                print(f"AUTOPLAY ERROR: Could not process skip signal: {e}")
        
        if os.path.exists(autoplay_file):
            try:
                with open(autoplay_file, 'r', encoding='utf-8') as f:
                    song_filename = f.readline().strip()
                os.remove(autoplay_file)
                if song_filename:
                    self.populate_song_list()
                    # Only add if not already in queue or currently playing
                    if song_filename not in self.autoplay_queue and song_filename != self.currently_playing_path:
                        self.autoplay_queue.append(song_filename)
                        print(f"QUEUE: Added '{song_filename}'. ({len(self.autoplay_queue)} song(s) waiting).")
                    else:
                        print(f"QUEUE: Skipping duplicate '{song_filename}' (already in queue or playing).")
            except Exception as e:
                print(f"AUTOPLAY ERROR: Could not process autoplay file: {e}")
                if os.path.exists(autoplay_file): os.remove(autoplay_file)
        
        self.after(1000, self.check_for_autoplay)
    
    def pause_and_play_song(self, song_to_play):
        """Pause current song, play inserted song, then resume"""
        print(f"QUEUE: Pausing current song to play '{song_to_play}'...")
        
        # Save current position if playing
        if pygame.mixer.music.get_busy() and not self.is_paused:
            self.paused_song_path = self.currently_playing_path
            self.paused_song_position = pygame.mixer.music.get_pos() / 1000.0
            print(f"QUEUE: Saved position {self.paused_song_position:.2f}s for '{os.path.basename(self.paused_song_path or '')}'")
            pygame.mixer.music.pause()
            self.is_paused = True
        
        # Search for the requested song in requests folder
        requests_dir = "requests"
        found_song = None
        
        if os.path.exists(requests_dir):
            song_clean = song_to_play.lower().strip()
            for filename in os.listdir(requests_dir):
                if filename.endswith('.mp3') and song_clean in filename.lower():
                    found_song = os.path.join(requests_dir, filename)
                    break
        
        if found_song and os.path.exists(found_song):
            print(f"QUEUE: Found '{song_to_play}' at {found_song}")
            try:
                pygame.mixer.music.load(found_song)
                pygame.mixer.music.play()
                self.currently_playing_path = found_song
                self.is_paused = False
                self.now_playing_label.config(text=f"Now Playing: {os.path.basename(found_song)}")
                print(f"QUEUE: Playing inserted song: {os.path.basename(found_song)}")
            except Exception as e:
                print(f"QUEUE ERROR: Could not play inserted song: {e}")
        else:
            print(f"QUEUE: Song '{song_to_play}' not found in requests folder.")
            self.now_playing_label.config(text=f"Song not found: {song_to_play}")
    
    def resume_paused_song(self):
        """Resume the previously paused song"""
        print("QUEUE: Resuming paused song...")
        
        if hasattr(self, 'paused_song_path') and self.paused_song_path:
            try:
                print(f"QUEUE: Resuming '{os.path.basename(self.paused_song_path)}' at {self.paused_song_position:.2f}s")
                pygame.mixer.music.load(self.paused_song_path)
                pygame.mixer.music.play(start=self.paused_song_position)
                self.currently_playing_path = self.paused_song_path
                self.is_paused = False
                self.paused_song_path = None
                self.paused_song_position = 0.0
                self.now_playing_label.config(text=f"Now Playing: {os.path.basename(self.currently_playing_path)}")
                print("QUEUE: Resumed previous song.")
            except Exception as e:
                print(f"QUEUE ERROR: Could not resume song: {e}")
        else:
            print("QUEUE: No paused song to resume.")
            self.now_playing_label.config(text="Now Playing: None")
    
    def skip_current_song(self):
        """Stop current song and play next in queue"""
        print("QUEUE: Skipping current song...")
        
        # Stop current playback
        pygame.mixer.music.stop()
        self.currently_playing_path = None
        self.is_paused = False
        
        # Check if there's a next song in queue
        if self.autoplay_queue:
            next_song = self.autoplay_queue.popleft()
            print(f"QUEUE: Playing next song: '{next_song}'. ({len(self.autoplay_queue)} remaining).")
            if next_song in self.song_combobox['values']:
                self.song_combobox.set(next_song)
                self.play_song()
                self.is_starting_new_song = True
            else:
                print(f"QUEUE ERROR: Song '{next_song}' not found in list.")
                self.now_playing_label.config(text="Now Playing: None")
                self.time_label.config(text="Time Remaining: --:--")
        else:
            print("QUEUE: No songs in queue.")
            self.now_playing_label.config(text="Now Playing: None")
            self.time_label.config(text="Time Remaining: --:--")

    def on_closing(self):
        pygame.mixer.quit()
        self.stop_vision_thread = True
        self.is_testing_output = False
        if self.input_stream: self.input_stream.close()
        if self.output_stream: self.output_stream.close()
        
        # Clear state files so now_playing overlay doesn't show old song
        try:
            if os.path.exists("now_playing_state.txt"):
                os.remove("now_playing_state.txt")
            if os.path.exists("autoplay.txt"):
                os.remove("autoplay.txt")
            if os.path.exists("pause_play_signal.txt"):
                os.remove("pause_play_signal.txt")
            if os.path.exists("resume_signal.txt"):
                os.remove("resume_signal.txt")
            if os.path.exists("skip_signal.txt"):
                os.remove("skip_signal.txt")
        except Exception as e:
            print(f"Cleanup error: {e}")
        
        self.destroy()

    def setup_neurosync_widgets(self, parent_frame):
        def create_scrollable_frame(parent, text_label):
            ini_frame = ttk.LabelFrame(parent, text=text_label)
            ini_frame.pack(fill="both", expand=True, padx=5, pady=5)
            canvas = tk.Canvas(ini_frame)
            scrollbar = ttk.Scrollbar(ini_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)
            canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            scrollbar.pack(side="right", fill="y")
            return scrollable_frame
        neurosync_paned_window = tk.PanedWindow(parent_frame, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, bd=2)
        neurosync_paned_window.pack(fill="both", expand=True)
        left_pane = ttk.Frame(neurosync_paned_window)
        neurosync_paned_window.add(left_pane, width=500, minsize=400)
        self.neurosync_api_scrollable_frame = create_scrollable_frame(left_pane, "Neurosync Local API")
        right_pane = ttk.Frame(neurosync_paned_window)
        neurosync_paned_window.add(right_pane)
        self.neurosync_main_scrollable_frame = create_scrollable_frame(right_pane, "Neurosync & Watcher")

    def setup_vision_widgets(self, parent_frame):
        vision_paned_window = tk.PanedWindow(parent_frame, orient=tk.VERTICAL, sashrelief=tk.RAISED, bd=2)
        vision_paned_window.pack(fill="both", expand=True, padx=5, pady=5)
        preview_frame = ttk.LabelFrame(vision_paned_window, text="Camera Preview", padding=10)
        vision_paned_window.add(preview_frame, height=480)
        self.video_label = tk.Label(preview_frame, bg="black", text="Preview will appear here", fg="white")
        self.video_label.pack(fill="both", expand=True)
        vision_settings_frame = ttk.Frame(vision_paned_window, padding=(10, 10))
        vision_paned_window.add(vision_settings_frame)
        controls_frame = ttk.Frame(vision_settings_frame)
        controls_frame.pack(fill="x", pady=5, anchor="n")
        ttk.Label(controls_frame, text="Available Cameras:").pack(side="left", padx=(0, 10))
        self.camera_combobox = ttk.Combobox(controls_frame, state="readonly", width=10)
        self.camera_combobox.pack(side="left", padx=10)
        start_btn = ttk.Button(controls_frame, text="Start Preview", command=self.start_camera_preview)
        start_btn.pack(side="left", padx=10)
        stop_btn = ttk.Button(controls_frame, text="Stop Preview", command=self.stop_camera_preview)
        stop_btn.pack(side="left", padx=10)
        saved_device_frame = ttk.Frame(vision_settings_frame)
        saved_device_frame.pack(fill="x", pady=5, anchor="n")
        ttk.Label(saved_device_frame, text="Saved Camera Index:").pack(side="left")
        self.saved_camera_device_var = tk.StringVar(value="None")
        ttk.Entry(saved_device_frame, textvariable=self.saved_camera_device_var, state="readonly").pack(side="left", fill="x", expand=True, padx=10)
        vlm_frame = ttk.LabelFrame(vision_settings_frame, text="Vision Language Model Settings", padding=10)
        vlm_frame.pack(fill="x", expand=True, pady=(10, 0), anchor="n")
        ttk.Label(vlm_frame, text="SmolVLM Model ID:").pack(side="left", padx=(0, 10))
        self.smol_vlm_entry = ttk.Entry(vlm_frame)
        self.smol_vlm_entry.pack(side="left", fill="x", expand=True)
        self.vision_ini_container = ttk.Frame(vision_settings_frame)
        self.vision_ini_container.pack(fill="both", expand=True, pady=10, anchor="n")

    def setup_tts_widgets(self, parent_frame):
        """Setup TTS Settings tab with StyleTTS2 and Pocket TTS controls"""
        # Main TTS selection frame
        tts_select_frame = ttk.LabelFrame(parent_frame, text="TTS Engine Selection", padding=10)
        tts_select_frame.pack(fill="x", padx=10, pady=10)
        
        # StyleTTS2 toggle
        self.styletts_enabled_var = tk.BooleanVar(value=False)
        styletts_check = ttk.Checkbutton(
            tts_select_frame,
            text="Enable StyleTTS2 (Port 13300)",
            variable=self.styletts_enabled_var,
            command=self.toggle_tts_engine
        )
        styletts_check.pack(anchor="w", pady=5)
        
        # Pocket TTS toggle
        self.pockettts_enabled_var = tk.BooleanVar(value=False)
        pockettts_check = ttk.Checkbutton(
            tts_select_frame,
            text="Enable Pocket TTS (Port 13301)",
            variable=self.pockettts_enabled_var,
            command=self.toggle_tts_engine
        )
        pockettts_check.pack(anchor="w", pady=5)
        # Auto-save when toggled
        self.pockettts_enabled_var.trace_add("write", lambda *args: self.save_tts_settings())
        
        # TTS URLs frame
        url_frame = ttk.LabelFrame(parent_frame, text="TTS Server URLs", padding=10)
        url_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(url_frame, text="StyleTTS2 URL:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.styletts_url_var = tk.StringVar(value="http://127.0.0.1:13300/tts")
        self.styletts_url_entry = ttk.Entry(url_frame, textvariable=self.styletts_url_var, width=50)
        self.styletts_url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(url_frame, text="Pocket TTS URL:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.pockettts_url_var = tk.StringVar(value="http://127.0.0.1:13301/tts")
        self.pockettts_url_entry = ttk.Entry(url_frame, textvariable=self.pockettts_url_var, width=50)
        self.pockettts_url_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        
        url_frame.grid_columnconfigure(1, weight=1)
        
        # Voice cloning frame
        voice_frame = ttk.LabelFrame(parent_frame, text="Voice Cloning", padding=10)
        voice_frame.pack(fill="x", padx=10, pady=10)
        
        ttk.Label(voice_frame, text="Reference Voice File:").pack(anchor="w", pady=(0, 5))
        self.voice_file_var = tk.StringVar(value="tts/StyleTTS2/voices/earn_lucky_pitch_minus_one_samplerate_24000_short_mono.wav")
        voice_entry = ttk.Entry(voice_frame, textvariable=self.voice_file_var, width=70)
        voice_entry.pack(fill="x", pady=(0, 10))
        
        ttk.Label(voice_frame, text="Pocket TTS uses voice cloning with truncate=True for better quality.", 
                  foreground="gray").pack(anchor="w")
        
        # Audio ducking frame
        ducking_frame = ttk.LabelFrame(parent_frame, text="Audio Ducking (TTS Priority)", padding=10)
        ducking_frame.pack(fill="x", padx=10, pady=10)
        
        self.ducking_enabled_var = tk.BooleanVar(value=False)
        ducking_check = ttk.Checkbutton(
            ducking_frame,
            text="Enable Audio Ducking",
            variable=self.ducking_enabled_var,
            command=self.on_ducking_toggle
        )
        ducking_check.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        
        ttk.Label(ducking_frame, text="Duck Amount (dB):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.ducking_amount_var = tk.StringVar(value="-15")
        ducking_amount_spin = ttk.Spinbox(ducking_frame, from_=-60, to=0, width=10, textvariable=self.ducking_amount_var, command=self.save_ducking_settings)
        ducking_amount_spin.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(ducking_frame, text="Attack (ms):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.ducking_attack_var = tk.StringVar(value="100")
        ducking_attack_spin = ttk.Spinbox(ducking_frame, from_=10, to=1000, width=10, textvariable=self.ducking_attack_var, command=self.save_ducking_settings)
        ducking_attack_spin.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(ducking_frame, text="Release (ms):").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.ducking_release_var = tk.StringVar(value="500")
        ducking_release_spin = ttk.Spinbox(ducking_frame, from_=100, to=5000, width=10, textvariable=self.ducking_release_var, command=self.save_ducking_settings)
        ducking_release_spin.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(ducking_frame, 
                  text="When TTS plays, music volume is reduced by the duck amount", 
                  foreground="gray", font=('TkDefaultFont', 8)).grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))
        
        # Save button
        save_frame = ttk.Frame(parent_frame, padding=10)
        save_frame.pack(fill="x", padx=10, pady=5)
        
        save_btn = ttk.Button(save_frame, text="Save TTS Settings", command=self.save_tts_settings)
        save_btn.pack(side="left", padx=5)
        
        ttk.Label(save_frame, text="(Updates mcp_settings.ini)", foreground="gray").pack(side="left", padx=10)
        
        # Launch buttons
        launch_frame = ttk.Frame(parent_frame, padding=10)
        launch_frame.pack(fill="x", padx=10, pady=10)
        
        styletts_btn = ttk.Button(launch_frame, text="Start StyleTTS2", command=self.run_styletts2_script)
        styletts_btn.pack(side="left", padx=5)
        
        pockettts_btn = ttk.Button(launch_frame, text="Start Pocket TTS", command=self.run_pockettts_script)
        pockettts_btn.pack(side="left", padx=5)
        
        audio_player_btn = ttk.Button(launch_frame, text="Start Audio Player", command=self.run_audio_player)
        audio_player_btn.pack(side="left", padx=5)
        
        # Status info
        status_frame = ttk.LabelFrame(parent_frame, text="TTS Status", padding=10)
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tts_status_label = ttk.Label(status_frame, text="Status: Not running", foreground="gray")
        self.tts_status_label.pack(anchor="w")
        
        ttk.Label(status_frame, text="Audio Player monitors tts_output/ folder for auto-playback", 
                 foreground="gray", font=('TkDefaultFont', 9)).pack(anchor="w", pady=(5, 0))
        
        info_text = """
TTS Notes:
• StyleTTS2: Original TTS system, works with custom voices
• Pocket TTS: Faster CPU-based TTS with voice cloning support
• Both save to server_output.wav for watcher_to_face lip-sync
• Enable only ONE TTS engine at a time in mcp_settings.ini
• Voice cloning requires Hugging Face authentication (hf auth login)
"""
        ttk.Label(status_frame, text=info_text, justify="left").pack(anchor="w", pady=10)
    
    def toggle_tts_engine(self):
        """Handle TTS engine toggle - ensure only one is enabled at a time"""
        if self.styletts_enabled_var.get() and self.pockettts_enabled_var.get():
            # If both checked, uncheck the one that was just clicked
            sender = self.focus_get()
            if sender == self.styletts_url_entry or str(sender).find('styletts') != -1:
                self.pockettts_enabled_var.set(False)
            else:
                self.styletts_enabled_var.set(False)
        
        # Update status
        if self.styletts_enabled_var.get():
            self.tts_status_label.config(text="Status: StyleTTS2 enabled (port 13300)", foreground="green")
        elif self.pockettts_enabled_var.get():
            self.tts_status_label.config(text="Status: Pocket TTS enabled (port 13301)", foreground="green")
        else:
            self.tts_status_label.config(text="Status: No TTS engine enabled", foreground="gray")
    
    def run_pockettts_script(self):
        """Launch Pocket TTS server"""
        self._run_start_script("Start_PocketTTS.bat")
    
    def load_tts_settings(self):
        """Load TTS settings from mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            
            # Load StyleTTS settings
            if self.config.has_section('StyleTTS'):
                styletts_enabled = self.config.getboolean('StyleTTS', 'enabled', fallback=False)
                self.styletts_enabled_var.set(styletts_enabled)
                
                styletts_url = self.config.get('StyleTTS', 'tts_url', fallback='http://127.0.0.1:13300/tts')
                self.styletts_url_var.set(styletts_url)
            
            # Load PocketTTS settings
            if self.config.has_section('PocketTTS'):
                pockettts_enabled = self.config.getboolean('PocketTTS', 'enabled', fallback=False)
                self.pockettts_enabled_var.set(pockettts_enabled)
                
                pockettts_url = self.config.get('PocketTTS', 'tts_url', fallback='http://127.0.0.1:13301/tts')
                self.pockettts_url_var.set(pockettts_url)
            
            # Update status display
            self.toggle_tts_engine()
            
        except Exception as e:
            print(f"CONTROL PANEL: Could not load TTS settings: {e}")
    
    def load_osc_settings(self):
        """Load OSC settings from mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            if self.config.has_section('OSC'):
                osc_enabled = self.config.getboolean('OSC', 'enabled', fallback=False)
                self.osc_enabled_var.set(osc_enabled)
                
                osc_ip = self.config.get('OSC', 'ip', fallback='127.0.0.1')
                self.osc_ip_var.set(osc_ip)
                
                osc_port = self.config.get('OSC', 'port', fallback='10000')
                self.osc_port_var.set(osc_port)
                
                osc_address = self.config.get('OSC', 'address', fallback='/chat/message')
                self.osc_address_var.set(osc_address)
        except Exception as e:
            print(f"CONTROL PANEL: Could not load OSC settings: {e}")
    
    def save_osc_settings(self):
        """Save OSC settings to mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            if not self.config.has_section('OSC'):
                self.config.add_section('OSC')
            
            self.config.set('OSC', 'enabled', str(self.osc_enabled_var.get()))
            self.config.set('OSC', 'ip', self.osc_ip_var.get())
            self.config.set('OSC', 'port', self.osc_port_var.get())
            self.config.set('OSC', 'address', self.osc_address_var.get())
            
            with open("mcp_settings.ini", "w") as f:
                self.config.write(f)
            
            messagebox.showinfo("Success", "OSC settings saved to mcp_settings.ini!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save OSC settings:\n{e}")
    
    def save_tts_settings(self):
        """Save TTS settings to mcp_settings.ini"""
        try:
            # Read current config
            self.config.read("mcp_settings.ini")
            
            # Update StyleTTS section
            if not self.config.has_section('StyleTTS'):
                self.config.add_section('StyleTTS')
            self.config.set('StyleTTS', 'enabled', str(self.styletts_enabled_var.get()))
            self.config.set('StyleTTS', 'tts_url', self.styletts_url_var.get())
            
            # Update PocketTTS section
            if not self.config.has_section('PocketTTS'):
                self.config.add_section('PocketTTS')
            self.config.set('PocketTTS', 'enabled', str(self.pockettts_enabled_var.get()))
            self.config.set('PocketTTS', 'tts_url', self.pockettts_url_var.get())
            
            # Save to file
            with open("mcp_settings.ini", "w") as f:
                self.config.write(f)
            
            self.tts_status_label.config(text="Status: Settings saved!", foreground="green")
            print("CONTROL PANEL: TTS settings saved to mcp_settings.ini")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save TTS settings:\n{e}")
            self.tts_status_label.config(text="Status: Save failed!", foreground="red")
    
    def on_ducking_toggle(self):
        """Called when ducking checkbox is toggled"""
        print(f"DUCKING TOGGLE: enabled={self.ducking_enabled_var.get()}")
        self.save_ducking_settings()
        
        # Start/stop monitoring based on toggle
        if self.ducking_enabled_var.get():
            self.check_ducking_signal()
            print("DUCKING MONITOR: Started")
        else:
            print("DUCKING MONITOR: Stopped (will restart on next TTS)")
    
    def save_ducking_settings(self):
        """Save audio ducking settings to mcp_settings.ini"""
        try:
            # Use absolute path
            ini_path = os.path.abspath("mcp_settings.ini")
            print(f"DUCKING SAVE: Writing to {ini_path}")
            
            self.config.read(ini_path)
            
            if not self.config.has_section('AudioDucking'):
                self.config.add_section('AudioDucking')
            
            self.config.set('AudioDucking', 'enabled', str(self.ducking_enabled_var.get()))
            self.config.set('AudioDucking', 'duck_amount', self.ducking_amount_var.get())
            self.config.set('AudioDucking', 'attack_ms', self.ducking_attack_var.get())
            self.config.set('AudioDucking', 'release_ms', self.ducking_release_var.get())
            
            with open(ini_path, "w") as f:
                self.config.write(f)
            
            print(f"*** DUCKING SAVED: enabled={self.ducking_enabled_var.get()}, amount={self.ducking_amount_var.get()}dB, attack={self.ducking_attack_var.get()}ms, release={self.ducking_release_var.get()}ms ***")
            
            # Verify it was written correctly by reading fresh
            verify_config = configparser.ConfigParser()
            verify_config.read(ini_path)
            saved_enabled = verify_config.get('AudioDucking', 'enabled', fallback='NOT_FOUND')
            saved_amount = verify_config.get('AudioDucking', 'duck_amount', fallback='NOT_FOUND')
            print(f"DUCKING VERIFY: Read back from ini - enabled={saved_enabled}, duck_amount={saved_amount}")
            print(f"DUCKING VERIFY: File exists at {ini_path} = {os.path.exists(ini_path)}")
            
        except Exception as e:
            print(f"CONTROL PANEL: Error saving ducking settings: {e}")
            import traceback
            traceback.print_exc()
    
    def load_ducking_settings(self):
        """Load audio ducking settings from mcp_settings.ini"""
        try:
            ini_path = os.path.abspath("mcp_settings.ini")
            print(f"DUCKING LOAD: Reading from {ini_path}")
            print(f"DUCKING LOAD: File exists = {os.path.exists(ini_path)}")
            
            # Force a fresh read
            self.config.read(ini_path)
            
            # Debug: show all sections
            print(f"DUCKING LOAD: Available sections: {self.config.sections()}")
            
            if self.config.has_section('AudioDucking'):
                ducking_enabled = self.config.getboolean('AudioDucking', 'enabled', fallback=False)
                duck_amount = self.config.get('AudioDucking', 'duck_amount', fallback='-15')
                attack_ms = self.config.get('AudioDucking', 'attack_ms', fallback='100')
                release_ms = self.config.get('AudioDucking', 'release_ms', fallback='500')
                
                print(f"DUCKING LOAD: enabled={ducking_enabled}, amount={duck_amount}, attack={attack_ms}, release={release_ms}")
                
                self.ducking_enabled_var.set(ducking_enabled)
                self.ducking_amount_var.set(duck_amount)
                self.ducking_attack_var.set(attack_ms)
                self.ducking_release_var.set(release_ms)
                
                print(f"DUCKING LOAD: UI updated - checkbox state = {self.ducking_enabled_var.get()}")
            else:
                print(f"DUCKING LOAD: [AudioDucking] section NOT FOUND in ini file")
        except Exception as e:
            print(f"CONTROL PANEL: Error loading ducking settings: {e}")
            import traceback
            traceback.print_exc()
    
    def check_ducking_signal(self):
        """Check for ducking signal file from audio_player.py"""
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            signal_file = os.path.join(script_dir, 'ducking_signal.txt')
            
            # Debug: print path every 10 checks
            if not hasattr(self, '_ducking_check_count'):
                self._ducking_check_count = 0
            self._ducking_check_count += 1
            if self._ducking_check_count % 10 == 0:
                print(f"DUCKING DEBUG: Checking {signal_file}, exists={os.path.exists(signal_file)}, enabled={self.ducking_enabled_var.get()}")
            
            if os.path.exists(signal_file):
                if not self.ducking_active:
                    # First time detection - initialize
                    print(f"*** DUCKING SIGNAL DETECTED at {signal_file} ***")
                    with open(signal_file, 'r') as f:
                        lines = f.readlines()
                        duck_amount = float(lines[0].strip()) if len(lines) > 0 else -15
                        attack_ms = int(lines[1].strip()) if len(lines) > 1 else 100
                        release_ms = int(lines[2].strip()) if len(lines) > 2 else 500
                    
                    # Store settings for persistent ducking
                    # Convert dB to volume: -15dB = 18% volume, -30dB = 3% volume
                    self._ducking_release_ms = release_ms
                    self._ducking_target_volume = max(0.0, 10.0 ** (duck_amount / 20.0))  # Proper dB conversion
                    self._ducking_attack_ms = attack_ms
                    
                    # Check if music is actually playing
                    if not pygame.mixer.music.get_busy():
                        print("DUCKING DEBUG: Signal detected but no music playing")
                        self.ducking_active = True
                        return
                    
                    # Apply ducking immediately
                    current_volume = pygame.mixer.music.get_volume()
                    print(f"*** DUCKING: Music volume {current_volume:.2f} → {self._ducking_target_volume:.2f} (duck={duck_amount}dB) ***")
                    print(f"DUCKING DEBUG: pygame.mixer.music.get_busy()={pygame.mixer.music.get_busy()}")
                    print(f"DUCKING DEBUG: pygame.mixer.get_init()={pygame.mixer.get_init()}")
                    
                    # Smooth attack
                    steps = 10
                    volume_step = (current_volume - self._ducking_target_volume) / steps
                    delay_per_step = attack_ms / 1000.0 / steps
                    
                    for i in range(steps):
                        new_vol = current_volume - (volume_step * (i + 1))
                        pygame.mixer.music.set_volume(new_vol)
                        actual_vol = pygame.mixer.music.get_volume()
                        print(f"DUCKING STEP {i+1}: set={new_vol:.2f}, actual={actual_vol:.2f}")
                        time.sleep(delay_per_step)
                    
                    final_vol = pygame.mixer.music.get_volume()
                    print(f"*** DUCKING COMPLETE: Final volume={final_vol:.2f}, target={self._ducking_target_volume:.2f} ***")
                    self.ducking_active = True
                else:
                    # Already ducking - re-apply volume in case it was reset by music reload
                    if hasattr(self, '_ducking_target_volume'):
                        current_vol = pygame.mixer.music.get_volume()
                        # Only re-apply if volume drifted from target
                        if abs(current_vol - self._ducking_target_volume) > 0.05:
                            pygame.mixer.music.set_volume(self._ducking_target_volume)
                            actual_vol = pygame.mixer.music.get_volume()
                            print(f"DUCKING: Re-applied target={self._ducking_target_volume:.2f}, was={current_vol:.2f}, actual={actual_vol:.2f}")
            else:
                if self.ducking_active:
                    # Signal file removed - release ducking
                    print(f"*** DUCKING SIGNAL GONE - restoring volume ***")
                    release_ms = getattr(self, '_ducking_release_ms', 500)
                    current_volume = pygame.mixer.music.get_volume()
                    
                    # Smooth release
                    steps = 10
                    volume_step = (1.0 - current_volume) / steps
                    delay_per_step = release_ms / 1000.0 / steps
                    
                    for i in range(steps):
                        new_vol = current_volume + (volume_step * (i + 1))
                        pygame.mixer.music.set_volume(new_vol)
                        time.sleep(delay_per_step)
                    
                    final_vol = pygame.mixer.music.get_volume()
                    print(f"*** RESTORE COMPLETE: Final volume={final_vol:.2f} ***")
                    self.ducking_active = False
                    print("*** CONTROL PANEL: TTS complete - restoring music volume ***")
        except Exception as e:
            print(f"DUCKING ERROR: {e}")
            import traceback
            traceback.print_exc()
        
        # Schedule next check
        if self.ducking_enabled_var.get():
            self.after(100, self.check_ducking_signal)
    
    def apply_audio_ducking(self, is_ducking):
        """Apply audio ducking to background music (legacy method)"""
        if not self.ducking_enabled_var.get():
            return
        
        try:
            duck_amount = int(self.ducking_amount_var.get())
            if is_ducking:
                # Apply ducking - reduce volume
                current_volume = pygame.mixer.music.get_volume()
                target_volume = max(0.0, 1.0 + (duck_amount / 100.0))
                pygame.mixer.music.set_volume(target_volume)
                print(f"CONTROL PANEL: Audio ducking applied - volume reduced to {target_volume:.2f}")
            else:
                # Release ducking - restore volume
                pygame.mixer.music.set_volume(1.0)
                print("CONTROL PANEL: Audio ducking released - volume restored")
        except Exception as e:
            print(f"CONTROL PANEL: Error applying ducking: {e}")
    
    def setup_ini_widgets(self, parent_frame):
        ini_frame = ttk.LabelFrame(parent_frame, text="mcp_settings.ini (General)")
        ini_frame.pack(fill="both", expand=True)
        ini_frame.bind('<Enter>', self._bind_mousewheel_for_right_pane)
        ini_frame.bind('<Leave>', self._unbind_mousewheel_for_right_pane)
        self.ini_canvas = tk.Canvas(ini_frame)
        scrollbar = ttk.Scrollbar(ini_frame, orient="vertical", command=self.ini_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.ini_canvas)
        self.canvas_window = self.ini_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.ini_canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable_frame.bind("<Configure>", lambda e: self.ini_canvas.configure(scrollregion=self.ini_canvas.bbox("all")))
        self.ini_canvas.configure(yscrollcommand=scrollbar.set)
        self.ini_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")
        social_stream_toggle_frame = ttk.Frame(parent_frame)
        social_stream_toggle_frame.pack(fill="x", padx=10, pady=5)
        social_stream_check = ttk.Checkbutton(
            social_stream_toggle_frame,
            text="Send AI Responses to Social Stream",
            variable=self.send_to_social_stream_var,
            command=lambda: self._send_runtime_update('send_to_social_stream', self.send_to_social_stream_var.get())
        )
        social_stream_check.pack(side="left")
        
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill="x", pady=(5,0))
        save_button = ttk.Button(button_frame, text="Save All Settings", command=self.save_all_settings)
        save_button.pack(side="left", expand=True, fill="x", padx=5)
        run_neurosync_button = ttk.Button(button_frame, text="1. Neurosync Local API", command=self.run_neurosync_api_script)
        run_neurosync_button.pack(side="left", expand=True, fill="x", padx=5)
        run_watcher_button = ttk.Button(button_frame, text="2. Neurosync Watcher To Face", command=self.run_watcher_to_face_script)
        run_watcher_button.pack(side="left", expand=True, fill="x", padx=5)
        run_script_button = ttk.Button(button_frame, text="3. MCP", command=self.run_main_script)
        run_script_button.pack(side="left", expand=True, fill="x", padx=5)
        run_vision_button = ttk.Button(button_frame, text="4. Vision", command=self.run_vision_script)
        run_vision_button.pack(side="left", expand=True, fill="x", padx=5)
        reload_button = ttk.Button(button_frame, text="Reload All Settings", command=self.reload_ini_ui)
        reload_button.pack(side="left", expand=True, fill="x", padx=5)

    def run_neurosync_api_script(self): self._run_start_script("start_neurosync_localapi.bat")
    def run_watcher_to_face_script(self): self._run_start_script("start_neurosync_watcher_to_face.bat")
    def run_main_script(self): self._run_start_script("start_mcp.bat")
    def run_styletts2_script(self): self._run_start_script("Start_StyleTTS2.bat")
    def run_vision_script(self): self._run_start_script("start_vision.bat")
    def run_opencode_server(self):
        """Launch OpenCode server with selected model"""
        model = self.opencode_model_var.get()
        print(f"OPENCODE: Starting server with model: {model}")
        self._run_start_script("Start_OpenCode_Server.bat")
        self.opencode_status_var.set(f"Starting ({model})...")
    
    def save_opencode_settings(self):
        """Save OpenCode settings to mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            if not self.config.has_section('OpenCode'):
                self.config.add_section('OpenCode')
            self.config.set('OpenCode', 'model', self.opencode_model_var.get())
            self.config.set('OpenCode', 'url', self.opencode_url_var.get())
            with open("mcp_settings.ini", "w") as f:
                self.config.write(f)
            print("CONTROL PANEL: OpenCode settings saved")
        except Exception as e:
            print(f"CONTROL PANEL: Error saving OpenCode settings: {e}")
    
    def load_opencode_settings(self):
        """Load OpenCode settings from mcp_settings.ini"""
        try:
            self.config.read("mcp_settings.ini")
            if self.config.has_section('OpenCode'):
                model = self.config.get('OpenCode', 'model', fallback='ollama/gemma3:4b-it-qat')
                url = self.config.get('OpenCode', 'url', fallback='http://localhost:4096')
                self.opencode_model_var.set(model)
                self.opencode_url_var.set(url)
        except Exception as e:
            print(f"CONTROL PANEL: Error loading OpenCode settings: {e}")
    
    def run_audio_player(self):
        """Launch Audio Player for auto TTS playback"""
        self._run_start_script("Start_Audio_Player.bat")
        print("CONTROL PANEL: Audio Player started - monitoring tts_output/ folder")
    def _run_start_script(self, bat_file_name):
        # Get absolute path to start_scripts folder
        base_dir = os.path.dirname(os.path.abspath(__file__))
        scripts_dir = os.path.join(base_dir, "start_scripts")
        script_path = os.path.join(scripts_dir, bat_file_name)
        
        print(f"DEBUG: __file__ = {__file__}")
        print(f"DEBUG: base_dir = {base_dir}")
        print(f"DEBUG: scripts_dir = {scripts_dir}")
        print(f"DEBUG: script_path = {script_path}")
        print(f"DEBUG: Script exists: {os.path.exists(script_path)}")
        
        try:
            if not os.path.exists(script_path):
                raise FileNotFoundError(f"Script not found: {script_path}")
            subprocess.Popen(["cmd", "/c", script_path], creationflags=subprocess.CREATE_NEW_CONSOLE, cwd=scripts_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Could not launch script:\n{e}")

    def _on_right_pane_mousewheel(self, event):
        if event.num == 5 or event.delta < 0: self.ini_canvas.yview_scroll(1, "units")
        if event.num == 4 or event.delta > 0: self.ini_canvas.yview_scroll(-1, "units")
    def _bind_mousewheel_for_right_pane(self, event): self.bind_all("<MouseWheel>", self._on_right_pane_mousewheel)
    def _unbind_mousewheel_for_right_pane(self, event): self.unbind_all("<MouseWheel>")
    def _on_canvas_configure(self, event): self.ini_canvas.itemconfig(self.canvas_window, width=event.width)

    def _read_ini_safely(self):
        try:
            self.config.read(INI_FILE_PATH, encoding='utf-8')
            return True
        except FileNotFoundError:
            return False

    def reload_ini_ui(self):
        if not self._read_ini_safely():
            return
        
        if self.config.has_section('MusicDownloader'):
            downloader_enabled = self.config.getboolean('MusicDownloader', 'enabled', fallback=True)
            self.music_downloader_enabled_var.set(downloader_enabled)
            
            queue_length_str = self.config.get('MusicDownloader', 'max_queue_length', fallback='20')
            try:
                self.max_queue_length = int(queue_length_str)
            except ValueError:
                self.max_queue_length = 20
            
            duration_seconds_str = self.config.get('MusicDownloader', 'max_download_duration_seconds', fallback='600')
            try:
                duration_minutes = int(duration_seconds_str) // 60
                self.max_duration_var.set(str(duration_minutes))
            except ValueError:
                self.max_duration_var.set('10')
        else:
            self.music_downloader_enabled_var.set(True)
            self.max_queue_length = 20
            self.max_duration_var.set('10')
        
        if self.config.has_section('Streaming'):
            platform = self.config.get('Streaming', 'platform', fallback='youtube')
            self.streaming_platform_var.set(platform)
        else:
            self.streaming_platform_var.set('youtube')
            
        self.max_queue_var.set(str(self.max_queue_length))
        self.autoplay_queue = deque(self.autoplay_queue, maxlen=self.max_queue_length)
        print(f"PLAYER: Autoplay queue size set to {self.max_queue_length}")

        for container in [self.scrollable_frame, self.vision_ini_container, self.neurosync_api_scrollable_frame, self.neurosync_main_scrollable_frame]:
            for widget in container.winfo_children(): widget.destroy()
        self.ini_entries.clear()
        self.sensitive_values.clear()
        section_container_map = { 'VisionService': self.vision_ini_container, 'NeurosyncLocalAPI': self.neurosync_api_scrollable_frame, 'Neurosync': self.neurosync_main_scrollable_frame, 'Watcher': self.neurosync_main_scrollable_frame, 'LiveLink': self.neurosync_main_scrollable_frame, }
        default_container = self.scrollable_frame
        tts_sections = {'StyleTTS', 'PocketTTS'}  # TTS sections now have dedicated tab
        osc_sections = {'OSC'}  # OSC section now has dedicated tab
        llm_sections = {'Gemini', 'Ollama', 'OllamaCloud'}  # LLM sections now have dedicated tab
        mcp_section = {'MCP'}  # MCP section now has dedicated tab in LLM tab
        assistant_section = {'Assistant', 'SystemPrompt'}  # Assistant sections now have dedicated tab in LLM tab
        music_sections = {'MusicDownloader'}  # MusicDownloader section now has dedicated tab
        memory_sections = {'RAG', 'Memory', 'Database'}  # Memory sections now have dedicated tab
        for section in self.config.sections():
            if section == 'Audio' or section in tts_sections or section in osc_sections or section in llm_sections or section in mcp_section or section in assistant_section or section in music_sections or section in memory_sections: continue
            parent_container = section_container_map.get(section, default_container)
            if not parent_container: continue
            self.ini_entries[section] = {}
            section_frame = ttk.LabelFrame(parent_container, text=section, padding=10)
            for key, value in self.config.items(section):
                if section == 'VisionService' and key in ('camera_index', 'smol_vlm_model_id'): continue
                row_frame = ttk.Frame(section_frame); row_frame.pack(fill="x", pady=2, padx=2)
                ttk.Label(row_frame, text=f"{key}:", width=20).pack(side="left", anchor="n", pady=2)
                widget = None
                if key in SENSITIVE_KEYS:
                    widget_frame = ttk.Frame(row_frame); widget_frame.pack(side="left", fill="x", expand=True)
                    widget = ttk.Entry(widget_frame, show="*"); widget.insert(0, value); widget.pack(side="left", fill="x", expand=True)
                    self.sensitive_values[widget] = value
                    toggle_button = ttk.Button(widget_frame, text="Show", width=5)
                    toggle_button.config(command=lambda w=widget, b=toggle_button: self.toggle_sensitive_field(w, b))
                    toggle_button.pack(side="left", padx=(5,0))
                elif section == DROPDOWN_SECTION and key == DROPDOWN_KEY:
                    widget = ttk.Combobox(row_frame, values=DROPDOWN_OPTIONS, state="readonly")
                    if value in DROPDOWN_OPTIONS: widget.set(value)
                    widget.pack(side="left", fill="x", expand=True)
                else:
                    widget = ttk.Entry(row_frame); widget.insert(0, value); widget.pack(side="left", fill="x", expand=True)
                if widget: self.ini_entries[section][key] = widget
            if section_frame.winfo_children(): section_frame.pack(fill="x", expand=False, padx=5, pady=5)
        if self.config.has_section('Audio'):
            self.selected_input_device_var.set(self.config.get('Audio', 'selected_input', fallback='None'))
            self.selected_output_device_var.set(self.config.get('Audio', 'selected_output', fallback='None'))
        if self.config.has_section('VisionService'):
            saved_index = self.config.get('VisionService', 'camera_index', fallback='None')
            self.saved_camera_device_var.set(saved_index)
            if hasattr(self, 'camera_combobox') and saved_index in self.camera_combobox['values']: self.camera_combobox.set(saved_index)
            vlm_model_id = self.config.get('VisionService', 'smol_vlm_model_id', fallback='HuggingFaceTB/SmolVLM-500M-Instruct')
            if hasattr(self, 'smol_vlm_entry'):
                self.smol_vlm_entry.delete(0, tk.END); self.smol_vlm_entry.insert(0, vlm_model_id)

    def _send_runtime_update(self, key, value):
        """Sends a live setting update to the running MCP script in a background thread."""
        try:
            MCP_HOST = self.config.get('MCP', 'host', fallback="127.0.0.1")
            MCP_PORT = self.config.get('MCP', 'port', fallback="5000")
            api_url = f"http://{MCP_HOST}:{MCP_PORT}/update_runtime_setting"
            
            payload = {"key": key, "value": value}
            
            requests.post(api_url, json=payload, timeout=3)
            print(f"CONTROL PANEL: Sent live update for '{key}' to MCP.")
            
        except requests.exceptions.RequestException:
            print(f"CONTROL PANEL WARNING: Could not send live update for '{key}'. MCP may not be running.")
        except Exception as e:
            print(f"CONTROL PANEL ERROR: An unexpected error occurred during live update: {e}")

    def save_all_settings(self):
        """Save ALL settings from all tabs to mcp_settings.ini"""
        print("CONTROL PANEL: Saving all settings from all tabs...")
        
        # Save settings from all tabs
        try: self.save_llm_settings()
        except Exception as e: print(f"Warning: Could not save LLM settings: {e}")
        
        try: self.save_memory_settings()
        except Exception as e: print(f"Warning: Could not save memory settings: {e}")
        
        try: self.save_music_settings()
        except Exception as e: print(f"Warning: Could not save music settings: {e}")
        
        try: self.save_osc_settings()
        except Exception as e: print(f"Warning: Could not save OSC settings: {e}")
        
        try: self.save_tts_settings()
        except Exception as e: print(f"Warning: Could not save TTS settings: {e}")
        
        # Save audio/general settings
        self.save_ini_file()
        
        print("CONTROL PANEL: All settings saved successfully!")
        messagebox.showinfo("Success", "ALL settings saved from all tabs!\n\nRemember to restart MCP for changes to take effect.")
    
    def save_ini_file(self):
        music_downloader_enabled_state = self.music_downloader_enabled_var.get()
        
        for section, keys in self.ini_entries.items():
            for key, widget in keys.items():
                value = widget.get()
                self.config.set(section, key, value)
                
        self.config.set('Audio', 'selected_input', self.selected_input_device_var.get())
        self.config.set('Audio', 'selected_output', self.selected_output_device_var.get())
        if hasattr(self, 'camera_combobox'): self.config.set('VisionService', 'camera_index', self.camera_combobox.get() or "None")
        if hasattr(self, 'smol_vlm_entry'): self.config.set('VisionService', 'smol_vlm_model_id', self.smol_vlm_entry.get())
        
        if not self.config.has_section('MusicDownloader'):
            self.config.add_section('MusicDownloader')
            
        self.config.set('MusicDownloader', 'enabled', str(music_downloader_enabled_state).lower())
        
        duration_seconds_to_send = None
        try:
            duration_minutes = int(self.max_duration_var.get())
            duration_seconds = duration_minutes * 60
            self.config.set('MusicDownloader', 'max_download_duration_seconds', str(duration_seconds))
            duration_seconds_to_send = duration_seconds
        except ValueError:
            print("WARNING: Invalid max duration value. This setting will not be saved.")

        try:
            int(self.max_queue_var.get())
            self.config.set('MusicDownloader', 'max_queue_length', self.max_queue_var.get())
        except ValueError:
            print("WARNING: Invalid queue size. Not saving.")

        if not self.config.has_section('Streaming'):
            self.config.add_section('Streaming')
        self.config.set('Streaming', 'platform', self.streaming_platform_var.get())
        
        try:
            with open(INI_FILE_PATH, 'w', encoding='utf-8') as configfile: self.config.write(configfile)
            print("Settings successfully saved to mcp_settings.ini!")
        except Exception as e: 
            print(f"Error writing to INI file: {e}")
            messagebox.showerror("Save Error", f"Could not save settings to file:\n{e}")
            return

        # Reinitialize pygame mixer with new output device
        output_device_str = self.selected_output_device_var.get()
        if output_device_str and output_device_str != 'None' and ']' in output_device_str:
            try:
                device_name = output_device_str.split('] ', 1)[1]
                # Stop any current playback
                pygame.mixer.music.stop()
                # Quit and reinitialize with new device
                pygame.mixer.quit()
                # Set environment variable for DirectSound
                os.environ['SDL_AUDIODRIVER'] = 'directsound'
                # Reinitialize - SDL will use the device name if it matches
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
                print(f"PLAYER: Reinitialized pygame mixer for output device: {device_name}")
            except Exception as e:
                print(f"PLAYER WARNING: Could not reinitialize pygame mixer: {e}")

        threading.Thread(
            target=self._send_runtime_update, 
            args=('music_downloader_enabled', music_downloader_enabled_state), 
            daemon=True
        ).start()

        if duration_seconds_to_send is not None:
            threading.Thread(
                target=self._send_runtime_update,
                args=('max_download_duration_seconds', duration_seconds_to_send),
                daemon=True
            ).start()
        
        platform = self.streaming_platform_var.get()
        threading.Thread(
            target=self.on_platform_change,
            daemon=True
        ).start()

    def toggle_sensitive_field(self, entry_widget, button_widget):
        if button_widget.cget("text") == "Show":
            entry_widget.config(show=""); entry_widget.delete(0, tk.END); entry_widget.insert(0, self.sensitive_values.get(entry_widget, ""))
            button_widget.config(text="Hide")
        else:
            self.sensitive_values[entry_widget] = entry_widget.get(); entry_widget.config(show="*")
            button_widget.config(text="Show")

    def populate_camera_list(self):
        available_cameras = []
        for i in range(10):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap is not None and cap.isOpened():
                available_cameras.append(str(i)); cap.release()
        self.camera_combobox['values'] = available_cameras
    def start_camera_preview(self):
        if self.vision_thread and self.vision_thread.is_alive(): return
        cam_index_str = self.camera_combobox.get()
        if not cam_index_str: return
        self.stop_vision_thread = False
        self.vision_thread = threading.Thread(target=self._video_capture_loop, args=(int(cam_index_str),), daemon=True)
        self.vision_thread.start()
    def stop_camera_preview(self):
        self.stop_vision_thread = True
        self.video_label.config(image='', text="Preview stopped"); self.video_label.image = None
    def _video_capture_loop(self, camera_index):
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.video_frame_queue.put(f"Failed to open camera {camera_index}"); return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        while not self.stop_vision_thread:
            ret, frame = cap.read()
            if not ret: continue
            try: self.video_frame_queue.put_nowait(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            except queue.Full: pass
        cap.release()
    def process_video_queue(self):
        try:
            item = self.video_frame_queue.get_nowait()
            if isinstance(item, str): self.video_label.config(image='', text=item, fg="red"); self.video_label.image = None
            else:
                label_w, label_h = self.video_label.winfo_width(), self.video_label.winfo_height()
                if label_w > 1 and label_h > 1:
                    item.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
                    photo_image = ImageTk.PhotoImage(image=item)
                    self.video_label.config(image=photo_image, text=""); self.video_label.image = photo_image
        except queue.Empty: pass
        self.after(30, self.process_video_queue)
    def populate_device_lists(self):
        try:
            devices = sd.query_devices()
            self.input_listbox.delete(0, tk.END); self.output_listbox.delete(0, tk.END)
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0: self.input_listbox.insert(tk.END, f"[{i}] {d['name']}")
                if d['max_output_channels'] > 0: self.output_listbox.insert(tk.END, f"[{i}] {d['name']}")
        except Exception as e: print(f"Error querying devices: {e}")
    def setup_input_widgets(self, parent_frame):
        device_frame = ttk.Frame(parent_frame); device_frame.pack(pady=5, fill="x")
        ttk.Label(device_frame, text="Selected Input Device:").pack(side="left")
        self.selected_input_device_var = tk.StringVar(value="None")
        ttk.Entry(device_frame, textvariable=self.selected_input_device_var, state="readonly").pack(side="left", fill="x", expand=True, padx=5)
        list_frame = ttk.Frame(parent_frame); list_frame.pack(pady=5, fill="both", expand=True)
        ttk.Label(list_frame, text="Mic device list (Double-click to select):").pack(anchor="w")
        self.input_listbox = tk.Listbox(list_frame, exportselection=False); self.input_listbox.pack(side="left", fill="both", expand=True)
        self.input_listbox.bind("<Double-Button-1>", self.on_input_device_select)
        ttk.Label(parent_frame, text="Input VU Meter:").pack(anchor="w", pady=(5, 0))
        self.input_vu_meter_canvas = tk.Canvas(parent_frame, height=30, bg="lightgrey", relief="sunken"); self.input_vu_meter_canvas.pack(pady=5, fill="x")
    def setup_output_widgets(self, parent_frame):
        device_frame = ttk.Frame(parent_frame); device_frame.pack(pady=5, fill="x")
        ttk.Label(device_frame, text="Selected Output Device:").pack(side="left")
        self.selected_output_device_var = tk.StringVar(value="None")
        ttk.Entry(device_frame, textvariable=self.selected_output_device_var, state="readonly").pack(side="left", fill="x", expand=True, padx=5)
        list_frame = ttk.Frame(parent_frame); list_frame.pack(pady=5, fill="both", expand=True)
        ttk.Label(list_frame, text="Output device list (Double-click to select):").pack(anchor="w")
        self.output_listbox = tk.Listbox(list_frame, exportselection=False); self.output_listbox.pack(side="left", fill="both", expand=True)
        self.output_listbox.bind("<Double-Button-1>", self.on_output_device_select)
        self.test_output_button = ttk.Button(list_frame, text="Test", command=self.toggle_output_test, width=10); self.test_output_button.pack(side="left", padx=5, anchor="n")
        ttk.Label(parent_frame, text="Output Test VU Meter:").pack(anchor="w", pady=(5, 0))
        self.output_vu_meter_canvas = tk.Canvas(parent_frame, height=30, bg="lightgrey", relief="sunken"); self.output_vu_meter_canvas.pack(pady=5, fill="x")
    def on_input_device_select(self, event):
        sel = self.input_listbox.curselection()
        if not sel: return
        self.selected_input_device_var.set(self.input_listbox.get(sel[0]))
        self.start_input_stream(int(self.input_listbox.get(sel[0]).split(']')[0][1:]))
    def on_output_device_select(self, event):
        sel = self.output_listbox.curselection()
        if not sel: return
        self.selected_output_device_var.set(self.output_listbox.get(sel[0]))
    def toggle_output_test(self):
        if self.is_testing_output: self.stop_output_test()
        else:
            sel_text = self.selected_output_device_var.get()
            if sel_text == "None" or "[" not in sel_text: return
            self.start_output_test(int(sel_text.split(']')[0][1:]))
    def start_input_stream(self, device_id):
        if self.input_stream: self.input_stream.close()
        try:
            samplerate = sd.query_devices(device_id, 'input')['default_samplerate']
            self.input_stream = sd.InputStream(device=device_id, channels=1, samplerate=samplerate, callback=self.input_audio_callback); self.input_stream.start()
        except Exception as e: print(f"Error starting input stream: {e}")
    def input_audio_callback(self, indata, frames, time, status):
        rms = np.sqrt(np.mean(indata**2)); current_db = 20 * math.log10(rms) if rms > 0 else MIN_DB
        self.input_audio_queue.put(current_db)
    def start_output_test(self, device_id):
        self.is_testing_output = True; self.test_output_button.config(text="Stop")
        try:
            samplerate = sd.query_devices(device_id, 'output')['default_samplerate']
            self.output_stream = sd.OutputStream(device=device_id, channels=1, samplerate=samplerate, callback=self.output_audio_callback); self.output_stream.start()
        except Exception as e: self.stop_output_test()
    def stop_output_test(self):
        if self.output_stream: self.output_stream.close()
        self.output_stream = None; self.is_testing_output = False
        self.test_output_button.config(text="Test"); self.output_smoothed_db = MIN_DB; self.output_peak_db = MIN_DB
    def output_audio_callback(self, outdata, frames, time, status):
        t = (self.output_start_idx + np.arange(frames)) / self.output_stream.samplerate
        outdata[:] = 0.5 * np.sin(2 * np.pi * TEST_TONE_FREQUENCY * t).reshape(-1, 1)
        self.output_start_idx += frames
        rms = np.sqrt(np.mean(outdata[:]**2)); current_db = 20 * math.log10(rms) if rms > 0 else MIN_DB
        self.output_audio_queue.put(current_db)
    def process_audio_queues(self):
        try:
            current_db = self.input_audio_queue.get_nowait()
            self.input_smoothed_db = (SMOOTHING_FACTOR * self.input_smoothed_db) + ((1 - SMOOTHING_FACTOR) * current_db)
            if self.input_smoothed_db > self.input_peak_db: self.input_peak_db, self.input_peak_hold_time = self.input_smoothed_db, time.time()
        except queue.Empty: pass
        if time.time() - self.input_peak_hold_time > PEAK_HOLD_DURATION: self.input_peak_db = max(self.input_smoothed_db, self.input_peak_db - 2)
        try:
            current_db = self.output_audio_queue.get_nowait()
            self.output_smoothed_db = (SMOOTHING_FACTOR * self.output_smoothed_db) + ((1 - SMOOTHING_FACTOR) * current_db)
            if self.output_smoothed_db > self.output_peak_db: self.output_peak_db, self.output_peak_hold_time = self.output_smoothed_db, time.time()
        except queue.Empty: pass
        if self.is_testing_output:
            if time.time() - self.output_peak_hold_time > PEAK_HOLD_DURATION: self.output_peak_db = max(self.output_smoothed_db, self.output_peak_db - 2)
        else: self.output_smoothed_db = max(MIN_DB, self.output_smoothed_db - 3); self.output_peak_db = max(self.output_smoothed_db, self.output_peak_db - 3)
        self.update_vu_meter_canvas(self.input_vu_meter_canvas, self.input_smoothed_db, self.input_peak_db)
        self.update_vu_meter_canvas(self.output_vu_meter_canvas, self.output_smoothed_db, self.output_peak_db)
        self.after(50, self.process_audio_queues)
    def update_vu_meter_canvas(self, canvas, smoothed_db, peak_db):
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width <= 1: return
        canvas.delete("all")
        bar_len = int(((max(MIN_DB, min(smoothed_db, MAX_DB)) - MIN_DB) / (MAX_DB - MIN_DB)) * width)
        green_w, yellow_w = int(width * 0.7), int(width * 0.9)
        if bar_len > 0: canvas.create_rectangle(0, 0, min(bar_len, green_w), height, fill="#4CAF50", width=0)
        if bar_len > green_w: canvas.create_rectangle(green_w, 0, min(bar_len, yellow_w), height, fill="#FFC107", width=0)
        if bar_len > yellow_w: canvas.create_rectangle(yellow_w, 0, bar_len, height, fill="#F44336", width=0)
        peak_pos = int(((max(MIN_DB, min(peak_db, MAX_DB)) - MIN_DB) / (MAX_DB - MIN_DB)) * width)
        if peak_pos > 1: canvas.create_line(peak_pos, 0, peak_pos, height, fill="black", width=2)
        canvas.create_text(width - 10, height / 2, text=f"{smoothed_db:.2f} dB", anchor="e")

if __name__ == "__main__":
    app = AudioApp()
    app.mainloop()