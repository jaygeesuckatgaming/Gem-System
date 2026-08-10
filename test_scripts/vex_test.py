import sqlite3
import datetime
import os
import sqlite_vec # This is needed to load the sqlite-vec extension

class ChatHistoryDB:
    def __init__(self, db_name="rag_chat_history.db"):
        """
        Initializes the database connection, loads sqlite-vec, and creates the chat_history table if it doesn't exist.
        """
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_table()

    def _connect(self):
        """
        Establishes a connection to the SQLite database and loads the sqlite-vec extension.
        """
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()

            # Enable extension loading
            self.conn.enable_load_extension(True)

            # Load the sqlite-vec extension
            try:
                sqlite_vec.load(self.conn)
                print("sqlite-vec extension loaded successfully.")
            except sqlite3.OperationalError as e:
                print(f"Warning: Could not load sqlite-vec extension. "
                      f"Ensure it's installed and accessible. Error: {e}")
                print("You might need to install it with 'pip install sqlite-vec'")
                print("On macOS, you might need a Python version from Homebrew or 'sqlean.py' for extension support.")
            
            # Disable extension loading for security after loading is complete
            self.conn.enable_load_extension(False)

        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")

    def _create_table(self):
        """
        Creates the chat_history table if it does not already exist.
        The schema is updated to support different message types (text, image)
        and separate columns for text content and file paths.
        """
        if self.cursor:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    message_type TEXT NOT NULL, -- e.g., 'text', 'image'
                    content_text TEXT,          -- for text messages
                    content_path TEXT,          -- for image paths or other file references
                    timestamp TEXT NOT NULL
                )
            """)
            self.conn.commit()

    def save_message(self, sender, message_type, content_data, content_path=None):
        """
        Saves a chat message to the database, supporting text and image references.

        Args:
            sender (str): The name or ID of the sender (e.g., "User", "Assistant").
            message_type (str): The type of message (e.g., "text", "image").
            content_data (str): The main content (e.g., text message, or a description for an image).
            content_path (str, optional): The file path for image messages. Defaults to None.
        """
        if self.cursor:
            timestamp = datetime.datetime.now().isoformat()
            try:
                self.cursor.execute(
                    """INSERT INTO chat_history (sender, message_type, content_text, content_path, timestamp) 
                       VALUES (?, ?, ?, ?, ?)""",
                    (sender, message_type, content_data if message_type == 'text' else None, content_path, timestamp)
                )
                self.conn.commit()
                # print(f"Message ({message_type}) from {sender} saved.")
            except sqlite3.Error as e:
                print(f"Error saving message: {e}")
        else:
            print("Database connection not established.")

    def get_chat_history(self, limit=None):
        """
        Retrieves the chat history from the database, ordered by timestamp.

        Args:
            limit (int, optional): The maximum number of messages to retrieve.
                                   If None, all messages are retrieved.

        Returns:
            list: A list of tuples, where each tuple represents a message:
                  (id, sender, message_type, content_text, content_path, timestamp).
        """
        if self.cursor:
            query = """SELECT id, sender, message_type, content_text, content_path, timestamp 
                       FROM chat_history ORDER BY timestamp ASC"""
            if limit:
                query += f" LIMIT {limit}"
            try:
                self.cursor.execute(query)
                return self.cursor.fetchall()
            except sqlite3.Error as e:
                print(f"Error retrieving chat history: {e}")
                return []
        else:
            print("Database connection not established.")
            return []

    def clear_chat_history(self):
        """
        Deletes all messages from the chat_history table.
        """
        if self.cursor:
            try:
                self.cursor.execute("DELETE FROM chat_history")
                self.conn.commit()
                print("Chat history cleared.")
            except sqlite3.Error as e:
                print(f"Error clearing chat history: {e}")
        else:
            print("Database connection not established.")

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
            # print("Database connection closed.")


# --- Example Usage ---
if __name__ == "__main__":
    db_manager = ChatHistoryDB("my_rag_image_chat.db")

    print("--- Saving Messages ---")
    db_manager.save_message("User", "text", "Hello there, RAG system!")
    db_manager.save_message("Assistant", "text", "Hi! How can I help you today?")
    db_manager.save_message("User", "text", "I need some information about large language models.")
    
    # Simulate saving an image reference
    image_path_1 = "./data/user_query_image.jpg" # This path would point to your actual image file
    # For demonstration, let's create a dummy file if it doesn't exist
    os.makedirs(os.path.dirname(image_path_1) or '.', exist_ok=True)
    if not os.path.exists(image_path_1):
        with open(image_path_1, 'w') as f:
            f.write("dummy image content") # In a real scenario, this would be an actual image
        print(f"Created dummy image file: {image_path_1}")
    db_manager.save_message("User", "image", "Here's a diagram I'm looking at.", content_path=image_path_1)
    
    db_manager.save_message("Assistant", "text", "I see. What aspects of the diagram are you interested in?")
    
    image_path_2 = "./data/assistant_response_image.png"
    os.makedirs(os.path.dirname(image_path_2) or '.', exist_ok=True)
    if not os.path.exists(image_path_2):
        with open(image_path_2, 'w') as f:
            f.write("dummy assistant image content")
        print(f"Created dummy image file: {image_path_2}")
    db_manager.save_message("Assistant", "image", "This architecture might be relevant.", content_path=image_path_2)
    
    db_manager.save_message("User", "text", "Tell me more about the encoder-decoder structure shown in the image.")


    print("\n--- Full Chat History ---")
    history = db_manager.get_chat_history()
    for msg_id, sender, msg_type, content_text, content_path, timestamp in history:
        if msg_type == 'text':
            print(f"[{timestamp}] {sender} (Text): {content_text}")
        elif msg_type == 'image':
            print(f"[{timestamp}] {sender} (Image, Description: '{content_text or 'N/A'}'): Path: {content_path}")

    print("\n--- Last 3 Messages ---")
    last_three = db_manager.get_chat_history(limit=3)
    for msg_id, sender, msg_type, content_text, content_path, timestamp in last_three:
        if msg_type == 'text':
            print(f"[{timestamp}] {sender} (Text): {content_text}")
        elif msg_type == 'image':
            print(f"[{timestamp}] {sender} (Image, Description: '{content_text or 'N/A'}'): Path: {content_path}")

    # Uncomment to clear history
    # print("\n--- Clearing History and Adding New Messages ---")
    # db_manager.clear_chat_history()
    # db_manager.save_message("User", "text", "Starting a new conversation.")
    # db_manager.save_message("Assistant", "text", "Welcome back! What's on your mind?")

    # print("\n--- New Chat History ---")
    # new_history = db_manager.get_chat_history()
    # for msg_id, sender, msg_type, content_text, content_path, timestamp in new_history:
    #     if msg_type == 'text':
    #         print(f"[{timestamp}] {sender} (Text): {content_text}")
    #     elif msg_type == 'image':
    #         print(f"[{timestamp}] {sender} (Image, Description: '{content_text or 'N/A'}'): Path: {content_path}")

    db_manager.close()