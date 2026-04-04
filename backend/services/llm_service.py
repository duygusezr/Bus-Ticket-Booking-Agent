from datetime import datetime
from typing import AsyncGenerator, List, Dict, Any
import asyncio
import google.genai as genai
from google.genai import types

from config import settings
from services.memory_service import get_current_summary, update_memory

GEMINI_MODEL = settings.GEMINI_CHAT_MODEL

_TOOL_NAMES = [
    "get_bus_trips", "make_reservation", "validate_seat_selection",
    "validate_tc_number", "validate_phone_number", "validate_email_address",
]


def _get_tools():
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
    prefix = f"BUGÜNÜN TARİHİ: {now.strftime('%Y-%m-%d')}\nŞU ANKİ SAAT: {now.strftime('%H:%M')}\n\n"

    if lang == "en":
        prompt = prefix + settings.SYSTEM_PROMPT_EN
        prompt += "\n\n## STRICT LANGUAGE RULE\nYou MUST reply ONLY in English."
    else:
        prompt = prefix + settings.SYSTEM_PROMPT
        prompt += "\n\n## STRICT LANGUAGE RULE\nCevaplarını SADECE Türkçe olarak vermelisin."

    if summary:
        header = "--- SUMMARY OF PREVIOUS CONVERSATION ---" if lang == "en" else "--- GEÇMİŞ KONUŞMALARIN ÖZETİ ---"
        prompt += f"\n\n{header}\n{summary}\n{'-'*37}"

    return prompt


def _has_function_call(response: Any) -> bool:
    """Safe check: does the first candidate's first part contain a function_call?"""
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
    """Generate a Gemini response with manual tool-call loop."""
    try:
        tools_map = _get_tools()
        tool_functions = list(tools_map.values())

        summary = get_current_summary(session_id)
        system_prompt = _build_system_prompt(lang, summary)

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        chat = client.aio.chats.create(
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

        # Tool-call loop (max 10 iterations to prevent infinite loops)
        for _ in range(10):
            if not _has_function_call(response):
                break

            function_responses: list[types.Part] = []
            for part in response.candidates[0].content.parts:
                fn = part.function_call
                if fn is None:
                    continue
                print(f"[LLM] Tool call: {fn.name}({dict(fn.args)})")
                if fn.name not in tools_map:
                    print(f"[LLM] Unknown tool: {fn.name}")
                    continue
                try:
                    result = tools_map[fn.name](**fn.args)
                except Exception as tool_err:
                    result = f"Hata: {tool_err}"
                print(f"[LLM] Tool result: {result}")
                function_responses.append(
                    types.Part.from_function_response(name=fn.name, response={"result": result})
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
        print(f"[LLM_ERROR] {err}")
        if "429" in err or "quota" in err.lower():
            return "Şu an API kotam doldu, biraz bekleyip tekrar dener misin?"
        raise RuntimeError(f"Gemini LLM Hatası: {err}") from e


async def generate_chat_response_stream(
    text: str,
    history: List[Dict[str, str]],
    lang: str,
    session_id: str = "default",
) -> AsyncGenerator[str, None]:
    """Streaming wrapper: resolves tool calls first, then yields the final text."""
    try:
        final_text = await generate_chat_response(text, history, lang, session_id)
        yield final_text
    except Exception as e:
        yield f"Hata: {e}"
