import os
import asyncio
import google.genai as genai
from google.genai import types
from pathlib import Path
import sys

# Add backend to path to import tools
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "backend"))

from backend.config import settings
from backend.services.tools import get_bus_trips

async def test_tool_calling():
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    print(f"Using Model: {settings.GEMINI_CHAT_MODEL}")
    
    try:
        chat = client.aio.chats.create(
            model=settings.GEMINI_CHAT_MODEL,
            config=types.GenerateContentConfig(
                tools=[get_bus_trips],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
                temperature=0.0
            )
        )
        
        print("Sending message...")
        response = await chat.send_message("Bursa'dan İstanbul'a seferleri bul.")
        print("Response received!")
        print(f"Text: {response.text}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_tool_calling())
