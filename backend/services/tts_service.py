import base64
import os
import re
from elevenlabs.client import ElevenLabs
from config import settings
import edge_tts

def get_eleven_client():
    """Anahtari her seferinde guncel ayarlardan alarak client olusturur."""
    if settings.ELEVENLABS_API_KEY and "your_" not in settings.ELEVENLABS_API_KEY.lower():
        return ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    return None

async def generate_tts_edge(text: str, lang: str) -> str:
    voice = "tr-TR-EmelNeural" if lang == "tr" else "en-US-AriaNeural"
    communicate = edge_tts.Communicate(text, voice)
    audio_data = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
    if not audio_data:
        raise Exception("Edge-TTS boş ses verisi döndürdü.")
    return base64.b64encode(audio_data).decode("utf-8")

async def generate_tts(text: str, lang: str = None, voice: str = "default") -> str:  # noqa
    """
    Gelen metni sese dönüştürür.
    Önce ElevenLabs dener, hata alırsa edge-tts'e düşer.
    """
    if not text or not text.strip():
        return ""

    lang = lang or settings.DEFAULT_LANG
    # ACT ve DELAY tokenlarını temizle (seslendirme için)
    clean_text = re.sub(r'<\|ACT:.*?\|>', '', text)
    clean_text = re.sub(r'<\|DELAY:.*?\|>', '', clean_text)
    clean_text = clean_text.strip()
    
    client = get_eleven_client()
    if not client:
        print("[TTS] ElevenLabs anahtarı yok, Edge-TTS kullanılıyor.")
        return await generate_tts_edge(clean_text, lang)

    voice_id = settings.ELEVENLABS_VOICE_ID or "EXAVITQu4vr4xnSDxMaL"
    
    try:
        last_err = None
        for attempt in range(2):
            try:
                audio_iterator = client.text_to_speech.convert(
                    text=clean_text,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                audio_content = b"".join(audio_iterator)
                if not audio_content:
                    raise Exception("ElevenLabs boş ses verisi döndürdü.")
                return base64.b64encode(audio_content).decode("utf-8")
            except Exception as e:
                last_err = e
                if "disconnected" in str(e).lower() or "connection" in str(e).lower():
                    import asyncio
                    await asyncio.sleep(1)
                else:
                    raise
        raise last_err
    except Exception as e:
        error_msg = str(e).lower()
        if "invalid" in error_msg or "permission" in error_msg or "quota" in error_msg or "not found" in error_msg:
            print(f"[TTS] ElevenLabs Hatası ({str(e)}). Fallback -> Edge-TTS...")
            return await generate_tts_edge(clean_text, lang)
        raise Exception(f"TTS Motoru Hatası: {str(e)}")
