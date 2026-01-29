
import os
from dotenv import load_dotenv
from google import genai

load_dotenv('backend/.env')
api_key = os.getenv('GEMINI_API_KEY')
client = genai.Client(api_key=api_key)

print("Listing models...")
for model in client.models.list():
    print(f"Model: {model.name}, Supported Actions: {model.supported_actions}")
