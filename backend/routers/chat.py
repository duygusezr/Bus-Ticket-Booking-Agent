import time
import logging
import json
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from config import settings
from services.llm_service import generate_chat_response, generate_chat_response_stream
from services.tts_service import generate_tts
from services.preprocessing_service import preprocess_request

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    text: str
    lang: Optional[str] = settings.DEFAULT_LANG
    history: List[Dict[str, str]] = []
    session_id: str = "default"


# ─────────────────────────────────────────────
# REST endpoint
# ─────────────────────────────────────────────

@router.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        t0 = time.perf_counter()
        lang = request.lang or settings.DEFAULT_LANG
        session_id = request.session_id

        processed_text = preprocess_request(request.text, request.history, lang, session_id)

        response_text = await generate_chat_response(processed_text, request.history, lang, session_id)
        t_llm = time.perf_counter()

        audio_base64 = await generate_tts(response_text, lang)
        t_tts = time.perf_counter()

        logger.info(
            "REST LLM=%.3fs TTS=%.3fs TOTAL=%.3fs",
            t_llm - t0, t_tts - t_llm, t_tts - t0,
        )
        return {"text": response_text, "audio": audio_base64, "emotion": "neutral"}

    except Exception as e:
        logger.exception("Chat endpoint hatası")
        raise HTTPException(
            status_code=500,
            detail={"error": "Chat işlemi başarısız.", "message": str(e).strip() or repr(e)},
        )


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
                logger.warning("WS geçersiz JSON: %s", raw[:80])
                continue

            text = req.get("text", "")
            history = req.get("history", [])
            lang = req.get("lang") or settings.DEFAULT_LANG
            session_id = req.get("session_id", "default")
            voice = req.get("voice", "default")  # "male" | "female" | "default"

            t0 = time.perf_counter()
            processed_text = preprocess_request(text, history, lang, session_id)

            try:
                full_response = ""
                t_llm = time.perf_counter()
                async for chunk in generate_chat_response_stream(processed_text, history, lang, session_id):
                    full_response += chunk
                    await websocket.send_json({"type": "text", "content": chunk})
                logger.info("WS LLM=%.3fs", time.perf_counter() - t_llm)

                t_tts = time.perf_counter()
                audio_base64 = await generate_tts(full_response.strip(), lang, voice)
                logger.info(
                    "WS TTS=%.3fs TOTAL=%.3fs",
                    time.perf_counter() - t_tts,
                    time.perf_counter() - t0,
                )

                await websocket.send_json({"type": "audio", "content": audio_base64})
                await websocket.send_json({"type": "emotion", "content": "neutral"})

                # Koltuk haritası popup tetikleyici
                from services.session_state import get_session
                sess = get_session(session_id)
                if sess.seat_map_pending and sess.available_seats:
                    await websocket.send_json({
                        "type": "seat_map",
                        "available_seats": sess.available_seats,
                        "occupied_seats": sess.occupied_seats or "",
                    })
                    sess.seat_map_pending = False

                await websocket.send_json({"type": "done"})

            except Exception as e:
                logger.exception("WS işlem hatası")
                await websocket.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        pass
