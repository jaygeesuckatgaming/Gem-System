# ==============================================================================
#                      Master Control Program (mcp.py)
#          - UNIFIED MULTIMODAL & PIPELINED ARCHITECTURE (ASYNC/QUART) -
# ==============================================================================

import asyncio
import keyboard
import httpx  # Replaces requests for async
import json
import configparser
import sys
import os
import platform
import ssl
import google.generativeai as genai
import re
import datetime
import pytz
import chromadb
from collections import deque
from pythonosc import udp_client, osc_message_builder
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
import threading  # Kept for the download worker queue
import html

# --- ASYNC FRAMEWORK ---
from quart import Quart, request, jsonify
from quart_cors import cors

import subprocess
import traceback
import queue
import yt_dlp
import ytmusicapi
from ollama import Client

# Import Twitch music checker
from twitch_music_checker import TwitchMusicChecker

# Import OpenCode integration
from opencode_integration import OpenCodeIntegration

import sounddevice as sd
import soundfile as sf
import websockets

# --- NEW: LOCAL LOGGER CONFIG ---
LOCAL_LOGGER_URL = "http://127.0.0.1:14300/chat"


# --- 1. CONFIGURATION LOADING ---
# ------------------------------------------------------------------------------
def load_config():
    """Loads all settings from the mcp_settings.ini file."""
    global MUSIC_RECOGNITION_ENABLED, MUSIC_RECOGNITION_SETTINGS

    config_file = "mcp_settings.ini"
    config_parser = configparser.ConfigParser(interpolation=None)
    if not os.path.exists(config_file):
        sys.exit(f"FATAL ERROR: Config file '{config_file}' not found.")
    config_parser.read(config_file)
    settings = {}
    try:
        settings["system_prompt"] = config_parser.get(
            "SystemPrompt", "prompt", fallback=""
        ).strip()
        settings["llm_choice"] = config_parser.get("MCP", "llm_choice")
        settings["host"] = config_parser.get("MCP", "host")
        settings["port"] = config_parser.getint("MCP", "port")
        settings["max_response_length"] = config_parser.getint(
            "Assistant", "max_response_length", fallback=0
        )
        raw_wake_words = config_parser.get("Assistant", "wake_words", fallback="")
        settings["wake_words"] = [
            word.strip().lower() for word in raw_wake_words.split(",") if word.strip()
        ]
        raw_command_verbs = config_parser.get("Assistant", "command_verbs", fallback="")
        settings["command_verbs"] = [
            verb.strip().lower()
            for verb in raw_command_verbs.split(",")
            if verb.strip()
        ]
        settings["vision_service_scan_url"] = config_parser.get(
            "VisionService", "scan_url"
        )
        settings["vision_service_get_image_url"] = config_parser.get(
            "VisionService", "vision_service_get_image_url", fallback=""
        )
        raw_triggers = config_parser.get(
            "VisionService", "vision_trigger_words", fallback=""
        )
        settings["vision_trigger_words"] = [
            word.strip().lower() for word in raw_triggers.split(",") if word.strip()
        ]
        settings["social_stream_enabled"] = config_parser.getboolean(
            "SocialStream", "enabled", fallback=False
        )
        settings["social_stream_session_id"] = config_parser.get(
            "SocialStream", "session_id"
        )
        raw_platforms = config_parser.get(
            "SocialStream", "target_platforms", fallback=""
        )
        settings["social_stream_targets"] = [
            p.strip() for p in raw_platforms.split(",") if p.strip()
        ]
        settings["social_stream_api_url"] = config_parser.get("SocialStream", "api_url")
        settings["styletts_enabled"] = config_parser.getboolean(
            "StyleTTS", "enabled", fallback=False
        )
        settings["styletts_url"] = config_parser.get("StyleTTS", "tts_url")
        settings["pockettts_enabled"] = config_parser.getboolean(
            "PocketTTS", "enabled", fallback=False
        )
        settings["pockettts_url"] = config_parser.get("PocketTTS", "tts_url", fallback="http://127.0.0.1:13301/tts")
        settings["gemini_api_key"] = config_parser.get("Gemini", "api_key")
        settings["gemini_model"] = config_parser.get("Gemini", "model")
        settings["ollama_model"] = config_parser.get("Ollama", "model")
        settings["ollama_vision_model"] = config_parser.get(
            "Ollama", "vision_model", fallback=""
        )
        settings["ollama_embedding_model"] = config_parser.get(
            "Ollama", "embedding_model", fallback=""
        )
        settings["ollama_api_url"] = config_parser.get("Ollama", "api_url")

        # --- NEW: OLLAMA CLOUD CONFIG ---
        if config_parser.has_section("OllamaCloud"):
            settings["ollama_cloud_base_url"] = config_parser.get(
                "OllamaCloud", "api_url", fallback="https://ollama.com"
            )
            settings["ollama_cloud_model"] = config_parser.get(
                "OllamaCloud", "model", fallback="gpt-oss:120b"
            )
            settings["ollama_cloud_api_key"] = config_parser.get(
                "OllamaCloud", "api_key", fallback=""
            )
        else:
            settings["ollama_cloud_base_url"] = "https://ollama.com"
            settings["ollama_cloud_model"] = "gpt-oss:120b"
            settings["ollama_cloud_api_key"] = ""
        # --------------------------------

        # --- NEW: LM STUDIO CONFIG ---
        # Defaulting to standard LM Studio port 1234
        if config_parser.has_section("LMStudio"):
            settings["lm_studio_base_url"] = config_parser.get(
                "LMStudio", "base_url", fallback="http://localhost:1234/v1"
            )
        else:
            settings["lm_studio_base_url"] = "http://localhost:1234/v1"
        # -----------------------------

        settings["osc_enabled"] = config_parser.getboolean(
            "OSC", "enabled", fallback=False
        )
        settings["osc_ip"] = config_parser.get("OSC", "ip")
        settings["osc_port"] = config_parser.getint("OSC", "port")
        settings["osc_address"] = config_parser.get("OSC", "address")
        raw_osc_verbs = config_parser.get("OSC", "trigger_verbs", fallback="")
        settings["osc_trigger_verbs"] = [
            verb.strip().lower() for verb in raw_osc_verbs.split(",") if verb.strip()
        ]
        raw_rag_triggers = config_parser.get("RAG", "rag_trigger_words", fallback="")
        settings["rag_trigger_words"] = [
            trigger.strip().lower()
            for trigger in raw_rag_triggers.split(",")
            if trigger.strip()
        ]

        settings["audio_selected_input_raw"] = config_parser.get(
            "Audio", "selected_input", fallback=""
        ).strip()

        if config_parser.has_section("MusicRecognition"):
            settings["music_recognition_enabled"] = config_parser.getboolean(
                "MusicRecognition", "enabled", fallback=False
            )
            if settings["music_recognition_enabled"]:
                MUSIC_RECOGNITION_ENABLED = True

                MUSIC_RECOGNITION_SETTINGS["rapidapi_key"] = config_parser.get(
                    "MusicRecognition", "rapidapi_key", fallback=""
                ).strip()
                MUSIC_RECOGNITION_SETTINGS["rapidapi_host"] = config_parser.get(
                    "MusicRecognition", "rapidapi_host", fallback=""
                ).strip()
                MUSIC_RECOGNITION_SETTINGS["recognition_endpoint_url"] = (
                    config_parser.get(
                        "MusicRecognition", "recognition_endpoint_url", fallback=""
                    ).strip()
                )
                MUSIC_RECOGNITION_SETTINGS["audio_duration"] = config_parser.getint(
                    "MusicRecognition", "audio_duration", fallback=8
                )
                MUSIC_RECOGNITION_SETTINGS["sample_rate"] = config_parser.getint(
                    "MusicRecognition", "sample_rate", fallback=44100
                )
                MUSIC_RECOGNITION_SETTINGS["channels"] = config_parser.getint(
                    "MusicRecognition", "channels", fallback=1
                )
                MUSIC_RECOGNITION_SETTINGS["temp_audio_filename"] = config_parser.get(
                    "MusicRecognition",
                    "temp_audio_filename",
                    fallback="temp_recognition_clip.wav",
                )

                raw_music_triggers = config_parser.get(
                    "MusicRecognition",
                    "trigger_words",
                    fallback="what song is this,identify this music,what is playing",
                )
                settings["music_trigger_words"] = [
                    word.strip().lower()
                    for word in raw_music_triggers.split(",")
                    if word.strip()
                ]
            else:
                MUSIC_RECOGNITION_ENABLED = False
        else:
            settings["music_recognition_enabled"] = False
            MUSIC_RECOGNITION_ENABLED = False

        if config_parser.has_section("MusicDownloader"):
            raw_download_triggers = config_parser.get(
                "MusicDownloader", "trigger_words", fallback=""
            )
            settings["download_trigger_words"] = [
                word.strip().lower()
                for word in raw_download_triggers.split(",")
                if word.strip()
            ]
            settings["music_downloader_enabled"] = config_parser.getboolean(
                "MusicDownloader", "enabled", fallback=False
            )
            settings["max_download_duration_seconds"] = config_parser.getint(
                "MusicDownloader", "max_download_duration_seconds", fallback=600
            )
        else:
            settings["download_trigger_words"] = []
            settings["music_downloader_enabled"] = False
            settings["max_download_duration_seconds"] = 600

    except Exception as e:
        sys.exit(
            f"FATAL ERROR: A setting is missing or invalid in '{config_file}'. Details: {e}"
        )
    return settings


# ------------------------------------------------------------------------------


def select_audio_device():
    """Selects an audio input device."""
    print("\n" + "-" * 70)
    print("--- Configuring Audio Device for Music Recognition ---")

    configured_device_str = config.get("audio_selected_input_raw", "")

    try:
        devices = sd.query_devices()
        input_devices = {d["index"]: d for d in devices if d["max_input_channels"] > 0}

        if not input_devices:
            print("MCP ERROR: No audio input devices found.")
            return None

        if configured_device_str:
            match = re.match(r"\[(\d+)\]", configured_device_str)
            if match:
                configured_index = int(match.group(1))
                if configured_index in input_devices:
                    device_name = input_devices[configured_index]["name"]
                    print(
                        f"MCP INFO: Using configured audio device from settings: Index {configured_index} ('{device_name}')"
                    )
                    return configured_index

        default_idx = sd.default.device[0]
        if default_idx in input_devices:
            return default_idx

        return next(iter(input_devices))

    except Exception as e:
        print(f"MCP ERROR: Could not query or configure audio devices. Details: {e}")
        return None


# ------------------------------------------------------------------------------


# --- 2. INITIALIZATION ---
# ------------------------------------------------------------------------------
MUSIC_RECOGNITION_ENABLED = False
MUSIC_RECOGNITION_SETTINGS = {}

config = load_config()

# --- QUART INIT ---
app = Quart(__name__)
app = cors(app, allow_origin="*")

gemini_model = None

VISION_HISTORY = deque(maxlen=5)
CURRENT_LOCATION = "the stream room"
SELECTED_INPUT_DEVICE_INDEX = None
download_queue = queue.Queue()

# OpenCode Integration
OPENCODE_CLIENT = None
OPENCODE_ENABLED = False

from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL_NAME = "google/embedding-gemma-300m"
local_embedding_model = None
try:
    if config["llm_choice"] == "gemini":
        local_embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        print(
            f"MCP INFO: Successfully loaded local embedding model: {EMBEDDING_MODEL_NAME}"
        )
except Exception as e:
    print(
        f"MCP WARNING: Could not load local embedding model. RAG with Gemini will fail. Details: {e}"
    )

try:
    chroma_client = chromadb.PersistentClient(path="gem_memory_db")
    chat_collection = chroma_client.get_or_create_collection(name="chat_history")
    image_collection = chroma_client.get_or_create_collection(name="images")
    print("MCP INFO: ChromaDB vector database is ready.")
except Exception as e:
    sys.exit(f"MCP FATAL ERROR: Could not initialize ChromaDB. Details: {e}")

geolocator = None
tf = None
geolocator = None
tf = None
try:
    tf = TimezoneFinder()
    print("MCP INFO: TimezoneFinder initialized.")
except Exception as e:
    print(f"MCP WARNING: TimezoneFinder failed: {e}")

# Geolocator disabled due to SSL issues - using fallback
print("MCP INFO: Geocoding disabled (SSL issues). Using fallback location.")
print("MCP WARNING: Time queries will fail. Check your internet connection.")


# ASYNC: Made async to use httpx
async def verify_ollama_models():
    if config["llm_choice"] == "ollama_cloud":
        return
    if "ollama" not in config["llm_choice"]:
        return
    print("MCP INFO: Verifying that required Ollama models are available...")
    try:
        tags_url = config["ollama_api_url"].replace("/api/chat", "/api/tags")
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(tags_url)
        response.raise_for_status()
        installed_models = {
            model["name"] for model in response.json().get("models", [])
        }
    except Exception as e:
        print(f"MCP WARNING: Could not get model list from Ollama. Details: {e}")
        return
    required_models = set()
    if config["llm_choice"] == "ollama":
        required_models.add(config.get("ollama_model"))
    elif config["llm_choice"] == "ollama_vision":
        required_models.add(config.get("ollama_vision_model"))
    required_models.add(config.get("ollama_embedding_model"))
    required_models.discard(None)
    required_models.discard("")
    all_models_found = True
    for model_name in required_models:
        if model_name not in installed_models:
            print(
                f"\nFATAL ERROR: The required Ollama model '{model_name}' is not available."
            )
            all_models_found = False
    if not all_models_found:
        sys.exit(1)
    print("MCP INFO: All required Ollama models were found.")


# Note: We keep synchronous logic for Gemini init as it's a library call during startup
if config["llm_choice"] == "gemini":
    print("MCP INFO: Initializing Gemini...")
    try:
        if (
            not config["gemini_api_key"]
            or config["gemini_api_key"] == "YOUR_GEMINI_API_KEY_HERE"
        ):
            sys.exit("FATAL ERROR: llm_choice is 'gemini' but api_key is not set.")
        genai.configure(api_key=config["gemini_api_key"])
        gemini_model = genai.GenerativeModel(config["gemini_model"])
        print(f"MCP INFO: Gemini model '{config['gemini_model']}' loaded.")
    except Exception as e:
        sys.exit(f"MCP FATAL ERROR: Failed to configure Gemini API. Details: {e}")
elif config["llm_choice"] == "lm_studio":
    print(f"MCP INFO: Initializing LM Studio Mode.")
    print(
        f"MCP INFO: Ensure LM Studio server is running at {config['lm_studio_base_url']}"
    )
elif config["llm_choice"] in ["ollama", "ollama_vision", "ollama_cloud"]:
    # Run async verification in the event loop at startup
    try:
        asyncio.run(verify_ollama_models())
    except Exception as e:
        sys.exit(f"MCP FATAL ERROR: Ollama Check Failed. {e}")

osc_client = None
if config["osc_enabled"]:
    try:
        osc_client = udp_client.SimpleUDPClient(config["osc_ip"], config["osc_port"])
        print(
            f"MCP INFO: OSC client configured to send to {config['osc_ip']}:{config['osc_port']}"
        )
    except Exception as e:
        print(f"MCP WARNING: Could not create OSC client. Details: {e}")

# OpenCode Integration Initialization
try:
    OPENCODE_CLIENT = OpenCodeIntegration(
        api_url="http://localhost:4096",
        workspace="C:\\Users\\jayge\\Documents\\AI\\Gem-System"
    )
    OPENCODE_ENABLED = True
    print("MCP INFO: OpenCode integration initialized")
except Exception as e:
    print(f"MCP WARNING: Could not initialize OpenCode integration: {e}")
    OPENCODE_ENABLED = False
# ------------------------------------------------------------------------------


# --- 3. CORE HELPER FUNCTIONS (ASYNC CONVERSION) ---
# ------------------------------------------------------------------------------
def clear_screen():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")


# --- NEW: IMPROVED RELAY FOR LOCAL CHAT LOGGER ---
async def send_to_local_logger(payload: dict):
    """Relays a complete data payload to the separate Flask Chat Logger script."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(LOCAL_LOGGER_URL, json=payload)
    except Exception as e:
        print(f"MCP ERROR: Could not forward to local logger: {e}")


async def log_assistant_response(text: str, source_name: str = "MasterControl"):
    """Constructs a full chat payload for the AI response and sends it to the logger."""
    payload = {
        "user": "Gemini",
        "chatmessage": text,
        "type": "MCP-AI",
        "sourceName": source_name,
        "timestamp": int(datetime.datetime.now().timestamp() * 1000),
    }
    await send_to_local_logger(payload)


def get_gemini_embedding(text: str = None, image_base64: str = None) -> list[float]:
    # CPU bound: will run in executor
    if not text:
        return None
    if image_base64:
        print(
            "MCP WARNING: Local SentenceTransformer embedding does not support images."
        )
    if local_embedding_model is None:
        return None
    try:
        embedding_array = local_embedding_model.encode(text, convert_to_tensor=False)
        return embedding_array.tolist()
    except Exception as e:
        print(f"MCP ERROR: Local Gemini embedding failed: {e}")
        return None


async def get_embedding(text: str = None, image_base64: str = None) -> list[float]:
    if not text and not image_base64:
        return None

    if config["llm_choice"] == "lm_studio":
        # LM Studio Embeddings (OpenAI Compatible)
        try:
            url = f"{config['lm_studio_base_url']}/embeddings"
            # LM Studio infers model from what is loaded, but "model" field is required
            payload = {"model": "local-model", "input": text if text else " "}
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
        except Exception as e:
            print(
                f"MCP ERROR: LM Studio embedding failed (Check if embedding model is loaded): {e}"
            )
            return None

    if config["llm_choice"] in ["ollama", "ollama_vision", "ollama_cloud"]:
        model_to_use = config.get("ollama_embedding_model")
        if not model_to_use:
            return None
        payload = {"model": model_to_use, "prompt": text if text else " "}
        if image_base64:
            payload["images"] = [image_base64]
        try:
            embed_url = config["ollama_api_url"].replace("/api/chat", "/api/embeddings")
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(embed_url, json=payload)
            response.raise_for_status()
            return response.json().get("embedding")
        except Exception as e:
            print(f"MCP ERROR: Ollama embedding failed: {e}")
            return None
    elif config["llm_choice"] == "gemini":
        # Run CPU bound task in thread
        return await asyncio.to_thread(get_gemini_embedding, text=text)
    return None


async def add_chat_to_memory(speaker: str, text: str):
    vector = await get_embedding(text=text)
    if vector:
        try:
            doc_id = datetime.datetime.now().isoformat()
            # ChromaDB I/O in thread
            await asyncio.to_thread(
                chat_collection.add,
                ids=[doc_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[
                    {"speaker": speaker, "text_content": text, "timestamp": doc_id}
                ],
            )
            print(f"MCP MEMORY: Added chat from '{speaker}' to ChromaDB.")
        except Exception as e:
            print(f"MCP ERROR: Failed to add chat to ChromaDB: {e}")


async def add_image_to_memory(image_identifier: str, image_base64: str):
    vector = await get_embedding(image_base64=image_base64)
    if vector:
        try:
            await asyncio.to_thread(
                image_collection.add,
                ids=[image_identifier],
                embeddings=[vector],
                metadatas=[{"timestamp": image_identifier}],
            )
            print(f"MCP MEMORY: Added image '{image_identifier}' to ChromaDB.")
        except Exception as e:
            print(f"MCP ERROR: Failed to add image to ChromaDB: {e}")


async def ask_llm(user_content: str, image_data_base64: str = None) -> tuple[str, dict]:
    print(f"MCP INFO: Sending prompt to {config['llm_choice'].upper()}...")
    print(f"MCP DEBUG: llm_choice value = '{config['llm_choice']}' (type: {type(config['llm_choice']).__name__})")
    print(f"MCP DEBUG: Checking against: lm_studio, ollama, ollama_vision, ollama_cloud, gemini")
    perf_data = {"tps": 0.0}
    try:
        response_json = None
        system_prompt = config.get("system_prompt", "")

        if config["llm_choice"] == "lm_studio":
            # LM Studio / OpenAI Compatible API
            url = f"{config['lm_studio_base_url']}/chat/completions"
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            # Note: LM Studio usually ignores the model name parameter and uses what is loaded in the GUI
            payload = {
                "model": "local-model",
                "messages": messages,
                "temperature": 0.7,
                "stream": False,
            }
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()

            # Extract content from OpenAI format
            content = response_json["choices"][0]["message"]["content"].strip()

            # LM Studio sometimes provides usage stats, but not always tps directly in the header
            # We will just return the content
            return content, perf_data

        elif config["llm_choice"] in ["ollama_vision", "ollama", "ollama_cloud"]:
            if config["llm_choice"] == "ollama_cloud":
                model = config["ollama_cloud_model"]
                base = config["ollama_cloud_base_url"].rstrip("/")
                # Remove /api/chat if already in base URL
                if base.endswith("/api/chat"):
                    base = base[:-9]
                url = f"{base}/api/chat"
            else:
                model = (
                    config["ollama_vision_model"]
                    if config["llm_choice"] == "ollama_vision"
                    else config["ollama_model"]
                )
                url = config["ollama_api_url"]
            user_message = {"role": "user", "content": user_content}
            if image_data_base64:
                user_message["images"] = [image_data_base64]
            messages = [{"role": "system", "content": system_prompt}, user_message]
            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "keep_alive": -1,
            }
            headers = None
            if config["llm_choice"] == "ollama_cloud" and config.get(
                "ollama_cloud_api_key"
            ):
                headers = {"Authorization": f"Bearer {config['ollama_cloud_api_key']}"}

            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            response_json = response.json()

        elif config["llm_choice"] == "gemini":
            final_gemini_prompt = f"{system_prompt}\n\n---\n\n{user_content}"
            # ASYNC Call for Gemini
            gemini_response = await gemini_model.generate_content_async(
                final_gemini_prompt
            )
            return gemini_response.text.strip(), perf_data
        
        else:
            print(f"MCP ERROR: Unknown LLM choice: '{config['llm_choice']}'")
            print(f"MCP ERROR: Valid options are: lm_studio, ollama, ollama_vision, ollama_cloud, gemini")

        if response_json:
            if "eval_count" in response_json and "eval_duration" in response_json:
                eval_count = response_json["eval_count"]
                eval_duration_ns = response_json["eval_duration"]
                if eval_duration_ns > 0:
                    eval_duration_s = eval_duration_ns / 1_000_000_000
                    tokens_per_second = eval_count / eval_duration_s
                    perf_data["tps"] = tokens_per_second
                    print(f"MCP PERF: {tokens_per_second:.2f} T/s")
            return response_json.get("message", {}).get(
                "content", ""
            ).strip(), perf_data

        return "Error: LLM choice not recognized.", perf_data
    except Exception as e:
        print(f"MCP ERROR: ask_llm failed: {e}")
        return "Sorry, I encountered an error while trying to think.", perf_data


async def retrieve_from_rag(user_query: str) -> str:
    print(f"MCP INFO: RAG retrieval for: '{user_query}'")
    vector = await get_embedding(text=user_query)
    if not vector:
        return ""
    context_str = "CONTEXT FROM LONG-TERM MEMORY:\n"
    found_context = False
    try:
        # ChromaDB Query in Thread
        chat_results = await asyncio.to_thread(
            chat_collection.query, query_embeddings=[vector], n_results=3
        )
        if chat_results and chat_results["ids"][0]:
            context_str += "[Relevant Chat History]\n"
            for data in chat_results["metadatas"][0]:
                context_str += f'- {data["speaker"]} said: "{data["text_content"]}"\n'
            found_context = True

        image_results = await asyncio.to_thread(
            image_collection.query, query_embeddings=[vector], n_results=1
        )
        if image_results and image_results["ids"][0]:
            context_str += "\n[Relevant Image]\n"
            context_str += f"- An image was found: '{image_results['ids'][0][0]}'\n"
            found_context = True
    except Exception as e:
        print(f"MCP ERROR: RAG search failed: {e}")
        return ""
    return context_str if found_context else ""


async def get_time_for_location(location_name: str) -> str:
    if not location_name:
        return "No location specified."
    
    # Hardcoded coordinates for common cities (geocoding disabled due to SSL)
    hardcoded_locations = {
        "tokyo": (35.6762, 139.6503),
        "pattaya": (12.9236, 100.8825),
        "bangkok": (13.7563, 100.5018),
        "london": (51.5074, -0.1278),
        "new york": (40.7128, -74.0060),
        "los angeles": (34.0522, -118.2437),
        "paris": (48.8566, 2.3522),
        "berlin": (52.5200, 13.4050),
    }
    
    lat_lon = None
    for city, coords in hardcoded_locations.items():
        if city in location_name.lower():
            lat_lon = coords
            break
    
    if lat_lon:
        lat, lon = lat_lon
        try:
            timezone_name = tf.timezone_at(lng=lon, lat=lat)
            if timezone_name:
                import datetime, pytz
                target_tz = pytz.timezone(timezone_name)
                target_time = datetime.datetime.now(target_tz)
                formatted_time = target_time.strftime("%I:%M %p on %A")
                return f"The time in {location_name.title()} is {formatted_time}."
        except Exception as e:
            pass
    
    # Fallback for unknown locations
    if geolocator is None or tf is None:
        print("MCP ERROR: Geolocator or timezone finder not initialized. Check startup logs.")
        return "My location system isn't working. Check the server logs."
    try:
        # Geopy in thread
        location = await asyncio.to_thread(geolocator.geocode, location_name)
        if not location:
            return f"I couldn't find '{location_name}'."
        timezone_name = await asyncio.to_thread(
            tf.timezone_at, lng=location.longitude, lat=location.latitude
        )
        if not timezone_name:
            return f"Could not find timezone for '{location_name}'."
        target_tz = pytz.timezone(timezone_name)
        target_time = datetime.datetime.now(target_tz)
        formatted_time = target_time.strftime("%I:%M %p on %A")
        city_name = location.address.split(',')[0]
        return f"The time in {city_name} is {formatted_time}."
    except Exception as e:
        print(f"MCP ERROR: Time lookup failed: {e}")
        traceback.print_exc()
        return "I had trouble looking up the time."


def send_over_osc(command_text: str):
    # OSC is fast UDP, safe to be synchronous usually, but can wrap if needed.
    # Keeping sync for simplicity as udp_client is non-blocking mostly.
    if not config["osc_enabled"] or not osc_client:
        return
    try:
        builder = osc_message_builder.OscMessageBuilder(address=config["osc_address"])
        builder.add_arg(command_text, builder.ARG_TYPE_STRING)
        builder.add_arg(True, builder.ARG_TYPE_TRUE)
        osc_client.send(builder.build())
        print(f"MCP INFO: Sent OSC -> '{command_text}'")
    except Exception as e:
        print(f"MCP ERROR: OSC failed: {e}")


async def get_image_from_vision_service() -> str:
    url = config.get("vision_service_get_image_url")
    if not url:
        return None
    print(f"MCP CORE: Requesting image from: {url}...")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response.json().get("image_base64")
    except Exception as e:
        print(f"MCP ERROR: Image fetch failed: {e}")
        return None


async def get_fresh_vision_context() -> str:
    url = config.get("vision_service_scan_url")
    if not url:
        return "Error: Vision URL not configured."
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        response.raise_for_status()
        return response.json().get("vision_context", "Error: Invalid response.")
    except Exception as e:
        return f"Error: Vision service unreachable: {e}"


async def send_to_social_stream(text_to_send: str):
    if not config.get("social_stream_enabled", False) or not text_to_send:
        return

    # --- CLEAN THE TEXT ---
    clean_text = re.sub(r"\(.*?\)", "", text_to_send)
    clean_text = re.sub(r"\*.*?\*", "", clean_text)
    clean_text = clean_text.strip()

    if not clean_text:
        return

    targets = config.get("social_stream_targets", [])
    api_url = config.get("social_stream_api_url", "").rstrip(
        "/"
    )  # Strips trailing slash to prevent double slash //
    session_id = config.get("social_stream_session_id")

    print(f"MCP DEBUG: Text sent to Social Stream Ninja: '{clean_text}'")

    # --- 1. HTTP POST METHOD ---
    async def http_post(target):
        url = f"{api_url}/{session_id}"  # Will safely become https://io.socialstream.ninja/SESSION_ID
        payload = {"action": "sendChat", "value": clean_text, "target": target}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, json=payload)
                # Print response.text for better debugging as requested by dev
                print(
                    f"  -> Social (HTTP) sent to '{target}'. Server replied: {response.text}"
                )
        except Exception as e:
            print(f"  -> Social (HTTP) failed '{target}': {e}")

    # --- 2. WEBSOCKET (WSS) METHOD ---
    async def ws_post():
        ws_url = "wss://io.socialstream.ninja:443"

        join_payload = {"join": session_id, "out": 1, "in": 2}
        chat_payload = {
            "action": "sendChat",
            "apiid": session_id,
            "value": clean_text,
            # Intentionally omitting target to guarantee global broadcast across Discord/YT/Twitch
        }

        try:
            async with websockets.connect(ws_url) as ws:
                await ws.send(json.dumps(join_payload))
                await asyncio.sleep(0.1)  # Brief pause to allow room join
                await ws.send(json.dumps(chat_payload))
                await asyncio.sleep(0.5)  # Allow message to flush before disconnecting
                print(f"  -> Social (WS) broadcast sent successfully")
        except Exception as e:
            print(f"  -> Social (WS) failed: {e}")

    print(f"MCP INFO: Broadcasting to Social Stream: {targets}")

    # Fire off HTTP targets and WS Broadcast simultaneously
    http_tasks = [http_post(t) for t in targets]
    await asyncio.gather(*http_tasks, ws_post())

    print("MCP INFO: Social broadcast done.")


def format_opencode_response(text: str) -> str:
    """Format OpenCode response for better readability in chat"""
    if not text:
        return text
    
    # Remove the OpenCode: prefix and quotes if present
    formatted = text.strip()
    if formatted.startswith('OpenCode:'):
        formatted = formatted[9:].strip()
    formatted = formatted.strip('"')
    
    # Fix word splitting (remove newlines between words)
    # Replace newlines that aren't paragraph breaks with spaces
    lines = formatted.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line:
            cleaned_lines.append(line)
    
    # Join with single spaces, preserve intentional paragraph breaks
    formatted = ' '.join(cleaned_lines)
    
    # Fix spacing around punctuation
    formatted = formatted.replace('  ', ' ')
    formatted = formatted.replace('. ', '.')
    formatted = formatted.replace('.  ', '. ')
    formatted = formatted.replace('? ', '?')
    formatted = formatted.replace('! ', '!')
    
    # Capitalize first letter
    if formatted:
        formatted = formatted[0].upper() + formatted[1:]
    
    # Format YouTube video info if detected
    if "latest video" in formatted.lower() or "video is" in formatted.lower():
        # Try to make it more conversational
        parts = formatted.split("-")
        if len(parts) > 1:
            formatted = "📹 " + parts[0].strip()
            for part in parts[1:]:
                formatted += f"\n   • {part.strip()}"
    
    return formatted

async def send_to_tts(text_to_speak: str):
    # Check if either TTS is enabled
    styletts_enabled = config.get("styletts_enabled", False)
    pockettts_enabled = config.get("pockettts_enabled", False)
    
    if not (styletts_enabled or pockettts_enabled) or not text_to_speak:
        return
    
    # Determine which TTS to use (Pocket TTS has priority if both enabled)
    if pockettts_enabled:
        url = config.get("pockettts_url", "http://127.0.0.1:13301/tts")
        tts_name = "Pocket TTS"
    else:
        url = config.get("styletts_url")
        tts_name = "StyleTTS"
    
    clean_text = re.sub(r"[^a-zA-Z0-9\s.,?!'\"():-]", "", text_to_speak)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    if not clean_text:
        return
    
    # Pocket TTS uses ?text= query param, StyleTTS uses POST json
    if pockettts_enabled:
        tts_url = f"{url}?text={clean_text}"
        print(f"MCP INFO: Sending to {tts_name} -> '{clean_text}'")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.get(tts_url)
        except Exception as e:
            print(f"MCP ERROR: {tts_name} failed: {e}")
    else:
        payload = {"chatmessage": clean_text}
        print(f"MCP INFO: Sending to {tts_name} -> '{clean_text}'")
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                await client.post(url, json=payload)
        except Exception as e:
            print(f"MCP ERROR: {tts_name} failed: {e}")


# Helper: Youtube check (Blocking, used in logic)
def check_song_exists_in_requests(query: str) -> str:
    """Check if a similar song already exists in requests folder. Returns filename if found, empty string if not."""
    if not os.path.exists("requests"):
        return ""
    
    query_clean = query.lower().strip()
    # Remove common YouTube suffixes for matching
    for suffix in [" official video", " official audio", " lyrics", " hd", " 4k"]:
        query_clean = query_clean.replace(suffix, "")
    
    # Extract key parts (artist - title format)
    if " - " in query_clean:
        parts = query_clean.split(" - ")
        artist = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else ""
    else:
        artist = ""
        title = query_clean
    
    # Search for matching files
    for filename in os.listdir("requests"):
        if filename.endswith(".mp3"):
            filename_clean = filename.lower().replace(".mp3", "")
            # Remove YouTube ID suffix like [stqBS3m-3WE]
            import re
            filename_clean = re.sub(r'\s*\[[a-zA-Z0-9_-]+\]\s*$', '', filename_clean)
            
            # Check if both artist and title match (fuzzy)
            artist_match = artist in filename_clean or filename_clean in artist if artist else False
            title_match = title in filename_clean or filename_clean in title if title else False
            
            # Or check if the whole query matches
            full_match = query_clean in filename_clean or filename_clean in query_clean
            
            if (artist_match and title_match) or full_match:
                print(f"MCP DOWNLOAD: Found existing file: {filename}")
                return filename
    
    return ""


def get_song_info_and_check_duration(query: str) -> dict:
    print(f"MCP DOWNLOAD: Verifying song: '{query}'")
    MAX_SEC = config.get("max_download_duration_seconds", 600)
    
    import re
    
    # Try direct YouTube search with yt-dlp first (more reliable)
    print(f"MCP DOWNLOAD: Trying yt-dlp search...")
    try:
        # Use web client with cookies - works better for authenticated users
        search_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "default_search": "ytsearch5",
            "cookiefile": os.path.abspath(os.path.join(os.path.dirname(__file__), "cookies.txt")),
        }
        with yt_dlp.YoutubeDL(search_opts) as ydl:
            search_query = f"ytsearch5:{query}"
            info = ydl.extract_info(search_query, download=False)
            if info and info.get("entries"):
                entries = list(info["entries"])
                print(f"MCP DOWNLOAD: Found {len(entries)} results via yt-dlp")
                for idx, entry in enumerate(entries):
                    if not entry:
                        continue
                    video_id = entry.get("id", "")
                    title = entry.get("title", "")
                    duration = entry.get("duration", 0)
                    
                    if not video_id or not title:
                        continue
                    
                    # Skip if too long or too short
                    if duration and (duration > MAX_SEC or duration < 30):
                        print(f"MCP DOWNLOAD: Skipping '{title[:50]}...' - duration {duration}s")
                        continue
                    
                    # Test download with web client
                    test_opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "cookiefile": os.path.abspath(os.path.join(os.path.dirname(__file__), "cookies.txt")),
                    }
                    try:
                        with yt_dlp.YoutubeDL(test_opts) as test_ydl:
                            test_info = test_ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                            if test_info and test_info.get("formats"):
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                print(f"MCP DOWNLOAD: FOUND via yt-dlp - '{title}' ({duration or 'unknown'}s)")
                                return {
                                    "status": "ok",
                                    "url": video_url,
                                    "title": title,
                                }
                    except Exception as test_err:
                        print(f"MCP DOWNLOAD: Video {idx+1} test failed: {str(test_err)[:80]}")
                        continue
    except Exception as e:
        print(f"MCP DOWNLOAD: yt-dlp search error: {e}")
    
    # Fallback to YTMusic
    print(f"MCP DOWNLOAD: Trying YTMusic search...")
    clean_query = re.sub(r'[^\w\s-]', '', query.lower())
    
    # Extract key terms
    key_terms = query.lower()
    for remove_word in ["official", "video", "audio", "lyrics", "music", "hd", "4k", "extended", "mix", "version", "feat", "ft", "."]:
        key_terms = key_terms.replace(remove_word, "")
    key_terms = ' '.join(key_terms.split())
    
    search_variations = [query, key_terms, f"{key_terms} official"]
    seen = set()
    
    for search_q in search_variations:
        if search_q in seen or not search_q:
            continue
        seen.add(search_q)
        
        try:
            print(f"MCP DOWNLOAD: YTMusic search: '{search_q}'")
            yt = ytmusicapi.YTMusic()
            search_results = yt.search(search_q, filter="songs")
            if not search_results:
                search_results = yt.search(search_q, filter="videos")
            
            if search_results:
                for i, result in enumerate(search_results[:10]):
                    video_id = result.get("videoId")
                    if not video_id:
                        continue
                    title = result.get("title", "")
                    artist = ""
                    artists_list = result.get("artists", [])
                    if artists_list:
                        artist = artists_list[0].get("name", "")
                    duration_str = result.get("duration", "0")
                    
                    duration = 0
                    if duration_str and ":" in str(duration_str):
                        parts = str(duration_str).split(":")
                        duration = int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else 0
                    
                    if duration and (duration > MAX_SEC or duration < 30):
                        continue
                    
                    test_opts = {
                        "quiet": True,
                        "no_warnings": True,
                        "noplaylist": True,
                        "cookiefile": os.path.abspath(os.path.join(os.path.dirname(__file__), "cookies.txt")),
                    }
                    try:
                        with yt_dlp.YoutubeDL(test_opts) as ydl:
                            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                            if info and info.get("formats"):
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                print(f"MCP DOWNLOAD: FOUND via YTMusic - '{title}'")
                                return {
                                    "status": "ok",
                                    "url": video_url,
                                    "title": f"{title} - {artist}".strip(" -") if artist else title,
                                }
                    except Exception as test_err:
                        if "age" in str(test_err).lower():
                            print(f"MCP DOWNLOAD: Video {i+1} age-restricted")
                        continue
        except Exception as e:
            print(f"MCP DOWNLOAD: YTMusic error: {e}")
            continue
    
    if "youtube.com" in query or "youtu.be" in query:
        return {"status": "ok", "url": query, "title": "YouTube Video"}
    
    print(f"MCP DOWNLOAD: FAILED - No results for '{query}'")
    return {"status": "error", "message": "No results found."}


# ------------------------------------------------------------------------------


# --- Music Downloader Helper Functions ---
# ------------------------------------------------------------------------------
def handle_song_download_task(video_url: str):
    print(f"MCP DOWNLOAD: Worker starting for: '{video_url}'")
    try:
        output_folder = "requests"
        os.makedirs(output_folder, exist_ok=True)
        yt_dlp_cmd = "yt-dlp.exe" if platform.system() == "Windows" else "yt-dlp"
        
        # Check for cookies.txt or use browser cookies
        cookies_arg = []
        cookies_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "cookies.txt"))
        if os.path.exists(cookies_file):
            cookies_arg = ["--cookies", cookies_file]
            print(f"MCP DOWNLOAD: Using cookies: {cookies_file}")
        else:
            # Try to use cookies directly from browser
            cookies_arg = ["--cookies-from-browser", "chrome"]
            print(f"MCP DOWNLOAD: Using Chrome browser cookies (no cookies.txt found)")
        
        # Use web client with cookies and custom output template (no video ID)
        cmd = [
            yt_dlp_cmd,
            "-x",
            "--audio-format",
            "mp3",
            "-P",
            output_folder,
            "-o", "%(title)s.%(ext)s",
            "--no-playlist",
            "--prefer-free-formats",
        ] + cookies_arg + [video_url]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        download_success = False
        downloaded_filename = None
        for line in iter(process.stdout.readline, ""):
            print(f"YT-DLP: {line.strip()}")
            if "Destination" in line or "Merging formats" in line or "Extracting audio" in line:
                download_success = True
        process.wait()
        
        if process.returncode == 0 and download_success:
            # Find the most recently created MP3 file
            import glob
            import time
            mp3_files = glob.glob(os.path.join(output_folder, "*.mp3"))
            if mp3_files:
                mp3_files_sorted = sorted(mp3_files, key=os.path.getctime, reverse=True)
                # Only use files created in the last 2 minutes
                now = time.time()
                for f in mp3_files_sorted:
                    if now - os.path.getctime(f) < 120:  # 2 minutes
                        downloaded_filename = os.path.basename(f)
                        print(f"MCP DOWNLOAD: Success -> '{downloaded_filename}'")
                        break
            
            if downloaded_filename:
                with open("autoplay.txt", "w", encoding="utf-8") as f:
                    f.write(downloaded_filename)
                print(f"MCP DOWNLOAD: Complete -> '{downloaded_filename}'")
            else:
                print("MCP DOWNLOAD ERROR: Download succeeded but no new file found!")
        else:
            print(f"MCP DOWNLOAD ERROR: Download failed (returncode={process.returncode})")
    except Exception as e:
        print(f"MCP DOWNLOAD ERROR: {e}")
        traceback.print_exc()


def _process_download_queue():
    while True:
        url = download_queue.get()
        handle_song_download_task(url)
        download_queue.task_done()
        save_download_queue(download_queue)


def save_download_queue(q):
    """Save download queue to file for persistence"""
    DOWNLOAD_QUEUE_FILE = "download_queue.txt"
    try:
        with open(DOWNLOAD_QUEUE_FILE, 'w', encoding='utf-8') as f:
            temp_list = []
            while not q.empty():
                url = q.get()
                f.write(url + '\n')
                temp_list.append(url)
            for url in temp_list:
                q.put(url)
    except Exception as e:
        print(f"MCP DOWNLOAD ERROR: Could not save queue: {e}")


def load_download_queue():
    """Load persistent download queue from file"""
    DOWNLOAD_QUEUE_FILE = "download_queue.txt"
    q = queue.Queue()
    if os.path.exists(DOWNLOAD_QUEUE_FILE):
        try:
            with open(DOWNLOAD_QUEUE_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if url:
                        q.put(url)
            print(f"MCP DOWNLOAD: Loaded {q.qsize()} items from persistent queue")
        except Exception as e:
            print(f"MCP DOWNLOAD ERROR: Could not load queue: {e}")
    return q


# ------------------------------------------------------------------------------



# --- VMagicMirror Motion Control ---
# ------------------------------------------------------------------------------
VMAGIC_MOTIONS = {
    'wave': '1',
    'dance': '2',
    'bow': '3',
    'jump': '4',
    'spin': '5',
    'clap': '6',
    'laugh': '7',
    'cry': '8',
    'sleep': '9',
}

def send_vmagic_motion(motion_name):
    """Send Ctrl+Alt+{key} to trigger VMagicMirror motion"""
    motion_name = motion_name.lower()
    if motion_name not in VMAGIC_MOTIONS:
        print(f"MCP VMAGIC: Unknown motion '{motion_name}'")
        return False
    
    key = VMAGIC_MOTIONS[motion_name]
    print(f"MCP VMAGIC: Sending Ctrl+Alt+{key} for '{motion_name}'")
    
    try:
        keyboard.press('ctrl')
        keyboard.press('alt')
        keyboard.press(key)
        import time
        time.sleep(0.05)
        keyboard.release(key)
        keyboard.release('alt')
        keyboard.release('ctrl')
        print(f"MCP VMAGIC: Sent!")
        return True
    except Exception as e:
        print(f"MCP VMAGIC ERROR: {e}")
        return False


# --- Music Recognition Helper Functions ---
# ------------------------------------------------------------------------------
def record_audio_for_music(filename):
    if not MUSIC_RECOGNITION_ENABLED:
        return None
    s = MUSIC_RECOGNITION_SETTINGS
    print(f"MCP MUSIC: Recording {s['audio_duration']}s...")
    try:
        # Blocking record
        rec = sd.rec(
            int(s["audio_duration"] * s["sample_rate"]),
            samplerate=s["sample_rate"],
            channels=s["channels"],
            dtype="int16",
            device=SELECTED_INPUT_DEVICE_INDEX,
        )
        sd.wait()
        sf.write(filename, rec, s["sample_rate"])
        return filename
    except Exception as e:
        print(f"Music Record Error: {e}")
        return None


async def recognize_song_via_api(audio_file_path):
    # Converted to Async
    if not os.path.exists(audio_file_path):
        return {"status": "error"}
    s = MUSIC_RECOGNITION_SETTINGS
    headers = {
        "X-RapidAPI-Key": s["rapidapi_key"],
        "X-RapidAPI-Host": s["rapidapi_host"],
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(audio_file_path, "rb") as f:
                response = await client.post(
                    s["recognition_endpoint_url"],
                    headers=headers,
                    files={"upload_file": f},
                )
        response.raise_for_status()
        res = response.json()
        if res.get("track"):
            t = res["track"]
            return {
                "status": "success",
                "title": t.get("title"),
                "artist": t.get("subtitle"),
            }
        return {"status": "error", "message": "Not recognized."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def clean_up_audio_file(filepath):
    if os.path.exists(filepath):
        try:
            os.remove(filepath)
        except:
            pass


async def handle_music_recognition_task_async():
    # Wrapper to run blocking record in thread, then async upload
    temp_file = MUSIC_RECOGNITION_SETTINGS["temp_audio_filename"]
    # Record (blocking) in thread
    rec_file = await asyncio.to_thread(record_audio_for_music, temp_file)
    if not rec_file:
        return
    # Upload (async)
    info = await recognize_song_via_api(rec_file)
    clean_up_audio_file(rec_file)

    resp_text = (
        f"I think the song is '{info['title']}' by {info['artist']}."
        if info["status"] == "success"
        else "Sorry, I couldn't identify the song."
    )
    await asyncio.gather(
        send_to_tts(resp_text),
        send_to_social_stream(resp_text),
        log_assistant_response(resp_text, source_name="MusicRec"),  # COMPLETE RELAY
        add_chat_to_memory("System", resp_text),
    )


# ------------------------------------------------------------------------------


# --- 4. UNIVERSAL PROCESSING FUNCTION (ASYNC) ---
# ------------------------------------------------------------------------------
async def process_task(source: str, user_text: str, vision_context: str = "") -> str:
    global VISION_HISTORY, CURRENT_LOCATION

    wake_word_detected, clean_user_text = False, ""
    for word in config["wake_words"]:
        if not word:
            continue
        pattern = re.compile(
            r"^(ok |so |well |hey |okay, |so, |well, |hey, )?"
            + re.escape(word)
            + r"\b",
            re.IGNORECASE,
        )
        match = pattern.search(user_text)
        if match:
            wake_word_detected, start_of_clean_text = True, match.end()
            clean_user_text = user_text[start_of_clean_text:].strip()
            if clean_user_text and clean_user_text[0] in [",", ".", ":", ";"]:
                clean_user_text = clean_user_text[1:].strip()
            break
    if not wake_word_detected:
        print(f"MCP: No wake word in '{user_text}'")
        return ""

    print(f"MCP: Wake word confirmed! Processing: '{clean_user_text}'")

    # Check for VMagicMirror motion commands (silent - no TTS)
    for motion in VMAGIC_MOTIONS.keys():
        if motion in clean_user_text.lower():
            send_vmagic_motion(motion)
            # Return empty string to skip TTS and Social Stream
            return ""
    
    await add_chat_to_memory("User", clean_user_text)

    # Music Recognition Trigger
    if MUSIC_RECOGNITION_ENABLED and any(
        k in clean_user_text.lower() for k in config["music_trigger_words"]
    ):
        print(f"MCP MUSIC: Triggered.")
        # Fire and forget async background task
        asyncio.create_task(handle_music_recognition_task_async())
        return "Listening..."

    is_download = any(
        t in clean_user_text.lower() for t in config.get("download_trigger_words", [])
    )
    # Check if this is a Twitch music request
    is_twitch_request = config.get("twitch_enabled", False) and any(
        t in clean_user_text.lower() for t in config.get("download_trigger_words", [])
    )
    is_time = any(
        k in clean_user_text.lower()
        for k in ["time is it", "what time", "current time"]
    )
    is_rag = any(
        clean_user_text.lower().startswith(t) for t in config["rag_trigger_words"]
    )
    is_osc = config["osc_enabled"] and any(
        clean_user_text.lower().startswith(v) for v in config["osc_trigger_verbs"]
    )
    is_vision = any(
        t in clean_user_text.lower() for t in config["vision_trigger_words"]
    )
    # More natural OpenCode triggers
    opencode_triggers = ["oc ", "use oc ", "try oc ", "ask oc ", "open code ", "opencode "]
    is_opencode = OPENCODE_ENABLED and any(clean_user_text.lower().startswith(trigger) for trigger in opencode_triggers)
    # Check for pause and play commands
    is_pause_play = any(
        phrase in clean_user_text.lower() 
        for phrase in ["pause the music and play", "pause and play", "pause the song and play"]
    )
    # Check for resume commands
    is_resume = any(
        phrase in clean_user_text.lower()
        for phrase in ["resume the music", "continue the song", "resume playing", "resume"]
    ) and not is_download  # Don't trigger on "resume downloading"

    if is_download and not config.get("music_downloader_enabled", False):
        resp = "Music request system is off."
        await add_chat_to_memory("Gem", resp)
        return resp

    final_response = ""

    # Handle Twitch music requests with verification
    if is_twitch_request and config.get("twitch_enabled", False):
        trigger = next(
            (
                t
                for t in config["download_trigger_words"]
                if t in clean_user_text.lower()
            ),
            "",
        )
        query = clean_user_text.replace(trigger, "", 1).strip()
        if not query:
            final_response = "What song should I play?"
        else:
            print(f"MCP TWITCH: Verifying '{query}' against Twitch DJ catalog...")
            result = TWITCH_MUSIC_CHECKER.verify_request(query)
            if result['status'] == 'allowed':
                # Check if song already exists
                existing_file = check_song_exists_in_requests(f"{result['artist']} - {result['track']}")
                if existing_file:
                    # Song exists, add directly to autoplay
                    with open("autoplay.txt", "w", encoding="utf-8") as f:
                        f.write(existing_file)
                    final_response = f"✅ Already have '{existing_file}' - playing now!"
                    print(f"MCP TWITCH: Using existing file: {existing_file}")
                else:
                    info = await asyncio.to_thread(get_song_info_and_check_duration, f"{result['artist']} - {result['track']}")
                    if info["status"] == "ok":
                        download_queue.put(info["url"])
                        save_download_queue(download_queue)
                        total = download_queue.qsize()
                        final_response = f"✅ Twitch approved! Added '{info['title']}' to queue. ({total} in queue)"
                    else:
                        final_response = info["message"]
            else:
                final_response = f"❌ {result['message']}"

    elif is_download:
        trigger = next(
            (
                t
                for t in config["download_trigger_words"]
                if t in clean_user_text.lower()
            ),
            "",
        )
        query = clean_user_text.lower().replace(trigger, "", 1).strip()
        if not query:
            final_response = "What song should I download?"
        else:
            # Check if song already exists
            existing_file = check_song_exists_in_requests(query)
            if existing_file:
                # Song exists, add directly to autoplay
                with open("autoplay.txt", "w", encoding="utf-8") as f:
                    f.write(existing_file)
                final_response = f"Already have '{existing_file}' - playing now!"
                print(f"MCP DOWNLOAD: Using existing file: {existing_file}")
            else:
                # yt-dlp check in thread
                info = await asyncio.to_thread(get_song_info_and_check_duration, query)
                if info["status"] == "ok":
                    download_queue.put(info["url"])
                    save_download_queue(download_queue)
                    total = download_queue.qsize()
                    final_response = f"Added '{info['title']}' to queue. ({total} in queue)"
                else:
                    final_response = info["message"]

    elif is_osc:
        verb = next(
            (
                v
                for v in config["osc_trigger_verbs"]
                if clean_user_text.lower().startswith(v)
            ),
            "",
        )
        dest = clean_user_text[len(verb) :].strip()
        if not dest:
            final_response = "Where to?"
        elif dest.lower() == CURRENT_LOCATION.lower():
            final_response = f"I'm at {dest}."
        else:
            send_over_osc(clean_user_text)
            CURRENT_LOCATION = dest
            final_response = f"Going to {dest}."

    elif is_time:
        loc, _ = await ask_llm(
            f"Extract city from: {clean_user_text}. Only location name."
        )
        print(f"MCP TIME: LLM extracted location: '{loc}' (length: {len(loc) if loc else 0})")
        # Use extracted location if it's reasonable (< 25 chars and not empty)
        location_to_use = loc.strip() if loc and len(loc) < 25 else "Pattaya"
        print(f"MCP TIME: Using location: '{location_to_use}'")
        time_ctx = await get_time_for_location(location_to_use)
        print(f"MCP TIME: Time context result: '{time_ctx}'")
        # Force LLM to use the actual time, not make up its own answer
        final_response, _ = await ask_llm(
            f"{time_ctx} User asks: '{clean_user_text}'. Give ONLY the actual time shown above, be concise."
        )

    elif is_pause_play:
        # Extract song name from command
        song_name = clean_user_text.lower()
        for phrase in ["pause the music and play", "pause and play", "pause the song and play"]:
            if phrase in song_name:
                song_name = song_name.split(phrase)[-1].strip()
                break
        # Remove common prefixes
        for prefix in ["the ", "a "]:
            if song_name.startswith(prefix):
                song_name = song_name[len(prefix):]
        song_name = song_name.strip().strip('"\'')
        
        if song_name:
            # Write song name to pause_play_signal.txt
            with open("pause_play_signal.txt", "w", encoding="utf-8") as f:
                f.write(song_name)
            final_response = f"⏸️ Pausing to play: {song_name}"
            print(f"MCP PAUSE: Created pause_play_signal.txt for '{song_name}'")
        else:
            final_response = "Which song should I play?"

    elif is_resume:
        # Write resume signal
        with open("resume_signal.txt", "w", encoding="utf-8") as f:
            f.write("resume")
        final_response = "▶️ Resuming previous song..."
        print("MCP RESUME: Created resume_signal.txt")

    elif is_vision:
        if config["llm_choice"] == "ollama_vision":
            img = await get_image_from_vision_service()
            if img:
                resp, _ = await ask_llm(
                    f"Describe image. User: {clean_user_text}", image_data_base64=img
                )
                final_response = resp
                await add_image_to_memory(
                    f"img_{datetime.datetime.now().timestamp()}", img
                )
            else:
                final_response = "Can't see image."
        else:
            final_response = await get_fresh_vision_context()
            VISION_HISTORY.appendleft(final_response)

    elif is_opencode:
        # Extract command after trigger phrase
        oc_command = clean_user_text.lower()
        for trigger in opencode_triggers:
            if oc_command.startswith(trigger):
                oc_command = oc_command[len(trigger):].strip()
                break
        
        if not oc_command:
            final_response = "What should I ask OpenCode to do?"
        else:
            print(f"MCP OPENCODE: Sending command: '{oc_command}'")
            try:
                oc_result = await OPENCODE_CLIENT.execute_task(oc_command)
                # Format the response for better readability
                formatted_result = format_opencode_response(oc_result)
                final_response = formatted_result
                print(f"MCP OPENCODE: Result: {oc_result[:200]}...")
                await asyncio.gather(
                    log_assistant_response(final_response, source_name="OpenCode"),
                    add_chat_to_memory("Gem", final_response),
                    send_to_social_stream(final_response)
                )
                return ""
            except Exception as e:
                final_response = f"OpenCode error: {str(e)}"

    else:
        rag = await retrieve_from_rag(clean_user_text) if is_rag else ""
        hist = "\n".join(VISION_HISTORY) if VISION_HISTORY else ""
        prompt = f"{rag}Loc: {CURRENT_LOCATION}\n{hist}\nUser: {clean_user_text}"
        final_response, _ = await ask_llm(prompt)

    await add_chat_to_memory("Gem", final_response)
    return final_response


# ------------------------------------------------------------------------------


# --- 5. API ENDPOINTS (QUART) ---
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
async def index():
    return "Hello from UNIFIED ASYNC MCP!"


@app.route("/update_runtime_setting", methods=["POST"])
async def update_runtime_setting():
    data = await request.get_json()
    key, value = data.get("key"), data.get("value")
    if not key:
        return jsonify({"status": "error"}), 400

    actual_val = value
    if isinstance(value, str):
        actual_val = value.lower() == "true"

    if key in config:
        config[key] = actual_val
        return jsonify({"status": "ok"})
    return jsonify({"status": "error"}), 404


@app.route("/add_to_download_queue", methods=["POST"])
async def handle_add_to_download_queue():
    data = await request.get_json()
    query = data.get("query", "")
    
    if not query:
        return jsonify({"status": "error", "message": "No query provided"}), 400
    
    print(f"MCP: Direct download request for '{query}'")
    
    info = await asyncio.to_thread(get_song_info_and_check_duration, query)
    if info["status"] == "ok":
        download_queue.put(info["url"])
        save_download_queue(download_queue)
        total = download_queue.qsize()
        return jsonify({
            "status": "ok",
            "title": info["title"],
            "queue_size": total
        })
    else:
        return jsonify({"status": "error", "message": info["message"]}), 400


@app.route("/chat", methods=["POST", "PUT"])
async def handle_chat_request():
    data = await request.get_json()
    chat_message = data.get("chatmessage", "") or data.get("message", "")

    # Filter out AI-generated messages to prevent loops
    if chat_message.startswith("Added ") and " to queue" in chat_message:
        print(f"MCP: Ignoring AI queue message: '{chat_message}'")
        return jsonify({"status": "ok"})
    if chat_message.startswith("✅ Twitch approved!") or chat_message.startswith("✅ Already have"):
        print(f"MCP: Ignoring AI Twitch message: '{chat_message}'")
        return jsonify({"status": "ok"})
    if chat_message.startswith("Already have ") and " playing now" in chat_message:
        print(f"MCP: Ignoring AI playback message: '{chat_message}'")
        return jsonify({"status": "ok"})

    # 1. RELAY COMPLETE ORIGINAL DATA TO LOGGER
    await send_to_local_logger(data)

    print(f"\nMCP: Received [Chat]: '{chat_message}'")

    final_response = await process_task(source="chat", user_text=chat_message)

    if final_response:
        # Skip Social Stream for queue messages to prevent loops
        is_queue_message = ("Added" in final_response and "to queue" in final_response) or \
                           final_response.startswith("✅") or \
                           ("Already have" in final_response and "playing now" in final_response)
        
        # 2. SEND COMPLETE AI PAYLOAD TO LOGGER
        tasks = [
            send_to_tts(final_response),
            log_assistant_response(final_response, source_name="ChatAPI"),
            add_chat_to_memory("Gem", final_response),
        ]
        if not is_queue_message:
            tasks.append(send_to_social_stream(final_response))
        await asyncio.gather(*tasks)

    return jsonify({"status": "ok"})


@app.route("/vision", methods=["POST"])
async def handle_vision_request():
    data = await request.get_json()
    user_text = data.get("text", "") or data.get("chatmessage", "")

    # 1. RELAY COMPLETE ORIGINAL DATA TO LOGGER
    await send_to_local_logger(data)

    final_response = await process_task(
        source="vision",
        user_text=user_text,
        vision_context=data.get("vision_context", ""),
    )
    if final_response:
        # Skip Social Stream for queue messages to prevent loops
        is_queue_message = ("Added" in final_response and "to queue" in final_response) or \
                           final_response.startswith("✅") or \
                           ("Already have" in final_response and "playing now" in final_response)
        
        # 2. SEND COMPLETE AI PAYLOAD TO LOGGER
        tasks = [
            send_to_tts(final_response),
            log_assistant_response(final_response, source_name="VisionAPI"),
            add_chat_to_memory("Gem", final_response),
        ]
        if not is_queue_message:
            tasks.append(send_to_social_stream(final_response))
        await asyncio.gather(*tasks)
    return jsonify({"response": final_response})


@app.route("/audio", methods=["POST"])
async def handle_audio_request():
    data = await request.get_json()
    user_text = data.get("text", "") or data.get("chatmessage", "")

    # 1. RELAY COMPLETE ORIGINAL DATA TO LOGGER
    await send_to_local_logger(data)

    final_response = await process_task(source="audio", user_text=user_text)
    if final_response:
        # Skip Social Stream for queue messages to prevent loops
        is_queue_message = ("Added" in final_response and "to queue" in final_response) or \
                           final_response.startswith("✅") or \
                           ("Already have" in final_response and "playing now" in final_response)
        
        # 2. SEND COMPLETE AI PAYLOAD TO LOGGER
        await asyncio.gather(
            send_to_tts(final_response),
            send_to_social_stream(final_response) if not is_queue_message else None,
            log_assistant_response(final_response, source_name="AudioAPI"),
            add_chat_to_memory("Gem", final_response),
        )
    return jsonify({"response": final_response})


@app.route("/update_vision", methods=["POST"])
async def update_vision_context():
    data = await request.get_json()
    if data.get("vision_context"):
        VISION_HISTORY.appendleft(data.get("vision_context"))
    return jsonify({"status": "updated"})


# ------------------------------------------------------------------------------


# --- 6. MAIN EXECUTION BLOCK ---
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("--- Starting UNIFIED ASYNC Master Control Program (MCP) ---")

    if config.get("music_recognition_enabled", False):
        SELECTED_INPUT_DEVICE_INDEX = select_audio_device()

    # Initialize Twitch music checker
    TWITCH_MUSIC_CHECKER = TwitchMusicChecker()

    # Load any saved download queue from file
    download_queue = load_download_queue()

    # Background threads for blocking download worker (keep as thread)
    download_thread = threading.Thread(target=_process_download_queue, daemon=True)
    download_thread.start()

    print(f"--- LLM Mode: {config['llm_choice'].upper()} ---")
    print(f"--- API Server listening on http://{config['host']}:{config['port']} ---")
    print("=" * 70 + "\n")

    # Quart run
    app.run(host=config["host"], port=config["port"], debug=True, use_reloader=False)
