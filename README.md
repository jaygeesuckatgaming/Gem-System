# Gem-System
Mainly for Windows but should be kind of easy to adapt to Linux..
A multimodal AI assistant system with voice interaction, face animation, music playback, and extensive service integration.

## Table of Contents

- [Overview](#overview)
- [Core Components](#core-components)
- [Audio System](#audio-system)
- [Text-to-Speech](#text-to-speech)
- [Face Animation (Neurosync)](#face-animation-neurosync)
- [Integration & Extensions](#integration--extensions)
- [Configuration](#configuration)
- [Architecture Patterns](#architecture-patterns)
- [Dependencies](#dependencies)
- [Quick Start](#quick-start)

---

## Overview

Gem-System is a comprehensive AI assistant platform featuring:

- **Voice Interaction**: Wake word detection, speech-to-text, and natural language responses
- **Multimodal LLM Support**: Gemini, Ollama (local/cloud), LM Studio, Mintron
- **Vision Integration**: Camera capture with VLM scene analysis (Camera, NDI)
- **Face Animation**: Real-time blendshape generation for Unreal Engine via LiveLink
- **Music System**: YouTube/YouTube Music integration with queue management
- **Twitch Integration**: Chat monitoring and song request handling
- **Vector Memory**: ChromaDB for conversation history and context
- **Multi-device Audio**: Simultaneous playback on different output devices

---

## Core Components

### `mcp_v2.py` - Master Control Program

**Central orchestrator** - Async multimodal MCP server using Quart framework

- **LLM Integration**: Supports Gemini, Ollama (local/cloud), LM Studio, Mintron
- **Vision Service**: Triggers camera capture and VLM analysis on keyword detection
- **TTS Routing**: Routes responses to StyleTTS or PocketTTS based on config
- **Music System**: YouTube music download, playback control, Twitch integration
- **Social Stream**: Integrates Twitch/chat messages into conversation
- **Vector Memory**: ChromaDB for conversation history and context
- **OSC Output**: Sends blendshape data to Unreal Engine via OSC
- **Wake Word Detection**: Configurable wake words and command verbs
- **Timezone/Location**: Automatic timezone detection for contextual responses

### `listen.py` - Audio Input Client

**System "ears"** - Microphone capture with VAD and Whisper transcription

- **VAD (Voice Activity Detection)**: WebRTC VAD with configurable aggressiveness
- **Silence Detection**: Auto-splits speech on 1.5s silence gaps
- **Pre-buffer**: Captures 0.5s before speech detected
- **Whisper Transcription**: Local Whisper model for speech-to-text
- **Device Selection**: Reads input device from `mcp_settings.ini`
- **MCP Integration**: Sends transcribed text to MCP via HTTP POST

### `vision.py` - Vision Service

**Dual-mode camera system**

- **VLM Mode**: Local SmolVLM for scene description (`/scan` endpoint)
- **Camera Service Mode**: Base64-encoded resized images (`/get_image` endpoint)
- **Continuous Capture**: OpenCV camera stream in dedicated thread
- **Trigger-based**: Activates on vision trigger words from MCP
- **Configurable**: Enable/disable local VLM to save resources

### `control_panel.py` - GUI Control Panel

**Tkinter-based control interface**

- **Audio Device Selection**: Dropdown for input/output devices
- **Real-time Meters**: Input/output audio level visualization
- **Settings Editor**: Full INI file editor with syntax highlighting
- **Music Player**: Queue management, play/pause/seek, background music
- **Audio Ducking**: Automatic music volume reduction during TTS playback
- **Camera Preview**: Live camera feed display
- **Service Launchers**: Buttons to start MCP, TTS, Neurosync services
- **Audio Testing**: Test tone generation for output device verification

---

## Audio System

### `audio_player.py` - Simple Audio Watcher

**Lightweight TTS playback** (no face tracking)

- **File Watching**: Monitors `tts_output/server_output.wav`
- **Auto-play**: Plays when file detected, deletes after playback
- **Smart Device Matching**: pygame._sdl2 device name matching
- **Audio Ducking**: Automatically reduces background music volume during TTS
- **Retry Logic**: Handles file locks with 5-retry delete
- **Fallback**: Auto-fallback to default device on failure

### `dual_audio_player.py` - Multi-Device Player

**Simultaneous playback on multiple devices**

- **GUI Interface**: Select two files + two output devices
- **Independent Control**: Separate device selection per file
- **Voicemeeter Optimized**: Defaults to Voicemeeter Input/AUX
- **Threading**: Concurrent playback on separate threads

### `song_wakeword.py` - Music Wakeword Handler

**Voice-controlled music system**

- **Wakeword Detection**: "play song", "queue song" triggers
- **YouTube Search**: YTMusic API for song lookup
- **Queue Management**: Add to playlist or play immediately
- **Integration**: Works with MCP music commands

### `song_library.py` - Music Library Manager

**Local music library management**

- **Library Scanning**: Scans configured folders for MP3/FLAC
- **Metadata**: Reads ID3 tags (artist, album, title)
- **Search**: Full-text search across library
- **Playlist**: Create and manage playlists

---

## Text-to-Speech

### `tts/pocket-tts/server.py` - PocketTTS Server

**CPU-based TTS with voice cloning**

- **FlowLM + Mimi**: Transformer flow model with neural audio codec
- **Voice Cloning**: Reference audio for custom voices
- **Pre-made Voices**: Built-in voice library (alba, anna, etc.)
- **Streaming**: Frame-by-frame generation (80ms frames)
- **HTTP API**: `/tts` endpoint with text + voice parameters
- **Config**: `server_settings.ini` for voice/model settings

### StyleTTS Integration

**External TTS service** (configured in `mcp_settings.ini`)

- **Style Transfer**: Prosody/style from reference audio
- **HTTP Endpoint**: Configurable URL in MCP settings
- **Toggle**: Enable/disable via config

---

## Face Animation (Neurosync)

### `Neurosync/NeuroSync_Player/watcher_to_face.py`

**WAV file to face animation processor**

- **File Watching**: Monitors configured WAV file path
- **Audio Processing**: Extracts MFCC/spectral features
- **Blendshape Generation**: ML model predicts 52 face shapes
- **Live Link**: Sends to Unreal Engine via Epic LiveLink
- **Emote Integration**: Sends "startspeaking"/"stopspeaking" emotes
- **Default Animation**: Idle animation when not speaking
- **Smart Audio Init**: pygame device matching

### `Neurosync/NeuroSync_Local_API/neurosync_local_api.py`

**Flask API for audio-to-blendshape**

- **Endpoint**: `/audio_to_blendshapes` (POST raw audio bytes)
- **Model**: PyTorch model trained on audio→face mapping
- **Response**: JSON array of 52 blendshape values
- **CUDA Support**: Auto-detects GPU, falls back to CPU

### Neurosync Player Components

**`livelink/`** - Epic LiveLink Face integration
- `livelink_init.py`: Socket connection to Unreal
- `faceblendshapes.py`: Blendshape data structures
- `default_animation.py`: Idle animation loop

**`utils/`** - Processing utilities
- `audio_processing.py`: Feature extraction
- `generate_face_shapes.py`: ML inference

**Animation System**
- `blending_anims.py`: Multiple animation blending
- `animation_emotion.py`: Emotion-based animations
- `animation_loader.py`: Load animations from files

---

## Integration & Extensions

### `opencode_integration.py` - OpenCode API Client

**AI coding assistant integration**

- **Session Management**: Create/manage OpenCode sessions
- **Task Execution**: Send prompts, receive code/output
- **Tool Support**: Handles tool calls and skill execution
- **Output Parsing**: Extracts text from multi-part responses
- **ANSI Cleaning**: Removes terminal formatting codes

### `download_worker.py` - YouTube Download Worker

**Music download service**

- **yt-dlp Integration**: Downloads from YouTube/YouTube Music
- **URL Detection**: Auto-detects YouTube URLs vs search queries
- **YTMusic Search**: Searches YouTube Music library
- **MP3 Conversion**: Extracts and converts to MP3
- **Metadata Cleaning**: Removes video IDs from filenames
- **Cookie Support**: Uses `cookies.txt` for authenticated access

### `twitch_music_checker.py` - Twitch Integration

**Twitch chat music requests**

- **Chat Monitoring**: Listens for song request commands
- **Permission System**: VIP/moderator priority
- **Queue Integration**: Adds to song queue
- **Cooldown**: Prevents spam requests

---

## Configuration

### `mcp_settings.ini` - Central Configuration

All settings in one file:

| Section | Key Settings |
|---------|--------------|
| **[MCP]** | LLM choice, host/port, wake words, command verbs |
| **[Audio]** | Input/output device selection (`[ID] DeviceName` format) |
| **[Gemini]** | API key, model name |
| **[Ollama]** | Model, API URL, vision model |
| **[OllamaCloud]** | Cloud model config, API key |
| **[LMStudio]** | Local LLM endpoint |
| **[VisionService]** | Camera index, VLM enable, trigger words, SmolVLM model ID |
| **[StyleTTS]** | TTS URL, enable flag |
| **[PocketTTS]** | TTS URL, enable flag |
| **[SocialStream]** | Session ID, platforms, API URL |
| **[Watcher]** | Target file path for audio watcher |
| **[Music]** | Download folder, queue settings, max duration |
| **[AudioDucking]** | Enable ducking, duck amount (dB), attack/release times |

---

## Architecture Patterns

### Smart Audio Device Matching

Used in `audio_player.py` and `watcher_to_face.py`:

```python
1. pygame.init() → Get device list via pygame._sdl2.get_audio_device_names()
2. Match config device name against available devices (exact or substring)
3. pygame.quit() → Re-init with matched device name
4. Fallback to default if no match found
```

### File Watching Pattern

```python
1. Check file exists
2. Wait for file size to stabilize (write complete)
3. Play/process file
4. Unload mixer to release lock
5. Delete file with retry (handles PermissionError)
```

### Async HTTP Pattern (mcp_v2.py)

```python
- Quart framework for async web server
- httpx for async HTTP client
- Concurrent requests to TTS, vision, LLM endpoints
- Non-blocking file downloads with queue
```

### Streaming TTS (PocketTTS)

```python
- Frame-by-frame generation (80ms @ 12.5Hz)
- StatefulModule base class maintains KV cache
- EOS detection → Continue for N frames after end-of-speech
- LRU cache for voice prompts (avoid re-encoding)
```

### Audio Ducking System

```python
- TTS playback triggers automatic music volume reduction
- Configurable duck amount (-60 to 0 dB)
- Attack time: How quickly music ducks (10-1000ms)
- Release time: How quickly music restores (100-5000ms)
- Smooth volume transitions using stepped interpolation
- Enabled/disabled via Control Panel TTS tab
```

---

## Dependencies

### Core

```
pygame              # Audio playback
sounddevice         # Audio device enumeration
quart, quart-cors   # Async web framework
httpx               # Async HTTP client
transformers        # Whisper, SmolVLM
torch               # PyTorch for ML models
opencv-python       # Camera capture
flask, flask-cors   # TTS and Neurosync APIs
google-generativeai # Gemini API
ollama              # Ollama client
chromadb            # Vector database
python-osc          # OSC output
yt-dlp, ytmusicapi  # YouTube downloads
webrtcvad           # Voice activity detection
keyboard            # Global hotkey detection
numpy               # Array operations
scipy               # Audio processing
Pillow              # Image processing
```

### Neurosync

```
numpy               # Audio feature arrays
flask               # Local API server
PyTorch model       # model.pth (audio→blendshape)
Epic LiveLink Face  # Unreal Engine plugin
```

### TTS (PocketTTS)

```
moshi               # Mimi audio codec
sentencepiece       # Text tokenizer
safetensors         # Model weights
```

---

## Quick Start

### Prerequisites

1. Python 3.10+ installed
2. Unreal Engine with LiveLink Face plugin (for face animation)
3. Voicemeeter or virtual audio cable (optional, for audio routing)

### Installation

```bash
# Install core dependencies
pip install -r requirements.txt

# Install PocketTTS (if using)
cd tts/pocket-tts
pip install -e .

# Install Neurosync dependencies (if using face animation)
cd Neurosync/NeuroSync_Local_API
pip install -r requirements.txt
```

### Configuration

1. Run `control_panel.py` to configure settings
2. Select audio input/output devices
3. Set LLM choice and API keys
4. Configure TTS services (PocketTTS/StyleTTS)
5. Enable/disable Vision Service and set camera index

### Starting the System

```bash
# Option 1: Use the Control Panel GUI
python control_panel.py

# Option 2: Start services manually
python mcp_v2.py              # Master Control Program
python listen.py              # Audio input (separate terminal)
python vision.py              # Vision service (if enabled)
python audio_player.py        # TTS playback (simple mode)
python watcher_to_face.py     # TTS + face animation (Neurosync mode)

# Start TTS server (if using PocketTTS)
cd tts/pocket-tts
python server.py

# Start Neurosync API (if using face animation)
cd Neurosync/NeuroSync_Local_API
python neurosync_local_api.py
```

### Directory Structure

```
Gem-System/
├── mcp_v2.py                 # Master Control Program
├── listen.py                 # Audio input client
├── vision.py                 # Vision service
├── control_panel.py          # GUI control panel
├── audio_player.py           # Simple TTS player
├── dual_audio_player.py      # Multi-device player
├── download_worker.py        # YouTube downloader
├── opencode_integration.py   # OpenCode API client
├── twitch_music_checker.py   # Twitch integration
├── mcp_settings.ini          # Central configuration
├── tts/
│   └── pocket-tts/
│       ├── server.py         # PocketTTS HTTP server
│       └── server_settings.ini
├── Neurosync/
│   ├── NeuroSync_Player/
│   │   └── watcher_to_face.py
│   └── NeuroSync_Local_API/
│       └── neurosync_local_api.py
├── harnesses/                # Test scripts
├── test_scripts/             # Utility tests
└── tts_output/               # TTS output folder
    └── server_output.wav
```

---

## Troubleshooting

### Audio Device Not Found
- Run `control_panel.py` and re-select the audio device
- Check device name format: `[ID] DeviceName`
- Ensure device is not in use by another application

### Mixer Initialization Failed
- Update pygame: `pip install --upgrade pygame`
- Check that SDL2 drivers are installed (Windows)
- Try default device by setting `selected_output = None` in config

### Vision Service Not Starting
- Check camera index in `mcp_settings.ini`
- Disable local VLM (`enable_local_vlm = false`) to save resources
- Verify camera is not in use by another application

### TTS Not Playing
- Ensure `audio_player.py` or `watcher_to_face.py` is running
- Check that `tts_output/server_output.wav` path is correct
- Verify audio output device is set correctly

---

## License

Individual components may have different licenses. Check individual directories for specific licensing terms.

**Neurosync**: Dual-license (MIT for <$1M annual revenue, commercial license required otherwise)

**PocketTTS**: MIT License

**StyleTTS2**: MIT License

---

## Support

For issues, questions, or contributions, please refer to the project repository.
