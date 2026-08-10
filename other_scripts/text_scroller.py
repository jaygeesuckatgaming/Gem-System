import tkinter as tk
from tkinter import filedialog, messagebox
import sys

class TextScrollerApp:
    def __init__(self, root):
        self.root = root
        self.root.geometry("800x600")
        self.root.configure(bg='black')

        # --- Settings ---
        self.scroll_speed = 5  # Default Speed
        self.tick_rate = 20      # Refresh rate (ms)
        self.is_paused = False
        self.text_content = ""
        self.font_size = 20
        self.font_family = "Arial"
        self.text_color = "white"
        self.bg_color = "black"

        # --- UI Setup ---
        self.canvas = tk.Canvas(root, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # --- Load File ---
        if not self.load_file():
            sys.exit() 

        # --- Create Text Object ---
        self.text_id = self.canvas.create_text(
            20, 600, 
            text=self.text_content,
            fill=self.text_color,
            font=(self.font_family, self.font_size),
            width=760,
            anchor="nw" 
        )

        # --- Bindings ---
        self.root.bind("<space>", self.toggle_pause)
        self.root.bind("<Up>", self.increase_speed)
        self.root.bind("<Down>", self.decrease_speed)
        self.root.bind("r", self.reset_text)          # Press 'R' to restart manually
        self.root.bind("R", self.reset_text)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Configure>", self.on_resize)
        self.root.bind("<MouseWheel>", self.on_mouse_wheel) 
        
        self.update_title()

        # --- Start Loop ---
        self.animate()

    def load_file(self):
        file_path = filedialog.askopenfilename(
            title="Select a Text File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path:
            return False
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                # .strip() removes empty lines at the end so it loops faster
                self.text_content = f.read().strip() 
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Could not read file:\n{e}")
            return False

    def update_title(self):
        state = "[PAUSED]" if self.is_paused else "[PLAYING]"
        self.root.title(f"Teleprompter | Speed: {self.scroll_speed:.1f} | {state} | Press 'R' to Reset")

    def on_resize(self, event):
        new_width = event.width - 40 
        self.canvas.itemconfig(self.text_id, width=new_width)

    def toggle_pause(self, event):
        self.is_paused = not self.is_paused
        self.update_title()

    def reset_text(self, event=None):
        """Force the text back to the bottom immediately"""
        window_height = self.canvas.winfo_height()
        current_x = self.canvas.coords(self.text_id)[0]
        self.canvas.coords(self.text_id, current_x, window_height)

    def increase_speed(self, event):
        self.scroll_speed += 0.5
        self.update_title()

    def decrease_speed(self, event):
        if self.scroll_speed > 0.5: # Don't let speed go to 0 via keys
            self.scroll_speed -= 0.5
        self.update_title()

    def on_mouse_wheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.canvas.move(self.text_id, 0, -50)
        if event.num == 4 or event.delta > 0:
            self.canvas.move(self.text_id, 0, 50)

    def animate(self):
        try:
            if not self.is_paused:
                # 1. Move text up
                self.canvas.move(self.text_id, 0, -self.scroll_speed)

                # 2. Check for Loop
                bbox = self.canvas.bbox(self.text_id)
                # bbox = (x1, y1, x2, y2) -> y2 is the bottom edge
                
                if bbox:
                    bottom_edge = bbox[3]
                    
                    # If the text has gone completely off the top...
                    if bottom_edge < 0:
                        self.reset_text()

        except Exception as e:
            print(f"Error in loop: {e}")

        # Ensure the loop always runs
        self.root.after(self.tick_rate, self.animate)

if __name__ == "__main__":
    root = tk.Tk()
    app = TextScrollerApp(root)
    root.mainloop()