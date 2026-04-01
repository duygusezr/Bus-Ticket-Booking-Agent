import re
import sys
import traceback
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Optional
import json

from services.llm_service import generate_chat_response, generate_chat_response_stream
from services.tts_service import generate_tts
# from services.emotion_service_v2 import analyze_sentiment_v2  # Removed for performance
from services.semantic_cache_service import semantic_cache
from config import settings
from services.tools import validate_seat_selection, validate_phone_number, validate_email_address

router = APIRouter()

class ChatRequest(BaseModel):
    text: str
    lang: Optional[str] = settings.DEFAULT_LANG
    history: List[Dict[str, str]] = []


def _extract_last_assistant_text(history: List[Dict[str, str]]) -> str:
    """Return the latest assistant message from history."""
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            return str(msg.get("content", "") or "")
    return ""

def _inject_ground_truth_context(text: str, history: List[Dict[str, str]]) -> str:
    """
    Scans entire conversation history for technical travel data (Route, Date, Sefer ID, Seat) 
    and injects it as a hidden [GROUND TRUTH] block to ensure the LLM summary is accurate.
    """
    g_id = None
    g_route = None
    g_date = None
    g_seat = None

    for m in history:
        content = str(m.get("content", ""))
        # 1. Sefer ID
        id_match = re.search(r"(?:Sefer|Trip)\s*(?:No|ID)[:=\s]*(\d+)", content, flags=re.IGNORECASE)
        if id_match: g_id = id_match.group(1)

        # 2. Route (Nereden Nereye)
        route_match = re.search(r"(?:Güzergah|Route|Trip)[:\s]*([a-zA-ZçğıöşüÇĞİÖŞÜ\s]+->[a-zA-ZçğıöşüÇĞİÖŞÜ\s]+|[a-zA-ZçğıöşüÇĞİÖŞÜ\s]+to[a-zA-ZçğıöşüÇĞİÖŞÜ\s]+)", content, flags=re.IGNORECASE)
        if route_match: g_route = route_match.group(1).strip()

        # 3. Date
        date_match = re.search(r"(?:Tarih|Date)[:\s]*(\d{1,2}[\.\-/]\d{1,2}[\.\-/]\d{4}|\d{4}-\d{2}-\d{2})", content, flags=re.IGNORECASE)
        if date_match: g_date = date_match.group(1)

        # 4. Seat
        seat_match = re.search(r"(?:Koltuk|Seat)[:\s]*(\d+)", content, flags=re.IGNORECASE)
        if seat_match: g_seat = seat_match.group(1)

    # 5. Build Ground Truth Block
    truth = []
    if g_id: truth.append(f"Sefer ID={g_id}")
    if g_route: truth.append(f"Route={g_route}")
    if g_date: truth.append(f"Date={g_date}")
    if g_seat: truth.append(f"Seat={g_seat}")

    if truth:
        truth_str = ", ".join(truth)
        if f"[GROUND TRUTH: {truth_str}]" not in text:
            return text + f" [GROUND TRUTH: {truth_str}]"
    return text


def _try_direct_seat_validation(text: str, history: List[Dict[str, str]]) -> Optional[str]:
    """
    Deterministic seat validation shortcut.
    If user sends a direct seat input right after a message containing
    'Boş koltuklar: ...', validate with tool function directly.
    """
    user_text = (text or "").strip()
    if not user_text:
        return None

    # Geriye dönük son 3-4 mesajda 'Boş koltuklar:' veya 'Uygun koltuklar:' ara
    available_seats = None
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            content = str(msg.get("content", ""))
            seat_list_match = re.search(r"(?:Boş koltuklar|Uygun koltuklar|Boş olan şu koltuklardan birini seçin):\s*([0-9,\s]+)", content, flags=re.IGNORECASE)
            if seat_list_match:
                available_seats = seat_list_match.group(1).strip()
                break

    if not available_seats:
        return None

    # Only short seat-like inputs should use this guardrail path.
    # Accept "5", "12", "beş", "on iki" etc. and avoid hijacking long messages.
    if not re.fullmatch(r"[0-9]{1,2}|[a-zA-ZçğıöşüÇĞİÖŞÜ\s]{2,12}", user_text):
        return None

    return validate_seat_selection(user_text, available_seats)


def _try_direct_phone_validation(text: str, history: List[Dict[str, str]]) -> Optional[str]:
    """
    Deterministic phone validation shortcut.
    Bot son mesajında telefon istiyorsa, LLM'yi beklemeden doğrudan doğrula.
    """
    user_text = (text or "").strip()
    if not user_text:
        return None

    last_assistant = _extract_last_assistant_text(history)
    if not last_assistant:
        return None

    last_lower = last_assistant.lower()

    # Bot telefon sordu mu?
    phone_keywords = ["telefon", "cep num", "05xx"]
    if not any(kw in last_lower for kw in phone_keywords):
        return None

    # Kullanıcı girişi telefon numarasına benziyor mu?
    clean = re.sub(r"[^0-9]", "", user_text)
    
    # Telefon numarası:
    # 10 haneli ise '5' ile başlamalı
    # 11 haneli ise '0' ile başlamalı
    # 12+ hane ise (ülke kodlu) '+90' vb.
    if len(clean) < 10 or len(clean) > 13:
        return None
        
    if len(clean) == 10 and not clean.startswith("5"):
        return None
    if len(clean) == 11 and not (clean.startswith("0") or clean.startswith("9")):
        return None

    print(f"[DIRECT PHONE] Input: '{user_text}' -> Digits: '{clean}'")
    return validate_phone_number(user_text)


def _try_direct_email_validation(text: str, history: List[Dict[str, str]]) -> Optional[str]:
    """
    Deterministic email validation shortcut.
    Bot son mesajında email istiyorsa, LLM'yi beklemeden doğrudan doğrula.
    """
    user_text = (text or "").strip()
    if not user_text:
        return None

    last_assistant = _extract_last_assistant_text(history)
    if not last_assistant:
        return None

    # Bot email sordu mu?
    email_keywords = ["e-posta", "eposta", "email", "mail adres"]
    last_lower = last_assistant.lower()
    if not any(kw.lower() in last_lower for kw in email_keywords):
        return None

    # Kullanıcı girişi email'e benziyor mu? (@ varsa veya sesli email kalıpları)
    has_at = "@" in user_text
    has_voice_at = any(w in user_text.lower().split() for w in ["at", "et"])
    has_domain = any(d in user_text.lower() for d in ["gmail", "mail", "hotmail", "yahoo", "outlook", "nokta", "com"])

    if not (has_at or has_voice_at or has_domain):
        return None

    print(f"[DIRECT EMAIL] Input: '{user_text}'")
    return validate_email_address(user_text)

@router.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """REST tabanlı (streaming olmayan) tam sohbet endpoint'i."""
    try:
        import time
        t_start = time.perf_counter()
        lang = request.lang or settings.DEFAULT_LANG

        system_injection = ""
        direct_seat_response = _try_direct_seat_validation(request.text, request.history)
        if direct_seat_response:
            if lang == "en":
                system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_seat_response}]"
            else:
                system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_seat_response}]"

        direct_phone_response = _try_direct_phone_validation(request.text, request.history)
        if direct_phone_response:
            if lang == "en":
                system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_phone_response}]"
            else:
                system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_phone_response}]"

        direct_email_response = _try_direct_email_validation(request.text, request.history)
        if direct_email_response:
            latest_sefer_id = None
            for m in request.history:
                match = re.search(r"(?:Sefer|Trip)[_]?ID:\s*(\d+)", m.get("content", ""), flags=re.IGNORECASE)
                if match:
                    latest_sefer_id = match.group(1)
                    
            if lang == "en":
                if latest_sefer_id:
                    system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_email_response}. Please provide a clear SUMMARY of all info (Route, etc.) to the user and ask 'Do you confirm?'. Do NOT use the reservation tool at this step! Use Trip ID={latest_sefer_id} for the final Step 9.]"
                else:
                    system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_email_response}. Please provide a SUMMARY and ask for confirmation. Do NOT book yet!]"
            else:
                if latest_sefer_id:
                    system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_email_response}. Lütfen şimdi kullanıcıya tüm bilgilerin (Güzergah, vb.) net bir ÖZETİNİ sun ve 'Onaylıyor musunuz?' diye sor. Asla bu adımda rezervasyon aracı kullanma! Onay sonrasına hazırlık için sefer_id={latest_sefer_id} değerini kullanacağını unutma.]"
                else:
                    system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_email_response}. Lütfen şimdi kullanıcıya bilgilerin ÖZETİNİ sun ve 'Onaylıyor musunuz?' diye sor. Asla bu adımda rezervasyon yapma!]"

        # LLM'in bu sonucu görüp bir sonraki adımı otomatik sorması için metne ekle
        processed_text = request.text + system_injection
        processed_text = _inject_ground_truth_context(processed_text, request.history)

        cached_match = semantic_cache.search(processed_text)
        if cached_match:
            print(f"--- [REST CHAT SEMANTIC HIT] --- TOTAL: {time.perf_counter() - t_start:.3f}s")
            return {
                "text": cached_match["text"],
                "audio": cached_match["audio"],
                "emotion": cached_match["emotion"]
            }

        # Gemini ile yanıt üret (tool calling + doğal dil tek adımda)
        response_text = await generate_chat_response(processed_text, request.history, lang)
        t_llm = time.perf_counter()

        audio_base64 = await generate_tts(response_text, lang)
        t_tts = time.perf_counter()

        # [OPTIMIZATION] Skip or background emotion in REST to avoid blocking
        emotion = "neutral" 
        
        # Optionally add to cache in background (if we ever re-enable cache)
        # semantic_cache.add(processed_text, response_text, audio_base64, emotion)

        print(f"--- [REST LATENCY] --- LLM: {t_llm-t_start:.3f}s | TTS: {t_tts-t_llm:.3f}s | TOTAL: {time.perf_counter()-t_start:.3f}s")
        return {"text": response_text, "audio": audio_base64, "emotion": emotion}

    except Exception as e:
        tb = traceback.format_exc()
        msg = str(e).strip() or repr(e)
        sys.stderr.write("\n[CHAT 500] %s\n%s\n" % (msg, tb))
        sys.stderr.flush()
        raise HTTPException(status_code=500, detail={"error": "Chat işlemi başarısız.", "message": msg})


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket tabanlı streaming sohbet endpoint'i."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                request_data = json.loads(data)
            except json.JSONDecodeError:
                # Gelen veri JSON değilse yoksay (örn. ping veya HMR)
                print(f"[WS] Beklenmeyen veri alındı (JSON değil): {data}")
                continue

            text = request_data.get("text", "")
            history = request_data.get("history", [])
            lang = request_data.get("lang") or settings.DEFAULT_LANG

            import time
            t_ws_start = time.perf_counter()

            system_injection = ""
            direct_seat_response = _try_direct_seat_validation(text, history)
            if direct_seat_response:
                if lang == "en":
                    system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_seat_response}]"
                else:
                    system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_seat_response}]"

            direct_phone_response = _try_direct_phone_validation(text, history)
            if direct_phone_response:
                if lang == "en":
                    system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_phone_response}]"
                else:
                    system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_phone_response}]"

            direct_email_response = _try_direct_email_validation(text, history)
            if direct_email_response:
                latest_sefer_id = None
                for m in history:
                    match = re.search(r"(?:Sefer|Trip)[_]?ID:\s*(\d+)", m.get("content", ""), flags=re.IGNORECASE)
                    if match:
                        latest_sefer_id = match.group(1)
                
                if lang == "en":
                    if latest_sefer_id:
                        system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_email_response}. Please provide a clear SUMMARY of all info (Route, etc.) to the user and ask 'Do you confirm?'. Do NOT use the reservation tool at this step! Use Trip ID={latest_sefer_id} for the final Step 9.]"
                    else:
                        system_injection = f" [SYSTEM INFORMATION: Tool result: {direct_email_response}. Please provide a SUMMARY and ask for confirmation. Do NOT book yet!]"
                else:
                    if latest_sefer_id:
                        system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_email_response}. Lütfen şimdi kullanıcıya tüm bilgilerin (Güzergah, vb.) net bir ÖZETİNİ sun ve 'Onaylıyor musunuz?' diye sor. Asla bu adımda rezervasyon aracı kullanma! Onay sonrasına hazırlık için sefer_id={latest_sefer_id} değerini kullanacağını unutma.]"
                    else:
                        system_injection = f" [SİSTEM BİLGİSİ: Araç sonucu: {direct_email_response}. Lütfen şimdi kullanıcıya bilgilerin ÖZETİNİ sun ve 'Onaylıyor musunuz?' diye sor. Asla bu adımda rezervasyon yapma!]"

            processed_text = text + system_injection
            processed_text = _inject_ground_truth_context(processed_text, history)

            # 0. Semantic Cache
            cached_ws_match = semantic_cache.search(processed_text)
            if cached_ws_match:
                await websocket.send_json({"type": "text", "content": cached_ws_match["text"]})
                await websocket.send_json({"type": "audio", "content": cached_ws_match["audio"]})
                await websocket.send_json({"type": "emotion", "content": cached_ws_match["emotion"]})
                await websocket.send_json({"type": "done"})
                print(f"[WS SEMANTIC HIT] Time: {time.perf_counter() - t_ws_start:.3f}s")
                continue

            # 1. Duygu analizi kaldırıldı (Performans için)
            # await websocket.send_json({"type": "emotion", "content": "neutral"})

            try:
                # --- GEMINI TEK ADIM: Logic + Tool Calling + Doğal Dil ---
                t_llm_start = time.perf_counter()
                
                full_response = ""
                async for chunk in generate_chat_response_stream(processed_text, history, lang):
                    full_response += chunk
                    await websocket.send_json({"type": "text", "content": chunk})
                
                t_llm_end = time.perf_counter()
                print(f"[WS] Gemini Response Latency: {t_llm_end - t_llm_start:.3f}s")

                # TTS
                t_tts_start = time.perf_counter()
                clean_text = re.sub(r'<\|ACT:.*?\|>', '', full_response, flags=re.DOTALL).strip()
                audio_base64 = await generate_tts(clean_text, lang)
                t_tts_end = time.perf_counter()
                print(f"[WS] TTS Latency: {t_tts_end - t_tts_start:.3f}s")

                await websocket.send_json({"type": "audio", "content": audio_base64})
                await websocket.send_json({"type": "emotion", "content": "neutral"})
                await websocket.send_json({"type": "done"})

            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        pass
