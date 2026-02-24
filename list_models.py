
import google.genai as genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("API Key not found in environment variables.")
else:
    client = genai.Client(api_key=api_key)
    with open("models_list_utf8.txt", "w", encoding="utf-8") as f:
        f.write("List of available models:\n")
        try:
            for m in client.models.list():
                f.write(f"Name: {m.name}\n")
                f.write(f"Supported methods: {m.supported_generation_methods}\n")
                f.write("-" * 20 + "\n")
            print("Successfully wrote to models_list_utf8.txt")
        except Exception as e:
            print(f"Error listing models: {e}")
