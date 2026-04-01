from datetime import datetime
from typing import AsyncGenerator, List, Dict
import asyncio
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
    """Gemini ile sohbet yanıtı üretir (Manuel Araç Çağrı Döngüsü ile)."""
    try:
        from services.tools import get_bus_trips, make_reservation, validate_seat_selection, validate_tc_number, validate_phone_number, validate_email_address
        
        # Tool map for dynamic execution
        tools_map = {
            "get_bus_trips": get_bus_trips,
            "make_reservation": make_reservation,
            "validate_seat_selection": validate_seat_selection,
            "validate_tc_number": validate_tc_number,
            "validate_phone_number": validate_phone_number,
            "validate_email_address": validate_email_address
        }

        summary = get_current_summary(session_id)
        system_prompt = _build_system_prompt(lang, summary)
        
        client = _build_gemini_client()
        gemini_history = _build_history_gemini(history)
        
        # Manuel döngü için automatic_function_calling=False
        chat = client.aio.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[get_bus_trips, make_reservation, validate_seat_selection, validate_tc_number, validate_phone_number, validate_email_address],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.0
            ),
            history=gemini_history
        )

        response = await chat.send_message(text)
        
        # Tool call döngüsü
        while response.candidates[0].content.parts[0].function_call:
            for part in response.candidates[0].content.parts:
                if fn := part.function_call:
                    tool_name = fn.name
                    args = fn.args
                    print(f"[LLM_SERVICE] ARAÇ ÇAĞRISI: {tool_name} (Args: {args})")
                    
                    if tool_name in tools_map:
                        # Fonksiyonu çalıştır
                        try:
                            result = tools_map[tool_name](**args)
                            print(f"[LLM_SERVICE] ARAÇ SONUCU: {result}")
                        except Exception as tool_err:
                            result = f"Hata: {str(tool_err)}"
                        
                        # Sonucu geri gönder
                        response = await chat.send_message(
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part.from_function_response(
                                        name=tool_name,
                                        response={"result": result}
                                    )
                                ]
                            )
                        )
                    else:
                        break
            
            if not response.candidates or not response.candidates[0].content.parts:
                break

        result_text = response.text or ""
        asyncio.create_task(update_memory(text, result_text, session_id))
        return result_text

    except Exception as e:
        err_str = str(e)
        print(f"[LLM_ERROR] {err_str}")
        if "429" in err_str or "quota" in err_str.lower():
            return "Şu an API kotam doldu, biraz bekleyip tekrar dener misin?"
        raise Exception(f"Gemini LLM Hatası: {err_str}")


async def generate_chat_response_stream(text: str, history: List[Dict[str, str]], lang: str, session_id: str = "default") -> AsyncGenerator[str, None]:
    """Streaming Gemini yanıtı (Manuel döngü ile araç çağrılarını destekler)."""
    # Basitlik için stream modunda da önce araçları çözer, sonra metni akıtırız
    # Bu, "streaming tool calls" yapmaktan daha stabildir.
    try:
        final_text = await generate_chat_response(text, history, lang, session_id)
        # Kelime kelime simüle et (veya doğrudan yield et)
        # Gerçek stream için tool call bittikten sonra send_message_stream çağrılmalı
        yield final_text
    except Exception as e:
        yield f"Hata: {str(e)}"
