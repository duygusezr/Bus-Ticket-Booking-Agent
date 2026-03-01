from typing import AsyncGenerator, List, Dict
# FutureWarning FIX: google.generativeai → google.genai
import google.genai as genai
from google.genai import types
from config import settings
from services.memory_service import get_current_summary, update_memory

GEMINI_MODEL = settings.GEMINI_CHAT_MODEL

def _build_client():
    return genai.Client(api_key=settings.GOOGLE_API_KEY)

def _build_history(history: List[Dict[str, str]]) -> list:
    result = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        result.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    return result

async def generate_chat_response(text: str, history: List[Dict[str, str]], lang: str, session_id: str = "default", _tried_keys: int = 0) -> str:
    """Gemini ile sohbet yanıtı üretir. Hafıza özeti ekler."""
    try:
        if not settings.GOOGLE_API_KEY or "YOUR_GEMINI" in settings.GOOGLE_API_KEY:
            return "Sistem: Gemini API anahtarı ayarlanmamış. Lütfen .env dosyasını kontrol edin."

        summary = get_current_summary(session_id)
        system_prompt = settings.SYSTEM_PROMPT
        # Dil kuralını zorla ekle
        if lang == "en":
            system_prompt += "\n\n## STRICT LANGUAGE RULE\nYou MUST reply ONLY in English. If the user writes in Turkish or any other language, do NOT answer in that language. Instead, kindly say: 'I'd love to chat, but could you speak English with me here?'"
        else:
            system_prompt += "\n\n## STRICT LANGUAGE RULE\nYou MUST reply ONLY in Turkish. If the user writes in English or any other language, do NOT answer in that language. Instead, kindly say: 'Seninle konuşmak isterim ama burada Türkçe konuşur musun?'"
        if summary:
            system_prompt += f"\n\n--- GEÇMİŞ KONUŞMALARIN ÖZETİ ---\n{summary}\n---------------------------------"

        client = _build_client()
        gemini_history = _build_history(history)

        response = await client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=gemini_history + [types.Content(role="user", parts=[types.Part(text=text)])],
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )

        result_text = response.text
        update_memory(text, result_text, session_id)
        return result_text

    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            total_keys = len(settings._keys)
            if _tried_keys + 1 < total_keys:
                settings.rotate_key()
                return await generate_chat_response(text, history, lang, session_id, _tried_keys + 1)
            return "Şu an tüm API kotalarım doldu, biraz bekleyip tekrar dener misin?"
        raise Exception(f"Gemini LLM Hatası: {str(e)}")


async def generate_chat_response_stream(text: str, history: List[Dict[str, str]], lang: str, session_id: str = "default", _tried_keys: int = 0) -> AsyncGenerator[str, None]:
    """Streaming Gemini yanıtı. Hafıza özeti ekler."""
    try:
        if not settings.GOOGLE_API_KEY or "YOUR_GEMINI" in settings.GOOGLE_API_KEY:
            yield "Sistem: Gemini API anahtarı ayarlanmamış."
            return

        summary = get_current_summary(session_id)
        system_prompt = settings.SYSTEM_PROMPT
        # Dil kuralını zorla ekle
        if lang == "en":
            system_prompt += "\n\n## STRICT LANGUAGE RULE\nYou MUST reply ONLY in English. If the user writes in Turkish or any other language, do NOT answer in that language. Instead, kindly say: 'I'd love to chat, but could you speak English with me here?'"
        else:
            system_prompt += "\n\n## STRICT LANGUAGE RULE\nYou MUST reply ONLY in Turkish. If the user writes in English or any other language, do NOT answer in that language. Instead, kindly say: 'Seninle konuşmak isterim ama burada Türkçe konuşur musun?'"
        if summary:
            system_prompt += f"\n\n--- GEÇMİŞ KONUŞMALARIN ÖZETİ ---\n{summary}\n---------------------------------"

        client = _build_client()
        gemini_history = _build_history(history)

        full_text = ""
        async for chunk in await client.aio.models.generate_content_stream(
            model=GEMINI_MODEL,
            contents=gemini_history + [types.Content(role="user", parts=[types.Part(text=text)])],
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        ):
            if chunk.text:
                full_text += chunk.text
                yield chunk.text

        update_memory(text, full_text, session_id)

    except Exception as e:
        if "429" in str(e) or "quota" in str(e).lower():
            total_keys = len(settings._keys)
            if _tried_keys + 1 < total_keys:
                settings.rotate_key()
                async for chunk in generate_chat_response_stream(text, history, lang, session_id, _tried_keys + 1):
                    yield chunk
                return
            yield "Şu an tüm API kotalarım doldu, biraz bekleyip tekrar dener misin?"
            return
        raise Exception(f"Gemini Stream Hatası: {str(e)}")
