from datetime import datetime
from typing import AsyncGenerator, List, Dict
import google.genai as genai
from google.genai import types
from config import settings
from services.memory_service import get_current_summary, update_memory

GEMINI_MODEL = settings.GEMINI_CHAT_MODEL


def _build_gemini_client():
    return genai.Client(api_key=settings.GOOGLE_API_KEY)


def _build_history_gemini(history: List[Dict[str, str]]) -> list:
    result = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        result.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    return result


def _build_system_prompt(lang: str, summary: str) -> str:
    # Sisteme bugünün tarihini enjekte et
    today_str = datetime.now().strftime("%Y-%m-%d")
    current_time_str = datetime.now().strftime("%H:%M")
    
    prefix = f"BUGÜNÜN TARİHİ: {today_str}\nŞU ANKİ SAAT: {current_time_str}\n\n"
    
    if lang == "en":
        system_prompt = prefix + settings.SYSTEM_PROMPT_EN
        system_prompt += "\n\n## STRICT LANGUAGE RULE\nYou MUST reply ONLY in English. Use English for all responses."
    else:
        system_prompt = prefix + settings.SYSTEM_PROMPT
        system_prompt += "\n\n## STRICT LANGUAGE RULE\nCevaplarını SADECE Türkçe olarak vermelisin. Başka dilde konuşma."
    
    if summary:
        if lang == "en":
            system_prompt += f"\n\n--- SUMMARY OF PREVIOUS CONVERSATION ---\n{summary}\n---------------------------------"
        else:
            system_prompt += f"\n\n--- GEÇMİŞ KONUŞMALARIN ÖZETİ ---\n{summary}\n---------------------------------"
            
    return system_prompt


async def generate_chat_response(text: str, history: List[Dict[str, str]], lang: str, session_id: str = "default") -> str:
    """Gemini ile sohbet yanıtı üretir."""
    try:
        from services.tools import get_bus_trips, make_reservation, validate_seat_selection, validate_tc_number, validate_phone_number, validate_email_address
        summary = get_current_summary(session_id)
        system_prompt = _build_system_prompt(lang, summary)
        
        client = _build_gemini_client()
        gemini_history = _build_history_gemini(history)
        
        chat = client.aio.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[get_bus_trips, make_reservation, validate_seat_selection, validate_tc_number, validate_phone_number, validate_email_address],
                temperature=0.0
            ),
            history=gemini_history
        )
        response = await chat.send_message(text)
        result_text = response.text or ""
        update_memory(text, result_text, session_id)
        return result_text
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower():
            return "Şu an API kotam doldu, biraz bekleyip tekrar dener misin?"
        raise Exception(f"Gemini LLM Hatası: {err_str}")


async def generate_chat_response_stream(text: str, history: List[Dict[str, str]], lang: str, session_id: str = "default") -> AsyncGenerator[str, None]:
    """Streaming Gemini yanıtı."""
    summary = get_current_summary(session_id)
    system_prompt = _build_system_prompt(lang, summary)
    try:
        from services.tools import get_bus_trips, make_reservation, validate_seat_selection, validate_tc_number, validate_phone_number, validate_email_address
        client = _build_gemini_client()
        gemini_history = _build_history_gemini(history)
        
        chat = client.aio.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[get_bus_trips, make_reservation, validate_seat_selection, validate_tc_number, validate_phone_number, validate_email_address],
                temperature=0.3
            ),
            history=gemini_history
        )
        
        full_text = ""
        async for chunk in await chat.send_message_stream(text):
            if chunk.text:
                full_text += chunk.text
                yield chunk.text
        update_memory(text, full_text, session_id)
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower():
            yield "Şu an API kotam doldu, biraz bekleyip tekrar dener misin?"
            return
        raise Exception(f"Gemini Stream Hatası: {err_str}")
