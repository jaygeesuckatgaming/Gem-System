"""
Dual Audio Player - Multi-Device Version
Play two audio files simultaneously on different output devices
"""

import tkinter as tk
from tkinter import ttk, filedialog
import sounddevice as sd
import numpy as np
import threading
import os
from pathlib import Path

class DualAudioPlayer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dual Audio Player - Multi-Device")
        self.root.geometry("750x500")
        self.root.resizable(True, True)
        
        self.file1_path = tk.StringVar()
        self.file2_path = tk.StringVar()
        self.device1_var = tk.StringVar()
        self.device2_var = tk.StringVar()
        self.is_playing = False
        
        # Get available audio devices
        self.devices = self.get_audio_devices()
        
        self.setup_ui()
        self.load_devices()
    
    def get_audio_devices(self):
        """Get list of available audio output devices"""
        devices = []
        try:
            device_list = sd.query_devices()
            for dev in device_list:
                if dev['max_output_channels'] > 0:
                    devices.append({
                        'id': dev['index'],
                        'name': dev['name']
                    })
        except Exception as e:
            print(f"Error getting devices: {e}")
        return devices
    
    def setup_ui(self):
        # File 1 + Device 1
        file1_frame = ttk.LabelFrame(self.root, text="Audio File 1 + Output Device", padding=10)
        file1_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Entry(file1_frame, textvariable=self.file1_path, width=40).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(file1_frame, text="Browse", command=self.browse_file1).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(file1_frame, text="Output Device:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.device1_combo = ttk.Combobox(file1_frame, textvariable=self.device1_var, width=50, state="readonly")
        self.device1_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # File 2 + Device 2
        file2_frame = ttk.LabelFrame(self.root, text="Audio File 2 + Output Device", padding=10)
        file2_frame.pack(fill="x", padx=20, pady=10)
        
        ttk.Entry(file2_frame, textvariable=self.file2_path, width=40).grid(row=0, column=0, padx=5, pady=5)
        ttk.Button(file2_frame, text="Browse", command=self.browse_file2).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(file2_frame, text="Output Device:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.device2_combo = ttk.Combobox(file2_frame, textvariable=self.device2_var, width=50, state="readonly")
        self.device2_combo.grid(row=1, column=1, padx=5, pady=5)
        
        # Play/Stop buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=20)
        
        self.play_btn = ttk.Button(button_frame, text="▶ PLAY BOTH", command=self.play_both, width=20)
        self.play_btn.pack(side="left", padx=10)
        
        self.stop_btn = ttk.Button(button_frame, text="■ STOP", command=self.stop, width=10)
        self.stop_btn.pack(side="left", padx=10)
        
        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, font=('TkDefaultFont', 10)).pack(pady=10)
        
        # Device info
        device_info = f"Available devices: {len(self.devices)}"
        ttk.Label(self.root, text=device_info, font=('TkDefaultFont', 8), foreground="gray").pack(side="bottom", pady=5)
    
    def load_devices(self):
        """Populate device dropdowns"""
        device_names = [f"[{d['id']}] {d['name']}" for d in self.devices]
        self.device1_combo['values'] = device_names
        self.device2_combo['values'] = device_names
        
        if device_names:
            # Default: Device 1 = Voicemeeter Input (VAIO), Device 2 = Voicemeeter AUX (VAIO)
            device1_set = False
            device2_set = False
            
            for name in device_names:
                name_lower = name.lower()
                # Device 1: Voicemeeter Input VAIO (prefer 2-channel version)
                if not device1_set and "voicemeeter input" in name_lower and "vaio" in name_lower:
                    self.device1_var.set(name)
                    device1_set = True
                # Device 2: Voicemeeter AUX Input VAIO
                elif not device2_set and "voicemeeter aux" in name_lower and "vaio" in name_lower:
                    self.device2_var.set(name)
                    device2_set = True
            
            # Fallback if not found
            if not device1_set:
                for name in device_names:
                    if "voicemeeter input" in name.lower():
                        self.device1_var.set(name)
                        device1_set = True
                        break
            if not device2_set:
                for name in device_names:
                    if "voicemeeter aux" in name.lower():
                        self.device2_var.set(name)
                        device2_set = True
                        break
            
            # Final fallback
            if not device1_set and device_names:
                self.device1_var.set(device_names[0])
            if not device2_set and len(device_names) > 1:
                self.device2_var.set(device_names[-1])
    
    def browse_file1(self):
        filename = filedialog.askopenfilename(
            title="Select Audio File 1",
            filetypes=[("WAV files", "*.wav"), ("MP3 files", "*.mp3"), ("All files", "*.*")]
        )
        if filename:
            self.file1_path.set(filename)
    
    def browse_file2(self):
        filename = filedialog.askopenfilename(
            title="Select Audio File 2",
            filetypes=[("WAV files", "*.wav"), ("MP3 files", "*.mp3"), ("All files", "*.*")]
        )
        if filename:
            self.file2_path.set(filename)
    
    def get_device_id(self, device_str):
        """Extract device ID from dropdown string"""
        try:
            device_id = int(device_str.split(']')[0].strip('['))
            print(f"Device ID extracted from '{device_str}' = {device_id}")
            return device_id
        except Exception as e:
            print(f"Error extracting device ID: {e}")
            return None
    
    def play_file_on_device(self, filepath, device_id, device_name):
        """Play audio file on specific device"""
        try:
            # Read audio file
            import scipy.io.wavfile as wavfile
            sample_rate, audio_data = wavfile.read(filepath)
            
            # Convert to float for sounddevice
            if audio_data.dtype == np.int16:
                audio_data = audio_data / 32768.0
            elif audio_data.dtype == np.int32:
                audio_data = audio_data / 2147483648.0
            
            # Play on specified device
            print(f"Playing {filepath} on device {device_id} ({device_name})")
            sd.play(audio_data, sample_rate, device=device_id)
            sd.wait()  # Wait for completion
            print(f"Finished playing {filepath}")
            
        except Exception as e:
            print(f"Error playing {filepath} on device {device_id}: {e}")
    
    def play_both(self):
        if self.is_playing:
            return
        
        file1 = self.file1_path.get()
        file2 = self.file2_path.get()
        
        if not file1 or not file2:
            self.status_var.set("Please select both audio files!")
            return
        
        device1_str = self.device1_var.get()
        device2_str = self.device2_var.get()
        device1_id = self.get_device_id(device1_str)
        device2_id = self.get_device_id(device2_str)
        
        if device1_id is None or device2_id is None:
            self.status_var.set("Please select valid output devices!")
            return
        
        # Verify devices are different
        if device1_id == device2_id:
            self.status_var.set("WARNING: Both files using same device! Select different devices.")
            print(f"⚠️  Both devices are the same: {device1_id}")
        
        self.is_playing = True
        self.play_btn.config(state="disabled")
        self.status_var.set(f"Playing: Device {device1_id} (Vocals) + Device {device2_id} (Instrumental)")
        
        print(f"🎵 Playing File 1 on Device {device1_id}: {device1_str}")
        print(f"🎵 Playing File 2 on Device {device2_id}: {device2_str}")
        
        # Play both files simultaneously on different devices
        thread1 = threading.Thread(target=self.play_file_on_device, args=(file1, device1_id, device1_str))
        thread2 = threading.Thread(target=self.play_file_on_device, args=(file2, device2_id, device2_str))
        
        thread1.daemon = True
        thread2.daemon = True
        
        thread1.start()
        thread2.start()
        
        # Monitor playback
        self.check_playback(thread1, thread2)
    
    def check_playback(self, thread1, thread2):
        if thread1.is_alive() or thread2.is_alive():
            self.root.after(100, self.check_playback, thread1, thread2)
        else:
            self.is_playing = False
            self.play_btn.config(state="normal")
            self.status_var.set("Playback complete")
    
    def stop(self):
        sd.stop()
        self.is_playing = False
        self.play_btn.config(state="normal")
        self.status_var.set("Stopped")
    
    def load_files(self, file1, file2, device1_name=None, device2_name=None):
        """Programmatically load files and optionally set devices"""
        self.file1_path.set(file1)
        self.file2_path.set(file2)
        
        if device1_name:
            for i, name in enumerate(self.device1_combo['values']):
                if device1_name.lower() in name.lower():
                    self.device1_var.set(name)
                    break
        
        if device2_name:
            for i, name in enumerate(self.device2_combo['values']):
                if device2_name.lower() in name.lower():
                    self.device2_var.set(name)
                    break
        
        # Auto-play after loading
        self.root.after(500, self.play_both)
    
    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = DualAudioPlayer()
    app.run()
