import logging
import sys
import traceback
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from config import settings
from services.stt_service import transcribe_audio

router = APIRouter()
logger = logging.getLogger(__name__)


def _log_stt_error(e: Exception, tb: str) -> None:
    """Hata mesajını terminalde (stderr) gösterir."""
    err = sys.stderr
    err.write("\n")
    err.write("=" * 60 + "\n")
    err.write("STT HATASI (terminal)\n")
    err.write("=" * 60 + "\n")
    err.write("Mesaj: %s\n" % (str(e).strip() or repr(e)))
    err.write("\nTraceback:\n%s\n" % tb)
    err.write("=" * 60 + "\n")
    err.flush()

@router.post("/api/stt")
async def stt_endpoint(file: UploadFile = File(...), lang: str = Form(settings.DEFAULT_LANG)):
    """
    Kullanıcıdan gelen ses dosyasını (webm/wav/mp3) ElevenLabs Scribe API üzerinden metne dönüştürür.
    """
    try:
        audio_bytes = await file.read()
        filename = file.filename or "recording.webm"
        logger.info("STT isteği: %s byte, dosya=%s", len(audio_bytes), filename)

        import time
        t_stt_start = time.perf_counter()
        result = await transcribe_audio(audio_bytes, filename, lang)
        t_stt_end = time.perf_counter()
        
        print(f"--- [STT LATENCY] ---")
        print(f"Time: {t_stt_end - t_stt_start:.3f}s")
        print("-" * 25)
        
        return result
    except Exception as e:
        tb = traceback.format_exc()
        msg = str(e).strip() or repr(e)
        # ElevenLabs rate limit hatası — kullanıcıya anlamlı mesaj dön
        if "429" in msg or "system_busy" in msg or "rate_limit" in msg:
            raise HTTPException(
                status_code=429,
                detail={"error": "Ses servisi şu an yoğun, lütfen 1-2 saniye bekleyip tekrar deneyin.", "message": "rate_limit"}
            )
        logger.exception("STT endpoint hatası: %s", e)
        _log_stt_error(e, tb)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Sesten metne çevirme başarısız.",
                "message": msg,
            },
        )
