import sys
import os
import asyncio
from pathlib import Path

# Add backend to sys.path to resolve imports properly
base_dir = Path(__file__).parent.resolve()
backend_dir = base_dir / "backend"
sys.path.append(str(backend_dir))

from services.llm_service import generate_chat_response

async def main():
    history = []
    text = "Antalya'dan Adana'ya 1 Temmuz için otobüs var mı?"
    print("User:", text)
    response = await generate_chat_response(text, history, "tr", "test_session_1")
    print("Gemini:", response)

if __name__ == "__main__":
    asyncio.run(main())
