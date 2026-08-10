import requests
import google.generativeai as genai # Changed import
from threading import Thread
from queue import Queue
# Removed: from openai import OpenAI
import os # Example for loading env vars if needed

from utils.llm.sentence_builder import SentenceBuilder # Assuming this stays the same

# --- Configuration Notes ---
# Your `config` dictionary should now contain:
# - "GEMINI_API_KEY": Your Google AI API key.
# - "GEMINI_MODEL_NAME": e.g., "gemini-1.5-flash-latest", "gemini-pro"
# - Keep other relevant keys: "USE_LOCAL_LLM", "LLM_STREAM_URL", "LLM_API_URL",
#   "USE_STREAMING", "system_message", "max_chunk_length", "flush_token_count"

# --- Example Config Structure ---
# config = {
#     "USE_LOCAL_LLM": False,
#     "USE_STREAMING": True,
#     "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"),
#     "GEMINI_MODEL_NAME": "gemini-1.5-flash-latest",
#     "system_message": "You are Mai, speak naturally...",
#     "max_chunk_length": 500,
#     "flush_token_count": 10,
#     # Add local LLM URLs if USE_LOCAL_LLM is True
#     "LLM_STREAM_URL": "http://localhost:5000/stream",
#     "LLM_API_URL": "http://localhost:5000/generate",
# }
# --- End Example Config ---


def warm_up_llm_connection(config):
    """
    Perform a lightweight dummy request to warm up the LLM connection.
    This avoids the initial delay when the user sends the first real request.
    """
    if config.get("USE_LOCAL_LLM", False): # Added default False
        try:
            # For local LLM, use a dummy ping request with a short timeout.
            requests.post(config["LLM_STREAM_URL"], json={"dummy": "ping"}, timeout=1)
            print("Local LLM connection warmed up.")
        except Exception as e:
            print(f"Local LLM connection warm-up failed: {e}")
    else:
        # Warm up Google Gemini API
        try:
            api_key = config.get("GEMINI_API_KEY")
            model_name = config.get("GEMINI_MODEL_NAME")

            if not api_key:
                raise ValueError("GEMINI_API_KEY not found in configuration.")
            if not model_name:
                raise ValueError("GEMINI_MODEL_NAME not found in configuration.")

            # Configure the Gemini client globally (or manage per request if needed)
            genai.configure(api_key=api_key)

            # Select the model
            model = genai.GenerativeModel(model_name)

            # Send a lightweight ping message.
            # Use generate_content which is the standard method.
            # max_output_tokens is the equivalent of max_tokens.
            response = model.generate_content(
                "ping", # Simple prompt
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=1,
                    temperature=0.1 # Keep temp low for a simple ping
                ),
                stream=False # Use non-streaming for warmup
            )
            # Optional: Check response, though try/except handles API errors
            # print(f"Gemini Warmup Response: {response.text}")
            print("Gemini API connection warmed up.")
        except Exception as e:
            print(f"Gemini API connection warm-up failed: {e}")


def update_ui(token: str):
    """
    Immediately update the UI with the token.
    (This function remains unchanged as it deals with printing tokens)
    """
    token = token.replace('\r\n', '\n')
    if '\n' in token:
        parts = token.split('\n')
        for i, part in enumerate(parts):
            print(part, end='', flush=True)
            if i < len(parts) - 1:
                print()
    else:
        print(token, end='', flush=True)


def build_gemini_compatible_history(chat_history):
    """
    Converts the chat history into the format Gemini expects.
    Alternating 'user' and 'model' roles.
    """
    gemini_history = []
    for entry in chat_history:
        # Ensure input exists and is not empty
        if "input" in entry and entry["input"]:
             gemini_history.append({'role': 'user', 'parts': [entry["input"]]})
        # Ensure response exists and is not empty
        if "response" in entry and entry["response"]:
             gemini_history.append({'role': 'model', 'parts': [entry["response"]]})
    return gemini_history

# --- Renamed build_llm_payload to reflect Gemini usage ---
def build_gemini_request_params(user_input, chat_history, config):
    """
    Build the request parameters for the Gemini API call, including
    history, system instruction, and generation configuration.

    Returns:
        dict: Contains 'history', 'system_instruction', and 'generation_config'.
    """
    system_message = config.get(
        "system_message",
        "You are Mai, speak naturally and like a human might with humour and dryness."
    )
    # Gemini uses a different history format
    gemini_history = build_gemini_compatible_history(chat_history)

    # Gemini generation parameters are grouped in GenerationConfig
    generation_config = genai.types.GenerationConfig(
        # max_new_tokens maps to max_output_tokens
        max_output_tokens=config.get("max_new_tokens", 4000),
        temperature=config.get("temperature", 1.0), # Default to 1.0 if not specified
        top_p=config.get("top_p", 0.9) # Default to 0.9 if not specified
    )

    # Safety settings (optional, but good practice)
    # Adjust as needed based on your use case and content policy needs.
    # safety_settings = [
    #    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    #    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    #    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    #    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]


    return {
        "history": gemini_history,
        "system_instruction": system_message,
        "generation_config": generation_config,
    #    "safety_settings": safety_settings
    }


# Local LLM functions remain largely the same, but ensure payload keys match if needed
def local_llm_streaming(user_input, chat_history, chunk_queue, config):
    """
    Streams tokens from a local LLM using streaming.
    (Assuming build_llm_payload structure was compatible or adapted for local LLM)
    """
    # Note: Ensure your local LLM endpoint expects the payload format generated
    # by the original `build_llm_payload` or adapt accordingly.
    # For simplicity, let's assume the original payload builder is needed here.
    original_payload = build_llm_payload(user_input, chat_history, config) # Using original for local

    full_response = ""
    max_chunk_length = config.get("max_chunk_length", 500)
    flush_token_count = config.get("flush_token_count", 10)

    sentence_builder = SentenceBuilder(chunk_queue, max_chunk_length, flush_token_count)
    token_queue = Queue()
    sb_thread = Thread(target=sentence_builder.run, args=(token_queue,))
    sb_thread.start()

    try:
        session = requests.Session()
        with session.post(config["LLM_STREAM_URL"], json=original_payload, stream=True) as response:
            response.raise_for_status()
            print("\n\nAssistant Response (streaming - local):\n", flush=True)
            for token in response.iter_content(chunk_size=1, decode_unicode=True):
                if not token:
                    continue
                full_response += token
                update_ui(token)
                token_queue.put(token)
        session.close()

        token_queue.put(None)
        sb_thread.join()
        return full_response.strip()

    except Exception as e:
        print(f"\nError during streaming local LLM call: {e}")
        token_queue.put(None) # Ensure queue terminates on error
        sb_thread.join()
        return "Error: Streaming LLM call failed."

# --- Need the original payload builder for local LLM calls ---
def build_llm_payload(user_input, chat_history, config):
    """
    Original payload builder, kept for local LLM compatibility.
    """
    system_message = config.get(
        "system_message",
        "You are Mai, speak naturally and like a human might with humour and dryness."
    )
    messages = [{"role": "system", "content": system_message}]
    for entry in chat_history:
        messages.append({"role": "user", "content": entry["input"]})
        messages.append({"role": "assistant", "content": entry["response"]})
    messages.append({"role": "user", "content": user_input})

    payload = {
        "messages": messages,
        "max_new_tokens": config.get("max_new_tokens", 4000),
        "temperature": config.get("temperature", 1.0),
        "top_p": config.get("top_p", 0.9)
    }
    return payload
# --- End original payload builder ---


def local_llm_non_streaming(user_input, chat_history, chunk_queue, config):
    """
    Calls a local LLM non-streaming endpoint and processes the entire response.
    (Assuming build_llm_payload structure was compatible or adapted for local LLM)
    """
    # Note: Ensure your local LLM endpoint expects the payload format generated
    # by the original `build_llm_payload` or adapt accordingly.
    original_payload = build_llm_payload(user_input, chat_history, config) # Using original for local

    full_response = ""
    max_chunk_length = config.get("max_chunk_length", 500)
    flush_token_count = config.get("flush_token_count", 10)

    sentence_builder = SentenceBuilder(chunk_queue, max_chunk_length, flush_token_count)
    token_queue = Queue()
    sb_thread = Thread(target=sentence_builder.run, args=(token_queue,))
    sb_thread.start()

    try:
        session = requests.Session()
        response = session.post(config["LLM_API_URL"], json=original_payload)
        session.close()
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        result = response.json()
        # Adjust the result parsing based on your local LLM's response structure
        # This is an example assuming a similar structure to the original code's expectation
        text = result.get('assistant', {}).get('content', "Error: No response content found.")
        if "Error:" in text:
             print(f"\nLLM Warning: {text}") # Print error if returned by LLM

        print("Assistant Response (non-streaming - local):\n", flush=True)
        # Process token by token for SentenceBuilder even in non-streaming
        # Split by space is a simple approach, might need refinement
        tokens = text.split(' ')
        for i, token in enumerate(tokens):
            token_with_space = token + (" " if i < len(tokens) - 1 else "") # Add space except for last token
            if token_with_space: # Avoid putting empty strings
                full_response += token_with_space
                update_ui(token_with_space)
                token_queue.put(token_with_space)

        token_queue.put(None)
        sb_thread.join()
        return full_response.strip()

    except requests.exceptions.RequestException as e:
        print(f"\nError calling local LLM API: {e}")
        token_queue.put(None) # Ensure queue terminates on error
        sb_thread.join()
        return f"Error: LLM API call failed ({e})."
    except Exception as e:
        print(f"\nError processing local LLM response: {e}")
        token_queue.put(None) # Ensure queue terminates on error
        sb_thread.join()
        return "Error: Exception occurred during non-streaming local LLM processing."


# --- Renamed openai_llm_streaming to gemini_llm_streaming ---
def gemini_llm_streaming(user_input, chat_history, chunk_queue, config):
    """
    Streams tokens from the Google Gemini API.
    """
    params = build_gemini_request_params(user_input, chat_history, config)
    full_response = ""
    max_chunk_length = config.get("max_chunk_length", 500)
    flush_token_count = config.get("flush_token_count", 10)

    sentence_builder = SentenceBuilder(chunk_queue, max_chunk_length, flush_token_count)
    token_queue = Queue()
    sb_thread = Thread(target=sentence_builder.run, args=(token_queue,))
    sb_thread.start()

    try:
        # Ensure API key is configured (can be done once globally or here)
        api_key = config.get("GEMINI_API_KEY")
        model_name = config.get("GEMINI_MODEL_NAME")
        if not api_key or not model_name:
             raise ValueError("Gemini API Key or Model Name missing in config.")
        genai.configure(api_key=api_key) # Configure if not done globally

        # Create the model instance with system instruction
        model = genai.GenerativeModel(
            model_name,
            system_instruction=params["system_instruction"],
            safety_settings=params["safety_settings"] # Apply safety settings
        )

        # Start a chat session using the history
        chat = model.start_chat(history=params["history"])

        # Send the user message and stream the response
        # Use send_message for conversational context
        response = chat.send_message(
            user_input,
            generation_config=params["generation_config"],
            stream=True
        )

        print("\n\nAssistant Response (streaming - Gemini):\n", flush=True)
        for chunk in response:
            # Access the text content of the chunk
            # Add error handling for potential missing text or parts
            try:
                token = chunk.text
                if token:
                    full_response += token
                    update_ui(token)
                    token_queue.put(token)
            except ValueError:
                 # Handle cases where chunk might not have text (e.g., finish reason)
                 # Or potentially blocked content based on safety settings
                 print(f"\nWarning: Received chunk without text. Possible block or end.", flush=True)
                 # print(f"Chunk details: {chunk}", flush=True) # Uncomment for debugging
                 if chunk.prompt_feedback.block_reason:
                     print(f"Streaming blocked due to: {chunk.prompt_feedback.block_reason}", flush=True)
                     # Decide how to handle blocked content, e.g., stop processing
                     break # Exit loop if content is blocked
            except Exception as chunk_error:
                print(f"\nError processing chunk: {chunk_error}", flush=True)
                # Decide if you want to continue or break on chunk processing errors

        token_queue.put(None) # Signal end of stream
        sb_thread.join()

        # Check final response for safety issues if needed (though chunks might indicate earlier)
        # final_safety = chat.history[-1].safety_ratings if chat.history else None
        # print(f"Final safety ratings: {final_safety}")

        return full_response.strip()

    except Exception as e:
        print(f"\nError calling Gemini API (streaming): {e}")
        token_queue.put(None) # Ensure queue terminates on error
        sb_thread.join()
        # Provide more specific error if possible (e.g., API key error, quota error)
        return f"Error: Gemini API call failed ({e})."


# --- Renamed openai_llm_non_streaming to gemini_llm_non_streaming ---
def gemini_llm_non_streaming(user_input, chat_history, chunk_queue, config):
    """
    Calls the Google Gemini API without streaming.
    """
    params = build_gemini_request_params(user_input, chat_history, config)
    full_response = ""
    max_chunk_length = config.get("max_chunk_length", 500)
    flush_token_count = config.get("flush_token_count", 10)

    sentence_builder = SentenceBuilder(chunk_queue, max_chunk_length, flush_token_count)
    token_queue = Queue()
    sb_thread = Thread(target=sentence_builder.run, args=(token_queue,))
    sb_thread.start()

    try:
        # Ensure API key is configured
        api_key = config.get("GEMINI_API_KEY")
        model_name = config.get("GEMINI_MODEL_NAME")
        if not api_key or not model_name:
             raise ValueError("Gemini API Key or Model Name missing in config.")
        genai.configure(api_key=api_key)

        # Create the model instance with system instruction
        model = genai.GenerativeModel(
            model_name,
            system_instruction=params["system_instruction"],
            safety_settings=params["safety_settings"]
        )

        # Combine history and the new user input for generate_content
        # generate_content is suitable for single-turn or when history is managed externally
        # For multi-turn, start_chat().send_message() is often cleaner, but this works too.
        content_payload = params["history"] + [{'role': 'user', 'parts': [user_input]}]

        response = model.generate_content(
            content_payload, # Pass combined history + current input
            generation_config=params["generation_config"],
            stream=False # Explicitly non-streaming
        )

        # Check for blocked content due to safety settings
        if not response.parts:
            block_reason = response.prompt_feedback.block_reason if response.prompt_feedback else 'Unknown'
            print(f"\nWarning: Gemini response blocked. Reason: {block_reason}", flush=True)
            token_queue.put(None) # Signal end
            sb_thread.join()
            return f"Error: Response blocked due to safety settings ({block_reason})."

        # Access the generated text
        text = response.text

        print("Assistant Response (non-streaming - Gemini):\n", flush=True)
        # Process token by token for SentenceBuilder even in non-streaming
        tokens = text.split(' ')
        for i, token in enumerate(tokens):
            token_with_space = token + (" " if i < len(tokens) - 1 else "")
            if token_with_space:
                full_response += token_with_space
                update_ui(token_with_space)
                token_queue.put(token_with_space)

        token_queue.put(None) # Signal end
        sb_thread.join()
        return full_response.strip()

    except Exception as e:
        print(f"\nError calling Gemini API (non-streaming): {e}")
        token_queue.put(None) # Ensure queue terminates on error
        sb_thread.join()
        return f"Error: Gemini API call failed ({e})."


def stream_llm_chunks(user_input, chat_history, chunk_queue, config):
    """
    Dispatches the LLM call to the proper variant based on the configuration.
    (Updated to call Gemini functions)
    """
    USE_LOCAL_LLM = config.get("USE_LOCAL_LLM", False)
    USE_STREAMING = config.get("USE_STREAMING", True) # Default to streaming if not set

    if USE_LOCAL_LLM:
        if USE_STREAMING:
            return local_llm_streaming(user_input, chat_history, chunk_queue, config)
        else:
            return local_llm_non_streaming(user_input, chat_history, chunk_queue, config)
    else:
        # --- Use Gemini functions ---
        # Ensure necessary Gemini config exists
        if not config.get("GEMINI_API_KEY") or not config.get("GEMINI_MODEL_NAME"):
             print("\nError: GEMINI_API_KEY or GEMINI_MODEL_NAME missing in config for Gemini API call.")
             return "Error: Missing Gemini configuration."

        if USE_STREAMING:
            return gemini_llm_streaming(user_input, chat_history, chunk_queue, config) # Changed call
        else:
            return gemini_llm_non_streaming(user_input, chat_history, chunk_queue, config) # Changed call

# Example Usage (assuming config is loaded and SentenceBuilder exists)
if __name__ == '__main__':
    # --- !!! IMPORTANT: Load your actual config here !!! ---
    # Example using environment variables - replace with your method
    config = {
        "USE_LOCAL_LLM": False, # Set to False to test Gemini
        "USE_STREAMING": True,   # Test streaming
        "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY"), # MUST BE SET IN YOUR ENV
        "GEMINI_MODEL_NAME": "gemini-1.5-flash-latest", # Or "gemini-pro" etc.
        "system_message": "You are a helpful assistant. Respond concisely.",
        "max_new_tokens": 150, # Maps to max_output_tokens
        "temperature": 0.7,
        "top_p": 0.9,
        "max_chunk_length": 100, # For SentenceBuilder
        "flush_token_count": 5,   # For SentenceBuilder
         # Add local LLM URLs if needed, even if USE_LOCAL_LLM is False
        "LLM_STREAM_URL": "http://localhost:11434/api/generate", # Example Ollama URL
        "LLM_API_URL": "http://localhost:11434/api/generate", # Example Ollama URL
    }

    if not config["USE_LOCAL_LLM"] and not config["GEMINI_API_KEY"]:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        exit(1)

    print("--- Warming up connection ---")
    warm_up_llm_connection(config)
    print("\n--- Starting chat simulation ---")

    test_chat_history = [
        # {"input": "Hello there!", "response": "Hi! How can I help you today?"}
    ]
    test_user_input = "Explain the difference between streaming and non-streaming API calls in simple terms."
    output_chunk_queue = Queue() # Queue for SentenceBuilder output (if needed elsewhere)

    print(f"\nUser: {test_user_input}")

    # Simulate the main call
    final_response = stream_llm_chunks(
        test_user_input,
        test_chat_history,
        output_chunk_queue, # Pass the queue for SentenceBuilder
        config
    )

    print("\n--- End of Assistant Response ---")
    print(f"\nFinal assembled response:\n{final_response}")

    # You could potentially process chunks from output_chunk_queue here if needed
    # while not output_chunk_queue.empty():
    #    chunk = output_chunk_queue.get()
    #    print(f"Processed chunk from queue: {chunk}")