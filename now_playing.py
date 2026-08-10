import tkinter as tk
import os
import time

class NowPlayingOverlay(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Now Playing Overlay")
        self.geometry("600x100+100+100")
        
        # Make window always on top
        self.attributes('-topmost', True)
        
        # Keep title bar so OBS can capture the window
        # self.overrideredirect(True)
        
        # Set background color
        bg_color = "#1a1a1a"
        text_color = "#00ff00"
        
        self.configure(bg=bg_color)
        
        # Label for "Now Playing"
        self.title_label = tk.Label(
            self,
            text="NOW PLAYING",
            font=("Arial", 14, "bold"),
            fg="#888888",
            bg=bg_color
        )
        self.title_label.pack(pady=(10, 0))
        
        # Label for song name
        self.song_label = tk.Label(
            self,
            text="No song playing",
            font=("Arial", 18, "bold"),
            fg=text_color,
            bg=bg_color
        )
        self.song_label.pack(pady=(0, 10))
        
        # Control frame
        control_frame = tk.Frame(self, bg=bg_color)
        control_frame.pack()
        
        # Track moveable state
        self.is_moveable = False
        
        # Start checking for now playing info
        self.check_now_playing()
    
    def toggle_moveable(self):
        """Toggle whether window can be moved (enables click-through)"""
        self.is_moveable = not self.is_moveable
        if self.is_moveable:
            self.move_btn.config(text="Lock Position", bg="#ff9900")
            # Make background transparent for click-through
            self.attributes('-transparentcolor', self['bg'])
        else:
            self.move_btn.config(text="Move Window", bg="#333333")
            # Remove transparency
            self.attributes('-transparentcolor', '')
    
    def check_now_playing(self):
        """Check autoplay.txt and control panel state for current song"""
        try:
            # Check control panel's currently_playing file
            currently_playing = ""
            
            # Try to read from a shared state file
            state_file = "now_playing_state.txt"
            if os.path.exists(state_file):
                with open(state_file, 'r', encoding='utf-8') as f:
                    currently_playing = f.readline().strip()
            
            # Fallback: check autoplay.txt
            if not currently_playing and os.path.exists("autoplay.txt"):
                with open("autoplay.txt", 'r', encoding='utf-8') as f:
                    currently_playing = f.readline().strip()
            
            # Clean up the filename
            if currently_playing:
                # Remove YouTube ID suffix like [stqBS3m-3WE]
                import re
                currently_playing = re.sub(r'\s*\[[a-zA-Z0-9_-]+\]\s*$', '', currently_playing)
                # Remove .mp3 extension
                if currently_playing.endswith('.mp3'):
                    currently_playing = currently_playing[:-4]
                
                self.song_label.config(text=currently_playing)
        except Exception as e:
            print(f"Now Playing Error: {e}")
        
        # Check again in 2 seconds
        self.after(2000, self.check_now_playing)
    
    def start_drag(self, event):
        """Start dragging the window"""
        if not self.is_moveable:
            return
        self.x = event.x
        self.y = event.y
    
    def do_drag(self, event):
        """Drag the window"""
        if not self.is_moveable:
            return
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

if __name__ == "__main__":
    app = NowPlayingOverlay()
    
    # Bind drag events
    app.bind("<ButtonPress-1>", app.start_drag)
    app.bind("<B1-Motion>", app.do_drag)
    
    app.mainloop()
