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
        self.geometry("1400x880")

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

        self.create_widgets()
        self.populate_device_lists()
        self.populate_camera_list()
        self.reload_ini_ui()
        self.process_audio_queues()
        self.process_video_queue()
        self.update_song_progress()
        self.check_for_autoplay()

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
            text="Enable New Settings",
            command=self.save_ini_file
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
        self.voice_file_var = tk.StringVar(value="StyleTTS2/voices/earn_lucky_pitch_minus_one_samplerate_24000_short_mono.wav")
        voice_entry = ttk.Entry(voice_frame, textvariable=self.voice_file_var, width=70)
        voice_entry.pack(fill="x", pady=(0, 10))
        
        ttk.Label(voice_frame, text="Pocket TTS uses voice cloning with truncate=True for better quality.", 
                 foreground="gray").pack(anchor="w")
        
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
        
        # Status info
        status_frame = ttk.LabelFrame(parent_frame, text="TTS Status", padding=10)
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.tts_status_label = ttk.Label(status_frame, text="Status: Not running", foreground="gray")
        self.tts_status_label.pack(anchor="w")
        
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
            
            messagebox.showinfo("Success", "TTS settings saved to mcp_settings.ini!\n\nRemember to restart MCP for changes to take effect.")
            self.tts_status_label.config(text="Status: Settings saved!", foreground="green")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save TTS settings:\n{e}")
            self.tts_status_label.config(text="Status: Save failed!", foreground="red")
    
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
        save_button = ttk.Button(button_frame, text="Save All Settings", command=self.save_ini_file)
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
    def _run_start_script(self, bat_file_name):
        script_path = os.path.join(os.path.dirname(__file__), "start_scripts", bat_file_name)
        try:
            subprocess.Popen(script_path, creationflags=subprocess.CREATE_NEW_CONSOLE)
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
        for section in self.config.sections():
            if section == 'Audio' or section in tts_sections: continue
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