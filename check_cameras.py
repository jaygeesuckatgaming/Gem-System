import tkinter as tk
from tkinter import ttk
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
import traceback # Import for detailed error reporting

# --- Configuration ---
MIN_DB = -60.0
MAX_DB = 0.0
SMOOTHING_FACTOR = 0.85
PEAK_HOLD_DURATION = 1.5
TEST_TONE_FREQUENCY = 440
INI_FILE_PATH = "mcp_settings.ini"
DROPDOWN_SECTION = "MCP"
DROPDOWN_KEY = "llm_choice"
DROPDOWN_OPTIONS = ["gemini", "ollama", "ollama_vision", "minitron"]

class AudioApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Master Control Panel")
        self.geometry("1200x750")
        self.config = configparser.ConfigParser(interpolation=None)
        self.ini_entries = {}
        self.input_audio_queue = queue.Queue()
        self.output_audio_queue = queue.Queue()
        self.video_frame_queue = queue.Queue()
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

        # --- UI Setup ---
        self.create_widgets()
        self.populate_device_lists()
        self.populate_camera_list()
        self.reload_ini_ui()
        self.process_audio_queues()
        self.process_video_queue()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        audio_ini_tab = ttk.Frame(notebook)
        notebook.add(audio_ini_tab, text="Audio & General Settings")
        vision_tab = ttk.Frame(notebook)
        notebook.add(vision_tab, text="Vision Settings")
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
        self.vision_ini_container = ttk.Frame(vision_settings_frame)
        self.vision_ini_container.pack(fill="both", expand=True, pady=10, anchor="n")

    def setup_ini_widgets(self, parent_frame):
        ini_frame = ttk.LabelFrame(parent_frame, text="mcp_settings.ini (General)")
        ini_frame.pack(fill="both", expand=True)
        self.ini_canvas = tk.Canvas(ini_frame)
        scrollbar = ttk.Scrollbar(ini_frame, orient="vertical", command=self.ini_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.ini_canvas)
        self.canvas_window = self.ini_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.ini_canvas.bind("<Configure>", self._on_canvas_configure)
        self.scrollable_frame.bind("<Configure>", lambda e: self.ini_canvas.configure(scrollregion=self.ini_canvas.bbox("all")))
        self.ini_canvas.configure(yscrollcommand=scrollbar.set)
        self.ini_canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        scrollbar.pack(side="right", fill="y")
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(fill="x", pady=(5,0))
        save_button = ttk.Button(button_frame, text="Save All Settings", command=self.save_ini_file)
        save_button.pack(side="left", expand=True, padx=5)
        reload_button = ttk.Button(button_frame, text="Reload All Settings", command=self.reload_ini_ui)
        reload_button.pack(side="right", expand=True, padx=5)

    def _on_canvas_configure(self, event):
        canvas_width = event.width
        self.ini_canvas.itemconfig(self.canvas_window, width=canvas_width)

    def _read_ini_safely(self):
        self.config = configparser.ConfigParser(interpolation=None)
        try:
            with open(INI_FILE_PATH, 'r', encoding='utf-8') as f: lines = f.readlines()
        except FileNotFoundError: return False, f"File not found: {INI_FILE_PATH}"
        current_section = None; i = 0
        while i < len(lines):
            line = lines[i]; stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith(('#', ';')): i += 1; continue
            if stripped_line.startswith('[') and stripped_line.endswith(']'):
                current_section = stripped_line[1:-1]
                if not self.config.has_section(current_section): self.config.add_section(current_section)
                i += 1; continue
            if current_section and '=' in stripped_line:
                key, value = stripped_line.split('=', 1); key = key.strip()
                full_value_lines = [value.strip()]
                while i + 1 < len(lines) and lines[i + 1].startswith((' ', '\t')):
                    i += 1; full_value_lines.append(lines[i].strip())
                full_value = '\n'.join(full_value_lines)
                self.config.set(current_section, key, full_value)
            i += 1
        return True, ""

    def reload_ini_ui(self):
        for widget in self.scrollable_frame.winfo_children(): widget.destroy()
        if hasattr(self, 'vision_ini_container'):
            for widget in self.vision_ini_container.winfo_children(): widget.destroy()
        self.ini_entries.clear()
        success, error_message = self._read_ini_safely()
        if not success:
            ttk.Label(self.scrollable_frame, text=f"Error reading INI file: {error_message}").pack()
            return
        VISION_SECTIONS = {'VisionService'}
        for section in self.config.sections():
            self.ini_entries[section] = {}
            if section in VISION_SECTIONS:
                parent_container = self.vision_ini_container
                section_frame = ttk.LabelFrame(parent_container, text=f"{section} Settings", padding=10)
                section_frame.pack(fill="x", expand=False, padx=5, pady=5)
            elif section == 'Ollama':
                parent_container = self.scrollable_frame
                section_frame = ttk.LabelFrame(parent_container, text=f"{section} Settings", padding=10)
                ollama_vision_frame = ttk.LabelFrame(self.vision_ini_container, text="Ollama (Vision Model)", padding=10)
            else:
                parent_container = self.scrollable_frame
                section_frame = ttk.LabelFrame(parent_container, text=f"{section} Settings", padding=10)
            for key in self.config.options(section):
                if (section == 'Audio' and key in ['selected_input', 'selected_output']) or \
                   (section == 'VisionService' and key == 'camera_index'):
                    continue
                value = self.config.get(section, key)
                current_key_parent = ollama_vision_frame if (section == 'Ollama' and key == 'vision_model') else section_frame
                row_frame = ttk.Frame(current_key_parent); row_frame.pack(fill="x", pady=2, padx=2)
                label = ttk.Label(row_frame, text=f"{key}:", width=20); label.pack(side="left", anchor="n", pady=2)
                if section == DROPDOWN_SECTION and key == DROPDOWN_KEY:
                    widget = ttk.Combobox(row_frame, values=DROPDOWN_OPTIONS, state="readonly")
                    if value in DROPDOWN_OPTIONS: widget.set(value)
                elif '\n' in value:
                    widget = tk.Text(row_frame, height=8, wrap="word")
                    widget.insert("1.0", value)
                else:
                    widget = ttk.Entry(row_frame)
                    widget.insert(0, value)
                widget.pack(side="left", fill="x", expand=True)
                self.ini_entries[section][key] = widget
            if parent_container == self.scrollable_frame and section_frame.winfo_children():
                section_frame.pack(fill="x", expand=False, padx=5, pady=5)
            if section == 'Ollama' and 'ollama_vision_frame' in locals() and ollama_vision_frame.winfo_children():
                ollama_vision_frame.pack(fill="x", expand=False, padx=5, pady=5)
        try:
            saved_input = self.config.get('Audio', 'selected_input', fallback='None')
            self.selected_input_device_var.set(saved_input)
            saved_output = self.config.get('Audio', 'selected_output', fallback='None')
            self.selected_output_device_var.set(saved_output)
            saved_index = self.config.get('VisionService', 'camera_index', fallback='None')
            self.saved_camera_device_var.set(saved_index)
            available_cam_indices = self.camera_combobox['values']
            if saved_index in available_cam_indices: self.camera_combobox.set(saved_index)
        except Exception as e: print(f"Error loading dedicated settings: {e}")

    def save_ini_file(self):
        settings_to_update = {}
        for section, keys in self.ini_entries.items():
            settings_to_update[section] = {}
            for key, widget in keys.items():
                value = widget.get("1.0", tk.END).strip() if isinstance(widget, tk.Text) else widget.get()
                settings_to_update[section][key] = value
        settings_to_update['Audio'] = {
            'selected_input': self.selected_input_device_var.get(),
            'selected_output': self.selected_output_device_var.get()
        }
        selected_cam_idx = self.camera_combobox.get()
        if 'VisionService' not in settings_to_update: settings_to_update['VisionService'] = {}
        settings_to_update['VisionService']['camera_index'] = selected_cam_idx if selected_cam_idx else "None"
        try:
            with open(INI_FILE_PATH, 'r', encoding='utf-8') as f: lines = f.readlines()
        except FileNotFoundError: lines = []
        new_lines = []; current_section = None; sections_found = set(); i = 0
        while i < len(lines):
            line = lines[i]; stripped_line = line.strip()
            if stripped_line.startswith('[') and stripped_line.endswith(']'):
                current_section = stripped_line[1:-1]; sections_found.add(current_section)
                new_lines.append(line); i += 1
            elif current_section and '=' in stripped_line and not stripped_line.startswith(('#', ';')):
                key = stripped_line.split('=')[0].strip()
                original_block_end_index = i + 1
                while original_block_end_index < len(lines) and lines[original_block_end_index].strip() and lines[original_block_end_index].startswith((' ', '\t')): original_block_end_index += 1
                if current_section in settings_to_update and key in settings_to_update[current_section]:
                    new_val = settings_to_update[current_section][key]
                    if '\n' in new_val:
                        first_line, rest = new_val.split('\n', 1)
                        indented_rest = '\n'.join(['  ' + l.strip() for l in rest.split('\n')])
                        final_val = first_line + '\n' + indented_rest
                    else: final_val = new_val
                    indentation = line[:len(line) - len(line.lstrip())]
                    new_lines.append(f"{indentation}{key} = {final_val}\n")
                    del settings_to_update[current_section][key]
                    if not settings_to_update[current_section]: del settings_to_update[current_section]
                    i = original_block_end_index
                else: new_lines.append(line); i += 1
            else: new_lines.append(line); i += 1
        if settings_to_update:
            for section, keys in settings_to_update.items():
                if section not in sections_found:
                    if new_lines and not new_lines[-1].strip() == "": new_lines.append("\n")
                    new_lines.append(f"[{section}]\n")
                for key, value in keys.items():
                    if '\n' in value:
                        first_line, rest = value.split('\n', 1)
                        indented_rest = '\n'.join(['  ' + l.strip() for l in rest.split('\n')])
                        value = first_line + '\n' + indented_rest
                    new_lines.append(f"{key} = {value}\n")
        try:
            with open(INI_FILE_PATH, 'w', encoding='utf-8') as f: f.writelines(new_lines)
            print("Settings successfully saved, preserving comments and format!")
            self.reload_ini_ui()
        except Exception as e: print(f"Error writing to file: {e}")

    def populate_camera_list(self):
        available_cameras = []
        # Based on diagnostics, we MUST use DSHOW.
        backend_to_use = cv2.CAP_DSHOW
        try:
            for i in range(10):
                cap = cv2.VideoCapture(i, backend_to_use)
                if cap is not None and cap.isOpened():
                    available_cameras.append(str(i))
                    cap.release()
        except Exception:
            print("="*60)
            print("A CRITICAL ERROR occurred while initializing the camera with DSHOW.")
            traceback.print_exc()
            print("="*60)
        
        self.camera_combobox['values'] = available_cameras
        if available_cameras:
            print(f"Found DSHOW cameras: {available_cameras}")
        else:
            print("No cameras could be opened with the DSHOW backend.")

    def start_camera_preview(self):
        if self.vision_thread is not None and self.vision_thread.is_alive(): return
        cam_index_str = self.camera_combobox.get()
        if not cam_index_str: return
        cam_index = int(cam_index_str)
        self.stop_vision_thread = False
        self.vision_thread = threading.Thread(target=self._video_capture_loop, args=(cam_index,), daemon=True)
        self.vision_thread.start()

    def stop_camera_preview(self):
        if self.vision_thread is not None and self.vision_thread.is_alive():
            self.stop_vision_thread = True
        self.video_label.config(image='', text="Preview stopped", fg="white")
        self.video_label.image = None

    def _video_capture_loop(self, camera_index):
        # Based on diagnostics, we MUST use DSHOW.
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"Error: Could not open camera index {camera_index} with DSHOW.")
            self.video_frame_queue.put(f"Failed to open camera {camera_index}")
            return
        while not self.stop_vision_thread:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb_frame)
            try:
                self.video_frame_queue.put_nowait(pil_img)
            except queue.Full:
                pass
        cap.release()

    def process_video_queue(self):
        try:
            item = self.video_frame_queue.get_nowait()
            if isinstance(item, str):
                self.video_label.config(image='', text=item, fg="red")
                self.video_label.image = None
                return
            label_w = self.video_label.winfo_width()
            label_h = self.video_label.winfo_height()
            if label_w > 1 and label_h > 1:
                item.thumbnail((label_w, label_h), Image.Resampling.LANCZOS)
                photo_image = ImageTk.PhotoImage(image=item)
                self.video_label.config(image=photo_image, text="")
                self.video_label.image = photo_image
        except queue.Empty:
            pass
        finally:
            self.after(30, self.process_video_queue)

    def on_closing(self):
        print("Closing application: Signaling threads to stop...")
        self.stop_vision_thread = True
        self.is_testing_output = False
        if self.input_stream:
            self.input_stream.close()
        if self.output_stream:
            self.output_stream.close()
        print("Destroying UI and exiting.")
        self.destroy()

    def populate_device_lists(self):
        try:
            devices = sd.query_devices()
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0: self.input_listbox.insert(tk.END, f"[{i}] {d['name']}")
                if d['max_output_channels'] > 0: self.output_listbox.insert(tk.END, f"[{i}] {d['name']}")
        except Exception as e: print(f"Error querying devices: {e}")

    def setup_input_widgets(self, parent_frame):
        device_frame = ttk.Frame(parent_frame); device_frame.pack(pady=5, fill="x")
        ttk.Label(device_frame, text="Selected Input Device:").pack(side="left", padx=(0, 10))
        self.selected_input_device_var = tk.StringVar(value="None")
        ttk.Entry(device_frame, textvariable=self.selected_input_device_var, state="readonly").pack(side="left", fill="x", expand=True)
        list_frame = ttk.Frame(parent_frame); list_frame.pack(pady=10, fill="both", expand=True)
        ttk.Label(list_frame, text="Mic device list (Double-click to select):").pack(anchor="w")
        self.input_listbox = tk.Listbox(list_frame, exportselection=False); self.input_listbox.pack(side="left", fill="both", expand=True)
        self.input_listbox.bind("<Double-Button-1>", self.on_input_device_select)
        ttk.Label(parent_frame, text="Input VU Meter:").pack(anchor="w", pady=(10, 0))
        self.input_vu_meter_canvas = tk.Canvas(parent_frame, height=30, bg="lightgrey", relief="sunken", borderwidth=1); self.input_vu_meter_canvas.pack(pady=5, fill="x")

    def setup_output_widgets(self, parent_frame):
        device_frame = ttk.Frame(parent_frame); device_frame.pack(pady=5, fill="x")
        ttk.Label(device_frame, text="Selected Output Device:").pack(side="left", padx=(0, 10))
        self.selected_output_device_var = tk.StringVar(value="None")
        ttk.Entry(device_frame, textvariable=self.selected_output_device_var, state="readonly").pack(side="left", fill="x", expand=True)
        list_frame = ttk.Frame(parent_frame); list_frame.pack(pady=10, fill="both", expand=True)
        ttk.Label(list_frame, text="Output device list (Double-click to select):").pack(anchor="w")
        self.output_listbox = tk.Listbox(list_frame, exportselection=False); self.output_listbox.pack(side="left", fill="both", expand=True)
        self.output_listbox.bind("<Double-Button-1>", self.on_output_device_select)
        self.test_output_button = ttk.Button(list_frame, text="Test", command=self.toggle_output_test, width=10); self.test_output_button.pack(side="left", padx=(10, 0), anchor="n")
        ttk.Label(parent_frame, text="Output Test VU Meter:").pack(anchor="w", pady=(10, 0))
        self.output_vu_meter_canvas = tk.Canvas(parent_frame, height=30, bg="lightgrey", relief="sunken", borderwidth=1); self.output_vu_meter_canvas.pack(pady=5, fill="x")

    def on_input_device_select(self, event):
        selection_indices = self.input_listbox.curselection()
        if not selection_indices: return
        selected_text = self.input_listbox.get(selection_indices[0])
        self.selected_input_device_var.set(selected_text)
        device_id = int(selected_text.split(']')[0][1:])
        self.start_input_stream(device_id)

    def on_output_device_select(self, event):
        selection_indices = self.output_listbox.curselection()
        if not selection_indices: return
        selected_text = self.output_listbox.get(selection_indices[0])
        self.selected_output_device_var.set(selected_text)

    def toggle_output_test(self):
        if self.is_testing_output: self.stop_output_test()
        else:
            selected_text = self.selected_output_device_var.get()
            if selected_text == "None" or "[" not in selected_text: return
            device_id = int(selected_text.split(']')[0][1:])
            self.start_output_test(device_id)

    def start_input_stream(self, device_id):
        if self.input_stream: self.input_stream.close()
        try:
            samplerate = sd.query_devices(device_id, 'input')['default_samplerate']
            self.input_stream = sd.InputStream(device=device_id, channels=1, samplerate=samplerate, callback=self.input_audio_callback)
            threading.Thread(target=self.input_stream.start, daemon=True).start()
        except Exception as e: print(f"Error starting input stream: {e}")

    def input_audio_callback(self, indata, frames, time_info, status):
        rms = np.sqrt(np.mean(indata**2)); current_db = 20 * math.log10(rms) if rms > 0 else MIN_DB
        self.input_audio_queue.put(current_db)

    def start_output_test(self, device_id):
        self.is_testing_output = True; self.test_output_button.config(text="Stop")
        try:
            samplerate = sd.query_devices(device_id, 'output')['default_samplerate']
            self.output_stream = sd.OutputStream(device=device_id, channels=1, samplerate=samplerate, callback=self.output_audio_callback)
            threading.Thread(target=self.output_stream.start, daemon=True).start()
        except Exception as e: print(f"Error starting output test: {e}"); self.stop_output_test()

    def stop_output_test(self):
        if self.output_stream: self.output_stream.close()
        self.output_stream = None; self.is_testing_output = False
        self.test_output_button.config(text="Test")
        self.output_smoothed_db = MIN_DB; self.output_peak_db = MIN_DB

    def output_audio_callback(self, outdata, frames, time_info, status):
        t = (self.output_start_idx + np.arange(frames)) / self.output_stream.samplerate; t = t.reshape(-1, 1)
        waveform = 0.5 * np.sin(2 * np.pi * TEST_TONE_FREQUENCY * t); outdata[:] = waveform
        self.output_start_idx += frames
        rms = np.sqrt(np.mean(waveform**2)); current_db = 20 * math.log10(rms) if rms > 0 else MIN_DB
        self.output_audio_queue.put(current_db)

    def process_audio_queues(self):
        try:
            while not self.input_audio_queue.empty():
                current_db = self.input_audio_queue.get_nowait()
                self.input_smoothed_db = (SMOOTHING_FACTOR * self.input_smoothed_db) + ((1 - SMOOTHING_FACTOR) * current_db)
                if self.input_smoothed_db > self.input_peak_db: self.input_peak_db = self.input_smoothed_db; self.input_peak_hold_time = time.time()
        except queue.Empty: pass
        if time.time() - self.input_peak_hold_time > PEAK_HOLD_DURATION: self.input_peak_db = max(self.input_smoothed_db, self.input_peak_db - 2)
        try:
            while not self.output_audio_queue.empty():
                current_db = self.output_audio_queue.get_nowait()
                self.output_smoothed_db = (SMOOTHING_FACTOR * self.output_smoothed_db) + ((1 - SMOOTHING_FACTOR) * current_db)
                if self.output_smoothed_db > self.output_peak_db: self.output_peak_db = self.output_smoothed_db; self.output_peak_hold_time = time.time()
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
        clamped_db = max(MIN_DB, min(smoothed_db, MAX_DB)); bar_length = int(((clamped_db - MIN_DB) / (MAX_DB - MIN_DB)) * width)
        green_w, yellow_w = int(width * 0.7), int(width * 0.9)
        if bar_length > 0: canvas.create_rectangle(0, 0, min(bar_length, green_w), height, fill="#4CAF50", width=0)
        if bar_length > green_w: canvas.create_rectangle(green_w, 0, min(bar_length, yellow_w), height, fill="#FFC107", width=0)
        if bar_length > yellow_w: canvas.create_rectangle(yellow_w, 0, bar_length, height, fill="#F44336", width=0)
        clamped_peak_db = max(MIN_DB, min(peak_db, MAX_DB)); peak_pos = int(((clamped_peak_db - MIN_DB) / (MAX_DB - MIN_DB)) * width)
        if peak_pos > 1: canvas.create_line(peak_pos, 0, peak_pos, height, fill="black", width=2)
        canvas.create_text(width - 10, height / 2, text=f"{smoothed_db:.2f} dB", anchor="e", fill="black")

if __name__ == "__main__":
    if not os.path.exists(INI_FILE_PATH):
        with open(INI_FILE_PATH, "w") as f:
            f.write("[General]\n"
                    "setting1 = value1\n\n"
                    "[Audio]\n"
                    "selected_input = None\n"
                    "selected_output = None\n\n"
                    "[VisionService]\n"
                    "camera_index = None\n\n"
                    f"[{DROPDOWN_SECTION}]\n"
                    f"{DROPDOWN_KEY} = gemini\n")
    app = AudioApp()
    app.mainloop()