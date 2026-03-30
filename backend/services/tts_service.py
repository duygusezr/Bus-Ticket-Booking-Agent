import base64
import os
import re
from elevenlabs.client import ElevenLabs
from config import settings
import edge_tts

TR_UNITS = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
TR_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]


def _number_to_turkish(n: int) -> str:
    if n == 0:
        return "sıfır"
    if n < 0:
        return "eksi " + _number_to_turkish(-n)

    def under_thousand(x: int) -> str:
        parts = []
        hundreds = x // 100
        rem = x % 100
        tens = rem // 10
        units = rem % 10
        if hundreds:
            if hundreds == 1:
                parts.append("yüz")
            else:
                parts.append(f"{TR_UNITS[hundreds]} yüz")
        if tens:
            parts.append(TR_TENS[tens])
        if units:
            parts.append(TR_UNITS[units])
        return " ".join(parts)

    parts = []
    millions = n // 1_000_000
    n %= 1_000_000
    thousands = n // 1_000
    n %= 1_000

    if millions:
        parts.append(f"{under_thousand(millions)} milyon")
    if thousands:
        parts.append("bin" if thousands == 1 else f"{under_thousand(thousands)} bin")
    if n:
        parts.append(under_thousand(n))
    return " ".join(parts).strip()


def _prepare_turkish_tts_text(text: str) -> str:
    """
    Improve Turkish number pronunciation:
    - 1.191,38 TL -> bin yuz doksan bir lira otuz sekiz kurus
    - long IDs (8+ digits) -> digit-by-digit readout
    - other integers -> cardinal word
    """
    result = text

    def money_repl(match: re.Match) -> str:
        raw = match.group(1).replace(".", "").replace(" ", "")
        whole, frac = (raw.split(",") + ["0"])[:2]
        lira = int(whole) if whole.isdigit() else 0
        kurus = int(frac[:2].ljust(2, "0")) if frac.isdigit() else 0
        if kurus > 0:
            return f"{_number_to_turkish(lira)} lira {_number_to_turkish(kurus)} kurus"
        return f"{_number_to_turkish(lira)} lira"

    # Currency first.
    result = re.sub(r"(\d[\d\.\s]*(?:,\d{1,2})?)\s*TL\b", money_repl, result, flags=re.IGNORECASE)

    def num_repl(match: re.Match) -> str:
        s = match.group(0)
        if len(s) >= 8:
            return " ".join(TR_UNITS[int(ch)] for ch in s)
        return _number_to_turkish(int(s))

    # Then standalone integer numbers.
    result = re.sub(r"\b\d+\b", num_repl, result)
    return result


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
        if chunk.get("type") == "audio":
            data = chunk.get("data")
            if data:
                audio_data.extend(data)
    if not audio_data:
        raise Exception("Edge-TTS boş ses verisi döndürdü.")
    return base64.b64encode(audio_data).decode("utf-8")

async def generate_tts(text: str, lang: str | None = None, voice: str = "default") -> str:
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
    if lang == "tr":
        clean_text = _prepare_turkish_tts_text(clean_text)
    
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
        assert last_err is not None
        raise last_err
    except Exception as e:
        error_msg = str(e).lower()
        if "invalid" in error_msg or "permission" in error_msg or "quota" in error_msg or "not found" in error_msg:
            print(f"[TTS] ElevenLabs Hatası ({str(e)}). Fallback -> Edge-TTS...")
            return await generate_tts_edge(clean_text, lang)
        raise Exception(f"TTS Motoru Hatası: {str(e)}")
