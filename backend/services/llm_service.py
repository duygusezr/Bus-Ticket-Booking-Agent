import logging
import asyncio
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any

import google.genai as genai
from google.genai import types

from config import settings
from services.memory_service import get_current_summary, update_memory
from services.session_state import update_session_from_tool_result

logger = logging.getLogger(__name__)

GEMINI_MODEL = settings.GEMINI_CHAT_MODEL

# Singleton client — modül yüklendiğinde bir kez oluşturulur, tüm isteklerde paylaşılır.
_GEMINI_CLIENT = genai.Client(api_key=settings.GOOGLE_API_KEY)


def _get_tools() -> dict:
    from services.tools import (
        get_bus_trips, make_reservation, validate_seat_selection,
        validate_tc_number, validate_phone_number, validate_email_address,
    )
    return {
        "get_bus_trips": get_bus_trips,
        "make_reservation": make_reservation,
        "validate_seat_selection": validate_seat_selection,
        "validate_tc_number": validate_tc_number,
        "validate_phone_number": validate_phone_number,
        "validate_email_address": validate_email_address,
    }


def _build_gemini_history(history: List[Dict[str, str]]) -> list:
    result = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        result.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    return result


def _build_system_prompt(lang: str, summary: str) -> str:
    now = datetime.now()
    prefix = (
        f"BUGÜNÜN TARİHİ: {now.strftime('%Y-%m-%d')}\n"
        f"ŞU ANKİ SAAT: {now.strftime('%H:%M')}\n\n"
    )

    if lang == "en":
        prompt = prefix + settings.SYSTEM_PROMPT_EN
        prompt += "\n\n## STRICT LANGUAGE RULE\nYou MUST reply ONLY in English."
    else:
        prompt = prefix + settings.SYSTEM_PROMPT
        prompt += "\n\n## STRICT LANGUAGE RULE\nCevaplarını SADECE Türkçe olarak vermelisin."

    if summary:
        header = (
            "--- SUMMARY OF PREVIOUS CONVERSATION ---"
            if lang == "en"
            else "--- GEÇMİŞ KONUŞMALARIN ÖZETİ ---"
        )
        prompt += f"\n\n{header}\n{summary}\n{'-' * 37}"

    return prompt


def _has_function_call(response: Any) -> bool:
    """İlk adayın ilk parçasında function_call var mı? Güvenli kontrol."""
    try:
        parts = response.candidates[0].content.parts
        return bool(parts) and parts[0].function_call is not None
    except (IndexError, AttributeError):
        return False


async def generate_chat_response(
    text: str,
    history: List[Dict[str, str]],
    lang: str,
    session_id: str = "default",
) -> str:
    """Manuel araç-çağrı döngüsüyle Gemini yanıtı üret."""
    try:
        tools_map = _get_tools()
        tool_functions = list(tools_map.values())

        summary = get_current_summary(session_id)
        system_prompt = _build_system_prompt(lang, summary)

        chat = _GEMINI_CLIENT.aio.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=tool_functions,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                temperature=0.0,
            ),
            history=_build_gemini_history(history),
        )

        response = await chat.send_message(text)

        # Araç çağrı döngüsü (sonsuz döngüyü önlemek için max 10 iterasyon)
        for _ in range(10):
            if not _has_function_call(response):
                break

            function_responses: list[types.Part] = []
            for part in response.candidates[0].content.parts:
                fn = part.function_call
                if fn is None:
                    continue

                logger.info("Araç çağrısı: %s(%s)", fn.name, dict(fn.args))

                if fn.name not in tools_map:
                    logger.warning("Bilinmeyen araç: %s", fn.name)
                    continue

                try:
                    result = tools_map[fn.name](**fn.args)
                except Exception as tool_err:
                    result = f"Hata: {tool_err}"

                logger.info("Araç sonucu [%s]: %s", fn.name, result)

                # Oturum durumunu araç sonucuna göre güncelle
                update_session_from_tool_result(
                    session_id=session_id,
                    tool_name=fn.name,
                    tool_args=dict(fn.args),
                    tool_result=str(result),
                )

                function_responses.append(
                    types.Part.from_function_response(
                        name=fn.name, response={"result": result}
                    )
                )

            if not function_responses:
                break

            response = await chat.send_message(
                types.Content(role="user", parts=function_responses)
            )

        result_text = response.text or ""
        asyncio.create_task(update_memory(text, result_text, session_id))
        return result_text

    except Exception as e:
        err = str(e)
        logger.error("LLM hatası: %s", err)
        if "429" in err or "quota" in err.lower():
            return "Şu an API kotam doldu, biraz bekleyip tekrar dener misin?"
        raise RuntimeError(f"Gemini LLM Hatası: {err}") from e


async def generate_chat_response_stream(
    text: str,
    history: List[Dict[str, str]],
    lang: str,
    session_id: str = "default",
) -> AsyncGenerator[str, None]:
    """
    Streaming sarmalayıcı.

    Not: Gemini SDK'sının araç çağrısını streaming modda çözmek karmaşık
    olduğundan, araç döngüsü önce tam olarak tamamlanır, ardından metin
    tek seferde yield edilir. Gerçek token akışı için Gemini'nin native
    streaming + araç döngüsü entegrasyonu gereklidir.
    """
    try:
        final_text = await generate_chat_response(text, history, lang, session_id)
        yield final_text
    except Exception as e:
        yield f"Hata: {e}"
