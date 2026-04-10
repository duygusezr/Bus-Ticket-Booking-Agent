import asyncio
import base64
import re

import edge_tts
from config import settings

_TR_UNITS = ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TR_TENS  = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]

_ACT_RE    = re.compile(r'<\|ACT:.*?\|>', re.DOTALL)
_DELAY_RE  = re.compile(r'<\|DELAY:.*?\|>')
_PAREN_RE  = re.compile(r'\(.*?\)')   # parantez içi — TTS'de okunmasın
_MONEY_RE  = re.compile(r'(\d[\d.\s]*(?:,\d{1,2})?)\s*TL\b', re.IGNORECASE)
_INT_RE    = re.compile(r'\b\d+\b')

# Dil + cinsiyet kombinasyonu için ses sözlüğü
_VOICES = {
    "tr":        "tr-TR-EmelNeural",    # Türkçe kadın (varsayılan)
    "tr_male":   "tr-TR-AhmetNeural",   # Türkçe erkek
    "en":        "en-US-AriaNeural",    # İngilizce kadın (varsayılan)
    "en_male":   "en-US-GuyNeural",     # İngilizce erkek
}


# ─────────────────────────────────────────────
# Number → Turkish words
# ─────────────────────────────────────────────

def _number_to_turkish(n: int) -> str:
    if n == 0:
        return "sıfır"
    if n < 0:
        return "eksi " + _number_to_turkish(-n)

    def _under_thousand(x: int) -> str:
        parts = []
        h = x // 100
        r = x % 100
        if h:
            parts.append("yüz" if h == 1 else f"{_TR_UNITS[h]} yüz")
        if r // 10:
            parts.append(_TR_TENS[r // 10])
        if r % 10:
            parts.append(_TR_UNITS[r % 10])
        return " ".join(parts)

    parts = []
    M = n // 1_000_000; n %= 1_000_000
    K = n // 1_000;     n %= 1_000

    if M: parts.append(f"{_under_thousand(M)} milyon")
    if K: parts.append("bin" if K == 1 else f"{_under_thousand(K)} bin")
    if n: parts.append(_under_thousand(n))
    return " ".join(parts).strip()


def _prepare_tts_text(text: str) -> str:
    """Convert numbers/currency to Turkish words for better TTS pronunciation."""
    def _money(m: re.Match) -> str:
        raw = m.group(1).replace(".", "").replace(" ", "")
        whole, *frac_parts = raw.split(",")
        frac = frac_parts[0] if frac_parts else "0"
        lira   = int(whole) if whole.isdigit() else 0
        kurus  = int(frac[:2].ljust(2, "0")) if frac.isdigit() else 0
        return (f"{_number_to_turkish(lira)} lira {_number_to_turkish(kurus)} kurus"
                if kurus else f"{_number_to_turkish(lira)} lira")

    def _num(m: re.Match) -> str:
        s = m.group(0)
        # Long IDs (8+ digits): read digit by digit
        if len(s) >= 8:
            return " ".join(_TR_UNITS[int(c)] for c in s)
        return _number_to_turkish(int(s))

    result = _MONEY_RE.sub(_money, text)
    result = _INT_RE.sub(_num, result)
    return result


# ─────────────────────────────────────────────
# Edge-TTS
# ─────────────────────────────────────────────

async def _edge_tts(text: str, lang: str, voice_key: str) -> str:
    """Synthesize via Edge-TTS with one retry on transient errors."""
    voice = _VOICES.get(voice_key, _VOICES.get(lang, _VOICES["tr"]))
    last_err: Exception | None = None

    for attempt in range(2):
        try:
            communicate = edge_tts.Communicate(text, voice)
            audio = bytearray()
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    audio.extend(chunk["data"])
            if not audio:
                raise RuntimeError("Edge-TTS returned empty audio.")
            return base64.b64encode(audio).decode()
        except Exception as e:
            last_err = e
            err_lower = str(e).lower()
            if attempt == 0 and any(k in err_lower for k in ("503", "invalid response", "connection")):
                await asyncio.sleep(1)
                continue
            break

    raise last_err  # type: ignore[misc]


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

async def generate_tts(text: str, lang: str | None = None, voice: str = "default") -> str:
    """
    Convert text to speech. Returns base64-encoded MP3 string.
    ACT/DELAY tokens are stripped before synthesis.
    Falls back to empty string on failure (non-fatal for callers).

    voice: "male" | "female" | "default"
    """
    if not text or not text.strip():
        return ""

    lang = lang or settings.DEFAULT_LANG

    # Cinsiyet+dil kombinasyonu anahtarı oluştur
    if voice == "male":
        voice_key = f"{lang}_male"
    else:
        voice_key = lang  # "tr" veya "en" — kadın sesi

    clean = _ACT_RE.sub("", text)
    clean = _DELAY_RE.sub("", clean)
    clean = _PAREN_RE.sub("", clean).strip()  # (YYYY-AA-GG) gibi parantez içlerini atla

    if lang == "tr":
        clean = _prepare_tts_text(clean)

    try:
        return await _edge_tts(clean, lang, voice_key)
    except Exception as e:
        print(f"[TTS] Edge-TTS failed: {e}. Returning empty.")
        return ""
