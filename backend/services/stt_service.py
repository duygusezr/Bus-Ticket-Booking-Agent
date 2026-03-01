import io
from elevenlabs.client import ElevenLabs
from config import settings

def get_eleven_client():
    """Anahtari her seferinde guncel ayarlardan alarak client olusturur."""
    if settings.ELEVENLABS_API_KEY and "your_" not in settings.ELEVENLABS_API_KEY.lower():
        return ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    return None

async def transcribe_audio(audio_bytes: bytes, filename: str, lang: str = settings.DEFAULT_LANG) -> dict:
    """Sadece ElevenLabs SDK (Scribe) kullanır."""
    if not audio_bytes or len(audio_bytes) == 0:
        raise Exception("Gönderilen ses verisi boş.")

    client = get_eleven_client()
    if not client:
        raise Exception("ElevenLabs API anahtarı ayarlanmamış veya geçersiz.")

    try:
        print(f"DEBUG: ElevenLabs SDK STT (Scribe) çağrılıyor... ({len(audio_bytes)} byte, {filename})")

        # ElevenLabs SDK, file parametresi olarak (filename, file_object, content_type) tuple'ı bekler
        audio_file = io.BytesIO(audio_bytes)

        # Dosya uzantısına göre content type belirle
        if filename.endswith(".webm"):
            content_type = "audio/webm"
        elif filename.endswith(".wav"):
            content_type = "audio/wav"
        elif filename.endswith(".mp3"):
            content_type = "audio/mpeg"
        elif filename.endswith(".ogg"):
            content_type = "audio/ogg"
        else:
            content_type = "audio/webm"  # Tarayıcı kaydı genellikle webm

        resp = client.speech_to_text.convert(
            file=(filename, audio_file, content_type),
            model_id="scribe_v1",
            language_code=lang,  # Frontend'den gelen dil (tr veya en)
        )

        print(f"DEBUG: Transkripsiyon başarılı: {resp.text[:50]}...")

        return {
            "text": resp.text,
            "lang": getattr(resp, "language_code", settings.DEFAULT_LANG)
        }
    except Exception as e:
        print(f"ElevenLabs SDK STT Hatası: {str(e)}")
        raise Exception(f"STT Servis Hatası: {str(e)}")