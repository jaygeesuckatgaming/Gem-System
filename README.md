This is an old readme it will be updated......
!! OBS I´m using Python 3.10 when testing, it might work with other versions but thats the python version i use..

Gem-System and Neurosync are now using the same venv (Conda).

For Unreal Engine Face Blendshapes its using the same technology as Convai (As far as i can tell) https://www.convai.com/

!! OBS !! Files in the Neurosync folder is under a dual licence and you can find the licence here https://github.com/AnimaVR/NeuroSync_Player/blob/main/LICENCE

!! OBS !! Files in the StyleTTS folder is under the MIT License

I´m not a programmer so this code probably isnt the fastest or best. This Is something i made because i couldn't find a system that had what i wanted. And with this system its "easier" to add more functions/Tools. So hopefully someone finds it interesting or usefull. The main goal with the project was to make an AI "VTuber" or what ever to call it, that "lives" inside Unreal Engine and since it is for an AI "VTuber" it is connected to Social Stream Ninja so stream chats can interact with it.

As of now the default configuration is using llava:7b for Chat,Vision and embedding

Music recognition is using https://rapidapi.com/ for now that connects to Shazam...


*Documentation made with the help of Gemini...*

---

## Key Features

*   **Speech:** Using StyleTTS2 as default TTS.
*   **Vision:** Uses a physical webcam or a virtual NDI stream as its visual input.
*   **Hearing:** Listens for and transcribes spoken commands from a microphone. It also uses this for music recognition.
*   **Music recognition** using rapidapi.com that connects to Shazam.
*   **Can look up what time it is** E.x ´Gem what time is it in Bangkok´ and it can look up the time for Bangkok.
*   **Location Awareness:** Remembers its "current location" (e.g., in Unreal Engine using nav points) and includes it as context for the LLM.
*   **OSC Command Bypass:** Can send direct action commands to external programs like Unreal Engine without involving the LLM. E.x Gem go to the balcony and it goes to that nav point in Unreal Engine.
*   **Face Blendshapes:** Created through Neurosync. For programs that supports Livelink. Tested with Unreal Engine and InZoi.

  
*   **Multi-Architecture Support:** Can run in a unified multimodal mode (`ollama_vision`) using models like `llava:7b` or a pipelined, text-description mode (`ollama`, `gemini`).
*   **Unified RAG/CAG Memory:** Includes a complete long-term memory system using `ChromaDB` for both chat history and image memory, with a high-speed in-memory cache for repeated queries.
*   **Dedicated Embedding Model:** Supports using a specific model for creating consistent vector embeddings.
*   **Model Verification:** Includes a robust check at startup to ensure all required Ollama models are installed, preventing silent failures.
*   **Flexible Wake Word:** Understands conversational wake words (e.g., "So Gem...") instead of just at the start of a sentence.
*   **Multi-Platform Broadcasting:** Can send its final responses to multiple social media platforms (Discord, Twitch, etc.) at once using Social Stream Ninja.
*   **Comprehensive Error Handling:** Includes detailed logging for better debugging of all integrated services.
*   ...and more.

---

## Project Overview

This project is a sophisticated AI system designed around a central "brain" called the **Master Control Program (MCP)**. It features a flexible, multimodal architecture, allowing it to process and understand text, images, and audio. This design enables it to operate in a unified mode—processing multiple data types at once—or in specialized pipelines that handle each type of input separately.

The system is engineered to be highly interactive, not only conversing with users but also interfacing with external platforms and game engines to create a dynamic and immersive experience.

### Core Components

At its heart, the system is comprised of several key scripts that work in concert:

*   **Master Control Program (`mcp_v1b.py`):** This is the central hub of the entire system. It receives inputs from all other components, decides how to process them, and orchestrates the AI's behavior. It supports different language models and modes of operation, including a unified multimodal mode for advanced models that can understand images and text simultaneously. The MCP maintains the system's memory using a robust vector database (`ChromaDB`), is aware of its virtual location, and can broadcast messages to multiple platforms. Crucially, it also sends and receives commands from external applications, such as Unreal Engine via OSC.

*   **Vision Service (`vision.py`):** This script acts as the eyes of the system, capturing video input from a physical **webcam** or a virtual **NDI (Network Device Interface) stream**. This flexibility allows for both simple local setups and more complex production environments where video is streamed over a network. The service has a dual-mode capability: it can either provide raw image data for direct analysis by the MCP or use a local Vision Language Model (VLM) to generate text descriptions of what it sees.

*   **Audio Client (`listen.py`):** This is the ears of the system. It continuously listens for spoken commands through a microphone. Using a local Whisper model, it transcribes any speech it hears into text and sends it to the MCP for interpretation and action.

*   **Facial Animation (`watcher_to_face.py` and `neurosync_local_api.py`):** These scripts give the system a face. The `watcher_to_face.py` script monitors for audio output and triggers corresponding facial animations. The `neurosync_local_api.py` provides an interface to convert audio signals into the detailed facial movements (blendshapes) needed for realistic animation.

### External Integrations

A key feature of this system is its ability to connect with other services and applications:

*   **Social Stream Ninja:** For text-based chat, the system integrates with Social Stream Ninja. This allows the MCP to receive chat messages from users on various social platforms (like Twitch, YouTube, etc.) and send its responses back to be broadcast to those audiences. This turns the AI into an interactive social presence.

*   **Unreal Engine (via OSC):** The system communicates with Unreal Engine using the **Open Sound Control (OSC)** protocol. This allows the MCP to send commands directly into the game engine to control an avatar, trigger events, change the environment, or interact with objects, making the AI a true agent within a virtual world.

### How It Works

The system is designed to be highly modular. A typical interaction can follow several paths:

1.  **Input:** An interaction is initiated. This can happen in two primary ways:
    *   A user speaks a command, which is picked up by the **Audio Client**, transcribed, and sent to the MCP.
    *   A user types a message in a chat connected to **Social Stream Ninja**, which forwards the text to the MCP.

2.  **Processing:** The MCP receives the text. If the command requires visual information (e.g., "what do you see?"), it requests data from the **Vision Service**, which is capturing a feed from a webcam or NDI source. The MCP then uses its language model to interpret the user's request in the full context of the conversation and any visual data.

3.  **Action & Response:** The MCP formulates a response and takes action.
    *   **Spoken Response:** The text response is sent to a text-to-speech (TTS) engine, generating an audio file.
    *   **Facial Animation:** The **Facial Animation** scripts detect this audio file and use the `neurosync_local_api.py` to generate synchronized facial movements for a virtual character.
    *   **Game Engine Control:** If the command was an action (e.g., "go to the kitchen"), the MCP sends a command via **OSC to Unreal Engine** to move the character.
    *   **Chat Broadcast:** The text response is also sent back through **Social Stream Ninja** to be displayed in the chat.

This unified and pipelined approach allows for a rich, interactive experience where the AI can not only understand and respond to users across multiple platforms but also perceive and react to its visual environment, all while presenting a dynamic and expressive virtual persona in Unreal Engine.

