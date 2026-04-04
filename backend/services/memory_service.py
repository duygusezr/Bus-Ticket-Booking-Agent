import asyncio
import logging
import time
import google.genai as genai
from config import settings
from typing import Dict, List

logger = logging.getLogger(__name__)

# Singleton istemci — llm_service ile aynı pattern, her özetlemede yeni nesne üretilmez.
_GEMINI_CLIENT = genai.Client(api_key=settings.GOOGLE_API_KEY)

_sessions: Dict[str, dict] = {}
_SUMMARIZE_EVERY = 5
_MIN_INPUT_LEN = 5


def _get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"summary": "", "buffer": [], "total": 0}
    return _sessions[session_id]


def get_current_summary(session_id: str = "default") -> str:
    return _get_session(session_id)["summary"]


async def update_memory(user_input: str, ai_response: str, session_id: str = "default") -> None:
    session = _get_session(session_id)
    session["buffer"].append({"user": user_input, "ai": ai_response})
    session["total"] += 1

    # Çok kısa girdileri atla (örn. "evet", "12") — özetlemeye değmez
    if len(user_input.strip()) < _MIN_INPUT_LEN:
        return

    if len(session["buffer"]) >= _SUMMARIZE_EVERY:
        asyncio.create_task(_summarize(session, session_id))


async def _summarize(session: dict, session_id: str) -> None:
    t0 = time.perf_counter()
    # Async boşluğundan önce buffer'ı anlık görüntüle — eş zamanlı eklemeyle yarışmayalım
    buffer_snapshot: List[dict] = session["buffer"][:]
    session["buffer"] = []

    try:
        buffer_text = "\n".join(
            f"Kullanıcı: {m['user']}\nELA: {m['ai']}" for m in buffer_snapshot
        )
        prev = f"Önceki özet:\n{session['summary']}\n\n" if session["summary"] else ""
        is_en = any(w in buffer_text.lower() for w in ("hello", "i want to", "ticket", "route", "trip"))
        lang = "English" if is_en else "Turkish"

        prompt = (
            f"{prev}New messages:\n{buffer_text}\n\n"
            f"Summarize in 3-5 sentences in {lang}. "
            "CRITICAL: Preserve exact Sefer IDs, cities, dates, seat numbers verbatim. "
            "Never substitute placeholder examples for real data."
        )

        response = await _GEMINI_CLIENT.aio.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
        )
        if response.text:
            session["summary"] = response.text.strip()
            logger.info(
                "Hafıza güncellendi (%s) t=%.3fs uzunluk=%d",
                session_id,
                time.perf_counter() - t0,
                len(session["summary"]),
            )

    except Exception as e:
        logger.error("Özetleme başarısız (%s): %s", session_id, e)
        # Buffer'ı geri yükle — mesajlar kaybolmasın
        session["buffer"] = buffer_snapshot + session["buffer"]
