import asyncio
import time
import google.genai as genai
from google.genai import types
from config import settings
from typing import Dict, List

_sessions: Dict[str, dict] = {}
SUMMARIZE_EVERY = 5  # Re-summarize more frequently in background


def _get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"summary": "", "buffer": [], "total": 0}
    return _sessions[session_id]


def get_current_summary(session_id: str = "default") -> str:
    return _get_session(session_id)["summary"]


async def update_memory(user_input: str, ai_response: str, session_id: str = "default"):
    """
    Hafızayı günceller. Karakter sayısı çok az ise özetleme tetiklemez.
    """
    session = _get_session(session_id)
    session["buffer"].append({"user": user_input, "ai": ai_response})
    session["total"] += 1
    
    # 5 karakterden kısa girişi skip et (örn: "evet", "12")
    if len(user_input.strip()) < 5:
        return

    if len(session["buffer"]) >= SUMMARIZE_EVERY:
        # Arka planda çalıştır (Non-blocking)
        asyncio.create_task(_summarize(session, session_id))


async def _summarize(session: dict, session_id: str):
    """
    Gemini ile arka planda (asenkron) özet üretir.
    """
    t_mem_start = time.perf_counter()
    try:
        api_key = settings.GOOGLE_API_KEY
        client = genai.Client(api_key=api_key)
        
        buffer_text = "\n".join(
            f"Kullanıcı: {m['user']}\nELA: {m['ai']}" for m in session["buffer"]
        )
        prev = f"Önceki özet:\n{session['summary']}\n\n" if session["summary"] else ""
        
        # Dil tespiti ve yönerge
        is_en = any(word in buffer_text.lower() for word in ["hello", "i want to", "ticket", "route", "trip"])
        lang_instr = "English" if is_en else "Turkish"
        
        prompt = (
            f"{prev}New messages:\n{buffer_text}\n\n"
            f"Summarize the conversation above in 3-5 sentences in {lang_instr}. "
            "IMPORTANT: Preserve exact technical details: cities, dates, Sefer IDs, Seat numbers. "
            "NEVER use placeholder names or example cities (like Istanbul-Ankara) if they were not in the actual conversation. "
            "Data integrity is CRITICAL. If a specific Sefer ID was mentioned, it MUST remain unchanged."
        )
        
        # Asenkron çağrı (aio)
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
        )
        
        text = response.text
        if text:
            session["summary"] = text.strip()
            session["buffer"] = []
            
        t_mem_end = time.perf_counter()
        print(f"[MEMORY] Özet güncellendi ({session_id}) | Latency: {t_mem_end - t_mem_start:.3f}s | Length: {len(session['summary'])}")
        
    except Exception as e:
        print(f"[MEMORY ERROR] Özetleme hatası: {e}")
        # Hata durumunda buffer'ı temizle ki bloklama yapmasın
        session["buffer"] = []
