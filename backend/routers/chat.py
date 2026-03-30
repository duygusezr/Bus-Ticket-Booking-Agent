import re
import sys
import traceback
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict, Optional
import json

from services.llm_service import generate_chat_response, generate_chat_response_stream
from services.tts_service import generate_tts
from services.emotion_service_v2 import analyze_sentiment_v2
from services.semantic_cache_service import semantic_cache
from config import settings
from services.tools import validate_seat_selection

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


def _try_direct_seat_validation(text: str, history: List[Dict[str, str]]) -> Optional[str]:
    """
    Deterministic seat validation shortcut.
    If user sends a direct seat input right after a message containing
    'Boş koltuklar: ...', validate with tool function directly.
    """
    user_text = (text or "").strip()
    if not user_text:
        return None

    last_assistant = _extract_last_assistant_text(history)
    if not last_assistant:
        return None

    seat_list_match = re.search(r"Boş koltuklar:\s*([0-9,\s]+)", last_assistant, flags=re.IGNORECASE)
    if not seat_list_match:
        return None

    # Only short seat-like inputs should use this guardrail path.
    # Accept "5", "12", "beş", "on iki" etc. and avoid hijacking long messages.
    if not re.fullmatch(r"[0-9]{1,2}|[a-zA-ZçğıöşüÇĞİÖŞÜ\s]{2,12}", user_text):
        return None

    available_seats = seat_list_match.group(1).strip()
    return validate_seat_selection(user_text, available_seats)

@router.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """REST tabanlı (streaming olmayan) tam sohbet endpoint'i."""
    try:
        import time
        t_start = time.perf_counter()
        lang = request.lang or settings.DEFAULT_LANG

        direct_seat_response = _try_direct_seat_validation(request.text, request.history)
        if direct_seat_response:
            print(f"--- [REST DIRECT SEAT] --- TOTAL: {time.perf_counter() - t_start:.3f}s")
            return {"text": direct_seat_response, "audio": await generate_tts(direct_seat_response, lang), "emotion": "relaxed"}

        cached_match = semantic_cache.search(request.text)
        if cached_match:
            print(f"--- [REST CHAT SEMANTIC HIT] --- TOTAL: {time.perf_counter() - t_start:.3f}s")
            return {
                "text": cached_match["text"],
                "audio": cached_match["audio"],
                "emotion": cached_match["emotion"]
            }

        # Gemini ile yanıt üret (tool calling + doğal dil tek adımda)
        response_text = await generate_chat_response(request.text, request.history, lang)
        t_llm = time.perf_counter()

        audio_base64 = await generate_tts(response_text, lang)
        t_tts = time.perf_counter()

        emotion = await analyze_sentiment_v2(response_text)
        t_emo = time.perf_counter()

        semantic_cache.add(request.text, response_text, audio_base64, emotion)

        print(f"--- [REST LATENCY] --- LLM: {t_llm-t_start:.3f}s | TTS: {t_tts-t_llm:.3f}s | TOTAL: {t_emo-t_start:.3f}s")
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
            request_data = json.loads(data)

            text = request_data.get("text", "")
            history = request_data.get("history", [])
            lang = request_data.get("lang") or settings.DEFAULT_LANG

            import time
            t_ws_start = time.perf_counter()

            direct_seat_response = _try_direct_seat_validation(text, history)
            if direct_seat_response:
                await websocket.send_json({"type": "text", "content": direct_seat_response})
                audio_base64 = await generate_tts(direct_seat_response, lang)
                await websocket.send_json({"type": "audio", "content": audio_base64})
                await websocket.send_json({"type": "emotion", "content": "relaxed"})
                await websocket.send_json({"type": "done"})
                print(f"[WS DIRECT SEAT] Time: {time.perf_counter() - t_ws_start:.3f}s")
                continue

            # 0. Semantic Cache
            cached_ws_match = semantic_cache.search(text)
            if cached_ws_match:
                await websocket.send_json({"type": "text", "content": cached_ws_match["text"]})
                await websocket.send_json({"type": "audio", "content": cached_ws_match["audio"]})
                await websocket.send_json({"type": "emotion", "content": cached_ws_match["emotion"]})
                await websocket.send_json({"type": "done"})
                print(f"[WS SEMANTIC HIT] Time: {time.perf_counter() - t_ws_start:.3f}s")
                continue

            # 1. Kullanıcı duygu analizi
            user_msg_emotion = await analyze_sentiment_v2(text)
            print(f"[WS] User Emotion Latency: {time.perf_counter() - t_ws_start:.3f}s")
            await websocket.send_json({"type": "emotion", "content": user_msg_emotion})

            try:
                # --- GEMINI TEK ADIM: Logic + Tool Calling + Doğal Dil ---
                t_llm_start = time.perf_counter()
                
                full_response = ""
                async for chunk in generate_chat_response_stream(text, history, lang):
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

                # Bot duygu analizi
                t_emo_start = time.perf_counter()
                bot_msg_emotion = await analyze_sentiment_v2(full_response)
                t_emo_end = time.perf_counter()
                print(f"[WS] Bot Emotion Latency: {t_emo_end - t_emo_start:.3f}s")

                await websocket.send_json({"type": "audio", "content": audio_base64})
                await websocket.send_json({"type": "emotion", "content": bot_msg_emotion})

                semantic_cache.add(text, full_response, audio_base64, bot_msg_emotion)

                await websocket.send_json({"type": "done"})

            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        pass
