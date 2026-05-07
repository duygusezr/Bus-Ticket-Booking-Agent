import logging
import asyncio
import inspect
import json
import re
from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any

from openai import AsyncOpenAI

from config import settings
from services.memory_service import get_current_summary, update_memory
from services.session_state import get_session, update_session_from_tool_result, build_state_block
from services.types import ToolResult

logger = logging.getLogger(__name__)

OPENAI_MODEL = settings.OPENAI_CHAT_MODEL

# Singleton client — modül yüklendiğinde bir kez oluşturulur, tüm isteklerde paylaşılır.
_OPENAI_CLIENT = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


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


def _python_type_to_json_schema(annotation: Any) -> dict:
    """Python tip notasyonunu basit JSON Schema'ya çevir."""
    import typing
    origin = getattr(annotation, "__origin__", None)
    if annotation is str or annotation == "str":
        return {"type": "string"}
    if annotation is int or annotation == "int":
        return {"type": "integer"}
    if annotation is float or annotation == "float":
        return {"type": "number"}
    if annotation is bool or annotation == "bool":
        return {"type": "boolean"}
    if origin is list:
        args = getattr(annotation, "__args__", (str,))
        return {"type": "array", "items": _python_type_to_json_schema(args[0])}
    return {"type": "string"}  # fallback


def _func_to_openai_tool(fn) -> dict:
    """Python fonksiyonunu OpenAI tool tanımına dönüştür."""
    sig = inspect.signature(fn)
    doc = (fn.__doc__ or "").strip().split("\n")[0]
    properties: dict = {}
    required: list = []
    hints = fn.__annotations__ if hasattr(fn, "__annotations__") else {}

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        annotation = hints.get(name, str)
        # Optional[X] kontrolü
        import typing
        origin = getattr(annotation, "__origin__", None)
        args = getattr(annotation, "__args__", None)
        is_optional = origin is typing.Union and type(None) in args if args else False
        if is_optional:
            inner = next(a for a in args if a is not type(None))
            schema = _python_type_to_json_schema(inner)
        else:
            schema = _python_type_to_json_schema(annotation)

        properties[name] = schema
        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(name)

    return {
        "type": "function",
        "function": {
            "name": fn.__name__,
            "description": doc,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _build_openai_messages(system_prompt: str, history: List[Dict[str, str]], user_text: str) -> list:
    """OpenAI mesaj listesi oluştur."""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        role = "user" if msg["role"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["content"]})
    messages.append({"role": "user", "content": user_text})
    return messages


def _build_system_prompt(lang: str, summary: str, session_id: str) -> str:
    from services.session_state import get_session, build_state_block
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

    # Structured state memory: doğrulanmış veriler her zaman system prompt içinde
    session = get_session(session_id)
    state_block = build_state_block(session, lang)
    if state_block:
        prompt += state_block

    return prompt


# ── İç enjeksiyon kalıplarını LLM çıktısından temizle ─────────
_INTERNAL_BLOCK_RE = re.compile(
    r'\[(?:ABSOLUTE SYSTEM TRUTH|SİSTEM BİLGİSİ|SYSTEM INFORMATION|SİSTEM BİLGİSİ)'
    r'[^\]]*\]',
    re.IGNORECASE | re.DOTALL,
)

def _sanitize_response(text: str) -> str:
    """LLM yanıtından iç enjeksiyon bloklarını sil."""
    cleaned = _INTERNAL_BLOCK_RE.sub('', text)
    # Birden fazla boşluk / satır başını düzelt
    cleaned = re.sub(r'  +', ' ', cleaned)
    return cleaned.strip()


async def generate_chat_response(
    text: str,
    history: List[Dict[str, str]],
    lang: str,
    session_id: str = "default",
) -> str:
    """Manuel araç-çağrı döngüsüyle OpenAI yanıtı üret."""
    MAX_RETRIES = 3
    last_err: Exception | None = None

    for attempt in range(MAX_RETRIES):
        try:
            tools_map = _get_tools()
            openai_tools = [_func_to_openai_tool(fn) for fn in tools_map.values()]

            summary = get_current_summary(session_id)
            system_prompt = _build_system_prompt(lang, summary, session_id)

            messages = _build_openai_messages(system_prompt, history, text)

            # Araç çağrı döngüsü (sonsuz döngüyü önlemek için max 10 iterasyon)
            for _ in range(10):
                response = await _OPENAI_CLIENT.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=messages,
                    tools=openai_tools,
                    tool_choice="auto",
                    temperature=0.0,
                )

                msg = response.choices[0].message

                # Araç çağrısı yok — son yanıt
                if not msg.tool_calls:
                    result_text = _sanitize_response(msg.content or "")
                    asyncio.create_task(update_memory(text, result_text, session_id))
                    return result_text

                # Asistan mesajını konuşma geçmişine ekle
                messages.append(msg)

                # Her araç çağrısını işle
                for tool_call in msg.tool_calls:
                    fn_name: str = tool_call.function.name
                    try:
                        fn_args: dict[str, Any] = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        fn_args = {}

                    logger.info("Araç çağrısı: %s(%s)", fn_name, fn_args)

                    if fn_name not in tools_map:
                        logger.warning("Bilinmeyen araç: %s", fn_name)
                        tool_result_msg = "Hata: Araç bulunamadı."
                    else:
                        try:
                            result: ToolResult = (
                                await tools_map[fn_name](**fn_args)
                                if asyncio.iscoroutinefunction(tools_map[fn_name])
                                else tools_map[fn_name](**fn_args)
                            )
                        except Exception as tool_err:
                            logger.exception("Araç çağrısı hatası [%s]: %s", fn_name, tool_err)
                            result = ToolResult(message=f"Hata: {tool_err}", success=False)

                        logger.info("Araç sonucu [%s]: %s", fn_name, result.message)

                        # Oturum durumunu araç sonucuna göre güncelle
                        update_session_from_tool_result(
                            session_id=session_id,
                            tool_name=fn_name,
                            tool_args=fn_args,
                            tool_result=result,
                        )
                        tool_result_msg = result.message

                    # Araç sonucunu mesajlara ekle
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result_msg,
                    })

            # Max iterasyon aşıldı — son gelen içeriği döndür
            result_text = _sanitize_response(msg.content or "")
            asyncio.create_task(update_memory(text, result_text, session_id))
            return result_text

        except Exception as e:
            last_err = e
            err = str(e)
            is_transient = "503" in err or "429" in err or "quota" in err.lower() or "unavailable" in err.lower() or "overloaded" in err.lower()

            if is_transient and attempt < MAX_RETRIES - 1:
                wait = (attempt + 1) * 1.5          # 1.5s, 3s
                logger.warning("OpenAI geçici hata (deneme %d/%d): %s — %.1fs sonra yeniden deneniyor",
                               attempt + 1, MAX_RETRIES, err[:120], wait)
                await asyncio.sleep(wait)
                continue

            logger.error("LLM hatası: %s", err)
            if is_transient:
                return ("Sunucu şu an yoğun, lütfen birkaç saniye sonra tekrar deneyin."
                        if lang == "tr"
                        else "The server is currently busy, please try again in a few seconds.")
            raise RuntimeError(f"OpenAI LLM Hatası: {err}") from e

    # Buraya ulaşılmamalı ama güvenlik için:
    raise RuntimeError(f"OpenAI LLM Hatası: {last_err}") from last_err


async def generate_chat_response_stream(
    text: str,
    history: List[Dict[str, str]],
    lang: str,
    session_id: str = "default",
) -> AsyncGenerator[str, None]:
    """
    Streaming sarmalayıcı.

    Not: Araç çağrı döngüsü önce tam olarak tamamlanır, ardından metin
    tek seferde yield edilir.
    """
    try:
        final_text = await generate_chat_response(text, history, lang, session_id)
        yield final_text
    except Exception as e:
        yield f"Hata: {e}"
