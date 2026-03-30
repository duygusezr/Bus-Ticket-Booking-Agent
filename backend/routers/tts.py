from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from config import settings
from services.tts_service import generate_tts

router = APIRouter()

class TTSRequest(BaseModel):
    text: str
    lang: Optional[str] = settings.DEFAULT_LANG
    voice: Optional[str] = "default"

@router.post("/api/tts")
async def tts_endpoint(request: TTSRequest):
    """
    Verilen metni ElevenLabs (veya ücretsiz edge-tts) üzerinden sese dönüştürür 
    ve base64 MP3 olarak string döner.
    """
    try:
        lang = request.lang or settings.DEFAULT_LANG
        voice = request.voice or "default"
        audio_base64 = await generate_tts(request.text, lang, voice)
        return {"audio": audio_base64}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Metinden sese çevirme başarısız.", "message": str(e)})
