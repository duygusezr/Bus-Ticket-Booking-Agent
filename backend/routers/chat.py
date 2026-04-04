import re
import sys
import time
import logging
import traceback
import json
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from config import settings
from services.llm_service import generate_chat_response, generate_chat_response_stream
from services.tts_service import generate_tts
from services.semantic_cache_service import semantic_cache
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

        cached = semantic_cache.search(processed_text)
        if cached:
            logger.info("REST cache HIT — %.3fs", time.perf_counter() - t0)
            return {"text": cached["text"], "audio": cached["audio"], "emotion": cached["emotion"]}

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
        tb = traceback.format_exc()
        msg = str(e).strip() or repr(e)
        sys.stderr.write(f"\n[CHAT 500] {msg}\n{tb}\n")
        sys.stderr.flush()
        raise HTTPException(
            status_code=500,
            detail={"error": "Chat işlemi başarısız.", "message": msg},
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

            t0 = time.perf_counter()
            processed_text = preprocess_request(text, history, lang, session_id)

            cached = semantic_cache.search(processed_text)
            if cached:
                await websocket.send_json({"type": "text", "content": cached["text"]})
                await websocket.send_json({"type": "audio", "content": cached["audio"]})
                await websocket.send_json({"type": "emotion", "content": cached["emotion"]})
                await websocket.send_json({"type": "done"})
                logger.info("WS cache HIT — %.3fs", time.perf_counter() - t0)
                continue

            try:
                full_response = ""
                t_llm = time.perf_counter()
                async for chunk in generate_chat_response_stream(processed_text, history, lang, session_id):
                    full_response += chunk
                    await websocket.send_json({"type": "text", "content": chunk})
                logger.info("WS LLM=%.3fs", time.perf_counter() - t_llm)

                t_tts = time.perf_counter()
                clean_text = re.sub(r"<\|ACT:.*?\|>", "", full_response, flags=re.DOTALL).strip()
                audio_base64 = await generate_tts(clean_text, lang)
                logger.info(
                    "WS TTS=%.3fs TOTAL=%.3fs",
                    time.perf_counter() - t_tts,
                    time.perf_counter() - t0,
                )

                await websocket.send_json({"type": "audio", "content": audio_base64})
                await websocket.send_json({"type": "emotion", "content": "neutral"})
                await websocket.send_json({"type": "done"})

            except Exception as e:
                logger.exception("WS işlem hatası")
                await websocket.send_json({"type": "error", "content": str(e)})

    except WebSocketDisconnect:
        pass
