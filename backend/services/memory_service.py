"""
Hafıza servisi — google.genai yeni paketi ile.
Her N mesajda bir Gemini ile özet üretir, RAM'de tutar.
"""
import google.genai as genai
from google.genai import types
from config import settings
from typing import Dict, List

_sessions: Dict[str, dict] = {}
SUMMARIZE_EVERY = 10


def _get_session(session_id: str) -> dict:
    if session_id not in _sessions:
        _sessions[session_id] = {"summary": "", "buffer": [], "total": 0}
    return _sessions[session_id]


def get_current_summary(session_id: str = "default") -> str:
    return _get_session(session_id)["summary"]


def update_memory(user_input: str, ai_response: str, session_id: str = "default"):
    session = _get_session(session_id)
    session["buffer"].append({"user": user_input, "ai": ai_response})
    session["total"] += 1
    if len(session["buffer"]) >= SUMMARIZE_EVERY:
        _summarize(session, session_id)


def _summarize(session: dict, session_id: str):
    try:
        api_key = settings.GOOGLE_API_KEY
        print(f"[MEMORY DEBUG] Summary key check: {api_key[:10]}...")
        client = genai.Client(api_key=api_key)  # rotasyon sistemini kullanır
        buffer_text = "\n".join(
            f"Kullanıcı: {m['user']}\nELA: {m['ai']}" for m in session["buffer"]
        )
        prev = f"Önceki özet:\n{session['summary']}\n\n" if session["summary"] else ""
        prompt = (
            f"{prev}Yeni konuşmalar:\n{buffer_text}\n\n"
            "Yukarıdaki konuşmayı 3-5 cümleyle Türkçe özetle. Sadece özeti yaz."
        )
        response = client.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
        )
        text = response.text
        session["summary"] = text.strip() if text else ""
        session["buffer"] = []
        print(f"[MEMORY] Özet güncellendi ({session_id}): {len(session['summary'])} karakter")
    except Exception as e:
        print(f"[MEMORY] Özetleme hatası: {e}")
        session["buffer"] = []
