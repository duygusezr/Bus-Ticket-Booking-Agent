import logging
import asyncio
import re
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any

import google.genai as genai
from google.genai import types

from config import settings
from services.memory_service import get_current_summary, update_memory
from services.session_state import update_session_from_tool_result
from services.types import ToolResult

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


# ── İç enjeksiyon kalıplarını LLM çıktısından temizle ─────────
_INTERNAL_BLOCK_RE = re.compile(
    r'\[(?:ABSOLUTE SYSTEM TRUTH|SİSTEM BİLGİSİ|SYSTEM INFORMATION)'
    r'[^\]]*\]',
    re.IGNORECASE | re.DOTALL,
)

def _sanitize_response(text: str) -> str:
    """LLM yanıtından iç enjeksiyon bloklarını sil."""
    cleaned = _INTERNAL_BLOCK_RE.sub('', text)
    # Birden fazla boşluk / satır başını düzelt
    cleaned = re.sub(r'  +', ' ', cleaned)
    return cleaned.strip()


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
    MAX_RETRIES = 3
    last_err: Exception | None = None

    for attempt in range(MAX_RETRIES):
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
                        result: ToolResult = await tools_map[fn.name](**fn.args) \
                            if asyncio.iscoroutinefunction(tools_map[fn.name]) \
                            else tools_map[fn.name](**fn.args)
                    except Exception as tool_err:
                        logger.exception("Araç çağrısı hatası [%s]: %s", fn.name, tool_err)
                        result = ToolResult(message=f"Hata: {tool_err}", success=False)

                    logger.info("Araç sonucu [%s]: %s", fn.name, result.message)

                    # Oturum durumunu araç sonucuna göre güncelle
                    update_session_from_tool_result(
                        session_id=session_id,
                        tool_name=fn.name,
                        tool_args=dict(fn.args),
                        tool_result=result,
                    )

                    function_responses.append(
                        types.Part.from_function_response(
                            name=fn.name, response={"result": result.message}
                        )
                    )

                if not function_responses:
                    break

                response = await chat.send_message(function_responses)

            result_text = _sanitize_response(response.text or "")
            asyncio.create_task(update_memory(text, result_text, session_id))
            return result_text

        except Exception as e:
            last_err = e
            err = str(e)
            is_transient = "503" in err or "429" in err or "quota" in err.lower() or "unavailable" in err.lower()

            if is_transient and attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 1.5          # 1.5s, 3s
                logger.warning("Gemini geçici hata (deneme %d/%d): %s — %.1fs sonra yeniden deneniyor",
                               attempt + 1, MAX_RETRIES, err[:120], wait)
                await asyncio.sleep(wait)
                continue

            logger.error("LLM hatası: %s", err)
            if is_transient:
                return ("Gemini şu an yoğun, lütfen birkaç saniye sonra tekrar deneyin."
                        if lang == "tr"
                        else "Gemini is currently busy, please try again in a few seconds.")
            raise RuntimeError(f"Gemini LLM Hatası: {err}") from e

    # Buraya ulaşılmamalı ama güvenlik için:
    raise RuntimeError(f"Gemini LLM Hatası: {last_err}") from last_err


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
