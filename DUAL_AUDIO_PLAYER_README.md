# Dual Audio Player - Setup Guide

## 🎵 Features

1. **Multi-Device Playback** - Play two audio files simultaneously on different output devices
2. **Wakeword Integration** - Trigger with "Gem sing the song [song name]"
3. **Song Library** - Organized dual-track song management

## 📁 Folder Structure

```
Gem-System/
├── dual_audio_player.py      # Main player GUI
├── song_library.py            # Song file manager
├── song_wakeword.py          # Wakeword handler
├── requests/karaoke/          # Song library folder
│   ├── never_gonna_give_you_up_vocals.wav
│   └── never_gonna_give_you_up_instrumental.wav
└── start_scripts/
    └── Start_Dual_Audio_Player.bat
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
conda activate mcp_env_1
pip install sounddevice scipy numpy
```

### 2. Add Songs to Library

The song library folder is: `requests/karaoke/`

Add dual-track songs with these naming patterns:

**Naming convention:**
- `{songname}_vocals.wav` + `{songname}_instrumental.wav`
- `{songname}_track1.wav` + `{songname}_track2.wav`
- `{songname}_a.wav` + `{songname}_b.wav`

**Example:**
```
requests/karaoke/
├── never_gonna_give_you_up_vocals.wav
├── never_gonna_give_you_up_instrumental.wav
├── sweet_caroline_vocals.wav
└── sweet_caroline_instrumental.wav
```

### 3. Run the Player

**Option A: Batch file**
```
Double-click: start_scripts\Start_Dual_Audio_Player.bat
```

**Option B: Command line**
```bash
python dual_audio_player.py
```

### 4. Use Wakeword (in MCP)

Say or type:
- "Gem sing the song never gonna give you up"
- "Gem sing the song sweet caroline"
- "Sing the song [song name]"

The player will:
1. Find the song files in `music/`
2. Open the dual player
3. Load both files
4. Start playback automatically

## 🎛️ Using the GUI

1. **Select File 1** - Browse for first audio file
2. **Select Output Device 1** - Choose audio device (e.g., Voicemeeter)
3. **Select File 2** - Browse for second audio file
4. **Select Output Device 2** - Choose different device (e.g., Headphones)
5. **Click "▶ PLAY BOTH"** - Play both files simultaneously!

## 🔧 Wakeword Integration in MCP

To integrate with your MCP speech recognition, add this to `mcp_v2.py`:

```python
from song_wakeword import SongWakewordHandler

song_handler = SongWakewordHandler()

# In your speech recognition callback:
def on_speech_detected(text):
    if song_handler.handle_command(text):
        return  # Command was handled
    
    # Continue with normal MCP processing...
```

## 📋 Available Commands

- "Gem sing the song [name]"
- "Sing the song [name]"
- "Gem play the song [name]"
- "Play the song [name]"
- "Gem sing [name]"

## 🎵 Testing

List available songs:
```bash
python song_wakeword.py
```

Test song search:
```bash
python song_library.py
```

## ⚠️ Troubleshooting

**No sound from one device:**
- Check device selection in dropdown
- Verify device is not muted in Windows sound settings
- Make sure device supports output (not input-only)

**Song not found:**
- Check naming convention matches patterns
- Verify files are in `requests/karaoke/` folder
- Run `python song_wakeword.py` to list available songs

**Devices not showing:**
- Install sounddevice: `pip install sounddevice`
- Restart Python after connecting new audio devices
- Check Windows sound control panel

## 🎤 Example Use Case

**Karaoke Setup:**
- File 1: Vocals → Voicemeeter (for streaming)
- File 2: Instrumental → Headphones (for monitoring)
- Both play in perfect sync!

**DJ Setup:**
- File 1: Main mix → Speakers
- File 2: Cue track → Headphones
- Independent volume control per device
