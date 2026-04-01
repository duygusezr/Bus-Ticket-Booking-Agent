import asyncio
import os
import sys
from pathlib import Path

# Add backend to path to import services
backend_path = Path(r"c:\Users\pc\Desktop\Bus Ticket Booking Agent\backend")
sys.path.append(str(backend_path))

from services.llm_service import generate_chat_response

async def run_test(name, text, history, lang):
    print(f"\n--- TEST step: {name} ---")
    print(f"User ({lang}): {text}")
    try:
        response = await generate_chat_response(text, history, lang)
        print(f"Bot ({lang}): {response}")
        return response
    except Exception as e:
        print(f"Error: {e}")
        return None

async def test_full_scenario():
    history = []
    
    # 1. Start
    r1 = await run_test("Start", "Hi, I want to book a ticket from Ankara to Istanbul tomorrow.", history, "en")
    history.append({"role": "user", "content": "Hi, I want to book a ticket from Ankara to Istanbul tomorrow."})
    history.append({"role": "assistant", "content": r1})
    
    # 2. Select Date (Bot said 12 April)
    r2 = await run_test("Select Date", "April 12th, 2026", history, "en")
    history.append({"role": "user", "content": "April 12th, 2026"})
    history.append({"role": "assistant", "content": r2})
    
    # 3. Select Seat
    r3 = await run_test("Select Seat", "I want seat number 5.", history, "en")
    history.append({"role": "user", "content": "I want seat number 5."})
    history.append({"role": "assistant", "content": r3})
    
    # 4. Confirmation of seat
    r4 = await run_test("Confirm Seat", "Yes, continue.", history, "en")
    history.append({"role": "user", "content": "Yes, continue."})
    history.append({"role": "assistant", "content": r4})
    
    # 5. Name
    r5 = await run_test("Name", "Eren Gungormez", history, "en")
    history.append({"role": "user", "content": "Eren Gungormez"})
    history.append({"role": "assistant", "content": r5})
    
    # 6. TC
    r6 = await run_test("TC", "49891147104", history, "en")
    history.append({"role": "user", "content": "49891147104"})
    history.append({"role": "assistant", "content": r6})
    
    # 7. Phone
    r7 = await run_test("Phone", "05372791437", history, "en")
    history.append({"role": "user", "content": "05372791437"})
    history.append({"role": "assistant", "content": r7})
    
    # 8. Email
    r8 = await run_test("Email", "erengungormez4@gmail.com", history, "en")
    history.append({"role": "user", "content": "erengungormez4@gmail.com"})
    history.append({"role": "assistant", "content": r8})
    
    # 9. Final Confirm
    r9 = await run_test("Confirm Final", "Yes, I confirm details.", history, "en")
    history.append({"role": "user", "content": "Yes, I confirm details."})
    history.append({"role": "assistant", "content": r9})

if __name__ == "__main__":
    asyncio.run(test_full_scenario())
