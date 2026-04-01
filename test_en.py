import asyncio
import os
import sys
from pathlib import Path

# Add backend to path to import services
backend_path = Path(r"c:\Users\pc\Desktop\Bus Ticket Booking Agent\backend")
sys.path.append(str(backend_path))

from services.llm_service import generate_chat_response

async def run_test(name, text, history, lang):
    print(f"\n--- TEST: {name} ---")
    print(f"User ({lang}): {text}")
    try:
        response = await generate_chat_response(text, history, lang)
        print(f"Bot ({lang}): {response}")
        return response
    except Exception as e:
        print(f"Error: {e}")
        return None

async def test_scenarios():
    history = []
    
    # 1. Greeting & Intent
    resp1 = await run_test("Greeting", "Hi, I want to go from Ankara to Istanbul tomorrow.", history, "en")
    history.append({"role": "user", "content": "Hi, I want to go from Ankara to Istanbul tomorrow."})
    history.append({"role": "assistant", "content": resp1})
    
    # 2. Selecting a trip (assuming bot listed trips)
    resp2 = await run_test("Selecting Trip", "I want the 10:00 AM trip with ID 1.", history, "en")
    history.append({"role": "user", "content": "I want the 10:00 AM trip with ID 1."})
    history.append({"role": "assistant", "content": resp2})

if __name__ == "__main__":
    asyncio.run(test_scenarios())
