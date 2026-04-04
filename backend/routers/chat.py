import re
import sys
import time
import traceback
import json
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from config import settings
from services.llm_service import generate_chat_response, generate_chat_response_stream
from services.tts_service import generate_tts
from services.semantic_cache_service import semantic_cache
from services.tools import validate_seat_selection, validate_phone_number, validate_email_address

router = APIRouter()


class ChatRequest(BaseModel):
    text: str
    lang: Optional[str] = settings.DEFAULT_LANG
    history: List[Dict[str, str]] = []


# ─────────────────────────────────────────────
# Deterministic shortcut validators
# ─────────────────────────────────────────────

def _last_assistant_text(history: List[Dict[str, str]]) -> str:
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            return str(msg.get("content", ""))
    return ""


def _try_seat_validation(text: str, history: List[Dict[str, str]]) -> Optional[str]:
    user_text = (text or "").strip()
    if not user_text:
        return None

    available_seats: Optional[str] = None
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            m = re.search(
                r"(?:Boş koltuklar|Uygun koltuklar|Boş olan şu koltuklardan birini seçin):\s*([0-9,\s]+)",
                str(msg.get("content", "")),
                flags=re.IGNORECASE,
            )
            if m:
                available_seats = m.group(1).strip()
                break

    if not available_seats:
        return None

    # Only intercept short seat-like inputs
    if not re.fullmatch(r"[0-9]{1,2}|[a-zA-ZçğıöşüÇĞİÖŞÜ\s]{2,12}", user_text):
        return None

    return validate_seat_selection(user_text, available_seats)


def _try_phone_validation(text: str, history: List[Dict[str, str]]) -> Optional[str]:
    user_text = (text or "").strip()
    if not user_text:
        return None

    last = _last_assistant_text(history).lower()
    if not any(kw in last for kw in ["telefon", "cep num", "05xx"]):
        return None

    clean = re.sub(r"[^0-9]", "", user_text)
    if len(clean) < 10 or len(clean) > 13:
        return None
    if len(clean) == 10 and not clean.startswith("5"):
        return None
    if len(clean) == 11 and not (clean.startswith("0") or clean.startswith("9")):
        return None

    print(f"[DIRECT PHONE] {user_text!r} → digits={clean!r}")
    return validate_phone_number(user_text)


def _try_email_validation(text: str, history: List[Dict[str, str]]) -> Optional[str]:
    user_text = (text or "").strip()
    if not user_text:
        return None

    last = _last_assistant_text(history).lower()
    if not any(kw in last for kw in ["e-posta", "eposta", "email", "mail adres"]):
        return None

    has_at = "@" in user_text
    has_voice_at = any(w in user_text.lower().split() for w in ["at", "et"])
    has_domain = any(d in user_text.lower() for d in ["gmail", "mail", "hotmail", "yahoo", "outlook", "nokta", "com"])

    if not (has_at or has_voice_at or has_domain):
        return None

    print(f"[DIRECT EMAIL] {user_text!r}")
    return validate_email_address(user_text)


def _latest_sefer_id(history: List[Dict[str, str]]) -> Optional[str]:
    for msg in reversed(history or []):
        m = re.search(r"(?:Sefer|Trip)[_]?ID[:\s]*(\d+)", msg.get("content", ""), flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _build_system_injection(
    lang: str,
    seat_result: Optional[str],
    phone_result: Optional[str],
    email_result: Optional[str],
    history: List[Dict[str, str]],
) -> str:
    """Compose system injection string from direct validation results."""
    if email_result:
        sefer_id = _latest_sefer_id(history)
        if lang == "en":
            base = f"[SYSTEM INFORMATION: Tool result: {email_result}. Provide a clear SUMMARY and ask 'Do you confirm?'. Do NOT book yet!"
            suffix = f" Use Trip ID={sefer_id} for Step 9.]" if sefer_id else "]"
        else:
            base = f"[SİSTEM BİLGİSİ: Araç sonucu: {email_result}. Kullanıcıya tüm bilgilerin ÖZETİNİ sun ve 'Onaylıyor musunuz?' diye sor. Rezervasyon yapma!"
            suffix = f" Onay sonrası sefer_id={sefer_id} kullanacaksın.]" if sefer_id else "]"
        return f" {base}{suffix}"

    for result in (phone_result, seat_result):
        if result:
            if lang == "en":
                return f" [SYSTEM INFORMATION: Tool result: {result}]"
            return f" [SİSTEM BİLGİSİ: Araç sonucu: {result}]"

    return ""


def _inject_ground_truth(text: str, history: List[Dict[str, str]]) -> str:
    """
    Extract confirmed booking data from history and inject as ABSOLUTE SYSTEM TRUTH
    to prevent LLM hallucinating IDs, routes, dates or seats.
    """
    g_id = g_route = g_date = g_seat = None

    for msg in history:
        content = str(msg.get("content", ""))

        m = re.search(r"(?:Sefer|Trip|ID)[:=\s]*(\d+)", content, flags=re.IGNORECASE)
        if m:
            g_id = m.group(1)

        m = re.search(
            r"(?:from|kalkış)?\s*([a-zğüşöçı\s]{3,20}?)\s*(?:-|->|to|varış)\s*([a-zğüşöçı\s]{3,20})",
            content, flags=re.IGNORECASE,
        )
        if m:
            c1, c2 = m.group(1).strip().capitalize(), m.group(2).strip().capitalize()
            if c1 and c2:
                g_route = f"{c1} to {c2}"

        m = re.search(r"(\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})", content)
        if m:
            g_date = m.group(1)
        else:
            m = re.search(
                r"\b(?:Ocak|Şubat|Mart|Nisan|Mayıs|Haziran|Temmuz|Ağustos|Eylül|Ekim|Kasım|Aralık"
                r"|January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s*\d{1,2}(?:st|nd|rd|th)?\b",
                content, flags=re.IGNORECASE,
            )
            if m:
                g_date = m.group(0)

        m = re.search(r"(?:Koltuk|Seat)[:\s]*(\d+)", content, flags=re.IGNORECASE)
        if m:
            g_seat = m.group(1)

    truth_parts = []
    if g_id:    truth_parts.append(f"STRICT_ID={g_id}")
    if g_route: truth_parts.append(f"STRICT_ROUTE={g_route}")
    if g_date:  truth_parts.append(f"STRICT_DATE={g_date}")
    if g_seat:  truth_parts.append(f"STRICT_SEAT={g_seat}")

    if truth_parts:
        injection = f" [ABSOLUTE SYSTEM TRUTH (NEVER HALLUCINATE): {' | '.join(truth_parts)}]"
        if injection not in text:
            return text + injection

    return text


def _preprocess_request(
    text: str,
    history: List[Dict[str, str]],
    lang: str,
) -> str:
    """Run deterministic validators and build the final text for LLM."""
    seat_result  = _try_seat_validation(text, history)
    phone_result = _try_phone_validation(text, history)
    email_result = _try_email_validation(text, history)

    injection = _build_system_injection(lang, seat_result, phone_result, email_result, history)
    processed = text + injection
    processed = _inject_ground_truth(processed, history)
    return processed


# ─────────────────────────────────────────────
# REST endpoint
# ─────────────────────────────────────────────

@router.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        t0 = time.perf_counter()
        lang = request.lang or settings.DEFAULT_LANG
        processed_text = _preprocess_request(request.text, request.history, lang)

        cached = semantic_cache.search(processed_text)
        if cached:
            print(f"[REST] Cache HIT — {time.perf_counter()-t0:.3f}s")
            return {"text": cached["text"], "audio": cached["audio"], "emotion": cached["emotion"]}

        response_text = await generate_chat_response(processed_text, request.history, lang)
        t_llm = time.perf_counter()

        audio_base64 = await generate_tts(response_text, lang)
        t_tts = time.perf_counter()

        print(f"[REST] LLM={t_llm-t0:.3f}s TTS={t_tts-t_llm:.3f}s TOTAL={t_tts-t0:.3f}s")
        return {"text": response_text, "audio": audio_base64, "emotion": "neutral"}

    except Exception as e:
        tb = traceback.format_exc()
        msg = str(e).strip() or repr(e)
        sys.stderr.write(f"\n[CHAT 500] {msg}\n{tb}\n")
        sys.stderr.flush()
        raise HTTPException(status_code=500, detail={"error": "Chat işlemi başarısız.", "message": msg})


# ─────────────────────────────────────────────
# WebSocket endpoint
# ─────────────────────────────────────────────

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                req = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[WS] Non-JSON received: {raw[:80]}")
                continue

            text    = req.get("text", "")
            history = req.get("history", [])
            lang    = req.get("lang") or settings.DEFAULT_LANG

            t0 = time.perf_counter()
            processed_text = _preprocess_request(text, history, lang)

            cached = semantic_cache.search(processed_text)
            if cached:
                await websocket.send_json({"type": "text",    "content": cached["text"]})
                await websocket.send_json({"type": "audio",   "content": cached["audio"]})
                await websocket.send_json({"type": "emotion", "content": cached["emotion"]})
                await websocket.send_json({"type": "done"})
                print(f"[WS] Cache HIT — {time.perf_counter()-t0:.3f}s")
                continue

            try:
                full_response = ""
                t_llm = time.perf_counter()
                async for chunk in generate_chat_response_stream(processed_text, history, lang):
                    full_response += chunk
                    await websocket.send_json({"type": "text", "content": chunk})
                print(f"[WS] LLM={time.perf_counter()-t_llm:.3f}s")

                t_tts = time.perf_counter()
                clean_text = re.sub(r'<\|ACT:.*?\|>', '', full_response, flags=re.DOTALL).strip()
                audio_base64 = await generate_tts(clean_text, lang)
                print(f"[WS] TTS={time.perf_counter()-t_tts:.3f}s TOTAL={time.perf_counter()-t0:.3f}s")

                await websocket.send_json({"type": "audio",   "content": audio_base64})
                await websocket.send_json({"type": "emotion", "content": "neutral"})
                await websocket.send_json({"type": "done"})

            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        pass
