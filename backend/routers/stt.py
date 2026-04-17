import logging
import sys
import time
import traceback
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from config import settings
from services.stt_service import transcribe_audio

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/api/stt")
async def stt_endpoint(
    file: UploadFile = File(...),
    lang: str = Form(settings.DEFAULT_LANG),
    last_assistant: str = Form(""),
):
    """
    Kullanıcıdan gelen ses dosyasını Gemini multimodal API üzerinden metne dönüştürür.
    last_assistant: Son asistan mesajı — bağlam tespiti için (isim/numara/e-posta).
    """
    try:
        audio_bytes = await file.read()
        filename = file.filename or "recording.webm"
        logger.info("STT isteği: %s byte, dosya=%s", len(audio_bytes), filename)

        t_start = time.perf_counter()
        result = await transcribe_audio(audio_bytes, filename, lang, last_assistant)
        logger.info("STT tamamlandı: %.3fs", time.perf_counter() - t_start)

        return result

    except Exception as e:
        tb = traceback.format_exc()
        msg = str(e).strip() or repr(e)
        if "429" in msg or "system_busy" in msg or "rate_limit" in msg:
            raise HTTPException(
                status_code=429,
                detail={"error": "Ses servisi şu an yoğun, lütfen 1-2 saniye bekleyip tekrar deneyin.", "message": "rate_limit"},
            )
        logger.exception("STT endpoint hatası: %s", msg)
        sys.stderr.write(f"\n{'='*60}\nSTT HATASI\n{'='*60}\n{msg}\n{tb}\n{'='*60}\n")
        sys.stderr.flush()
        raise HTTPException(
            status_code=500,
            detail={"error": "Sesten metne çevirme başarısız.", "message": msg},
        )
