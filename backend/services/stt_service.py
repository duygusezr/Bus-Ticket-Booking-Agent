"""
STT service: Gemini-based audio transcription with post-processing.
number_utils is the single source of truth for number word → digit conversion.
"""
import re
from config import settings
import httpx

from services.number_utils import (
    normalize_text,
    extract_digit_stream,
    normalize_phone_digits,
    UNIT_MAP,
    TEN_MAP,
    COMPOUND_MAP,
    _merge_decade_unit,
)


# ─────────────────────────────────────────────
# ASR noise cleanup
# ─────────────────────────────────────────────

_BOOKING_KEYWORDS = frozenset({
    "ocak", "subat", "mart", "nisan", "mayis", "haziran",
    "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik",
    "istanbul", "ankara", "izmir", "bursa", "antalya", "adana", "konya",
    "evet", "hayir", "koltuk", "sefer", "bilet", "rezervasyon",
})

_TR_NUMBER_WORDS = frozenset({
    "bir", "iki", "uc", "dort", "bes", "alti", "yedi", "sekiz",
    "dokuz", "on", "onbir", "oniki", "onuc",
})

_EXCLUDE_WORDS = frozenset({
    # TR date/context
    "ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos",
    "eylul", "ekim", "kasim", "aralik", "bugun", "yarin", "haftaya", "gun",
    "ay", "yil", "pazartesi", "sali", "carsamba", "persembe", "cuma",
    "cumartesi", "pazar", "bin", "isim", "sehir", "bursa", "istanbul",
    "ankara", "gidis", "donus",
    # EN date/context
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "today", "tomorrow",
    "next", "week", "day", "month", "year", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday",
})

_NUMBER_WORDS = frozenset({
    "sifir", "bir", "iki", "uc", "dort", "bes", "alti", "yedi", "sekiz", "dokuz",
    "on", "yirmi", "otuz", "kirk", "elli", "altmis", "atmis", "almis", "yetmis",
    "yemis", "seksen", "seksan", "doksan", "onbir", "oniki", "onuc", "ondort",
    "onbes", "onalti", "onyedi", "onsekiz", "ondokuz",
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "hundred", "thousand",
})


def _deduplicate(text: str) -> str:
    """Remove STT hallucination repeats (char-level and word-level)."""
    if len(text) > 3 and len(text) % 2 == 0:
        h = len(text) // 2
        if text[:h] == text[h:]:
            text = text[:h]

    words = text.split()
    if len(words) % 2 == 0:
        h = len(words) // 2
        if words[:h] == words[h:]:
            text = " ".join(words[:h])
    return text


def _score_fragment(part: str) -> int:
    p = normalize_text(part)
    score = 0
    if re.search(r"\b\d{1,2}\b", p):
        score += 2
    if any(kw in p for kw in _BOOKING_KEYWORDS):
        score += 3
    if any(nw in p.split() for nw in _TR_NUMBER_WORDS):
        score += 2
    if len(p.split()) <= 6:
        score += 1
    return score


def _clean_asr_text(raw: str) -> str:
    """Remove ASR noise and return the most booking-relevant fragment."""
    if not raw:
        return ""
    text = re.sub(r"\(([^)]*)\)", " ", raw.strip())
    
    # Whisper yaygın halüsinasyonları temizle
    hallucinations = [
        "altyazı m.k.", "altyazı m.k", "altyazi m.k.", "altyazi m.k", "m.k.", "m.k", 
        "izlediğiniz için teşekkürler", "subtitles by", "amara.org", "çeviri"
    ]
    t_lower = text.lower()
    for h in hallucinations:
        if h in t_lower:
            text = re.compile(re.escape(h), re.IGNORECASE).sub("", text)
            
    text = re.sub(r"\s+", " ", text).strip()
    text = _deduplicate(text)

    parts = [p.strip(" .,!?:;") for p in re.split(r"[.!?]+", text) if p.strip(" .,!?:;")]
    if not parts:
        return text

    best = max(parts, key=_score_fragment)
    return best.strip() if _score_fragment(best) >= 3 else text


# ─────────────────────────────────────────────
# Context detection
# ─────────────────────────────────────────────

def _is_email_context(text: str) -> bool:
    t = normalize_text(text)
    if "@" in t:
        return True
    at_words = any(w in t.split() for w in ("at", "et"))
    domain_hints = any(d in t for d in ("gmail", "mail", "hotmail", "yahoo", "outlook", "yandex", "icloud"))
    dot_hints = any(d in t.split() for d in ("nokta", "dot", "com", "net", "org"))
    return (at_words and (domain_hints or dot_hints)) or (domain_hints and dot_hints)


def _is_name_context(history_last: str) -> bool:
    """Asistan isim soruyorsa numeric normalizasyon yapma."""
    name_keywords = [
        # TR
        "ad soyad", "isim", "adınız", "soyadınız", "ad ve soyad",
        # EN
        "full name", "your name", "passenger name", "name please", "name?",
    ]
    return any(kw in history_last for kw in name_keywords)


def _is_numeric_context(text: str) -> bool:
    t = normalize_text(text)
    tokens = re.sub(r"[^a-z0-9\s]", " ", t).split()
    if not tokens:
        return False
    for tok in tokens:
        if tok in _EXCLUDE_WORDS:
            return False
    numeric = sum(1 for tok in tokens if tok.isdigit() or tok in _NUMBER_WORDS)
    return numeric / len(tokens) >= 0.6


# ─────────────────────────────────────────────
# Number word → digit conversion (EN)
# ─────────────────────────────────────────────

_EN_WORD_MAP: dict[str, str] = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
    "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19", "twenty": "20",
    "thirty": "30", "forty": "40", "fifty": "50", "sixty": "60",
    "seventy": "70", "eighty": "80", "ninety": "90",
}


def _convert_en_numbers(text: str) -> str:
    t = text.lower()
    for word, digit in sorted(_EN_WORD_MAP.items(), key=lambda x: -len(x[0])):
        t = re.sub(rf"\b{re.escape(word)}\b", digit, t)
    return re.sub(r"\s+", " ", t).strip()


# ─────────────────────────────────────────────
# Number word → digit conversion (TR) — inline regex approach for conversational text
# ─────────────────────────────────────────────

_TR_COMPOUND_MAP: dict[str, str] = {
    "on bir": "11", "onbir": "11", "on iki": "12", "oniki": "12",
    "on üç": "13", "on uc": "13", "onuc": "13",
    "on dört": "14", "on dort": "14", "ondort": "14",
    "on beş": "15", "on bes": "15", "onbes": "15",
    "on altı": "16", "on alti": "16", "onalti": "16",
    "on yedi": "17", "onyedi": "17", "on sekiz": "18", "onsekiz": "18",
    "on dokuz": "19", "ondokuz": "19",
    "yirmi bir": "21", "yirmibir": "21", "yirmi iki": "22", "yirmiiki": "22",
    "yirmi üç": "23", "yirmi uc": "23", "yirmiuc": "23",
    "yirmi dört": "24", "yirmi dort": "24", "yirmidort": "24",
    "yirmi beş": "25", "yirmi bes": "25", "yirmibes": "25",
    "yirmi altı": "26", "yirmi alti": "26", "yirmialti": "26",
    "yirmi yedi": "27", "yirmiyedi": "27", "yirmi sekiz": "28", "yirmisekiz": "28",
    "yirmi dokuz": "29", "yirmidokuz": "29",
    "otuz bir": "31", "otuzbir": "31", "otuz iki": "32", "otuziki": "32",
    "otuz üç": "33", "otuz uc": "33", "otuzuc": "33",
    "otuz dört": "34", "otuz dort": "34", "otuzdort": "34",
    "otuz beş": "35", "otuz bes": "35", "otuzbes": "35",
    "otuz altı": "36", "otuz alti": "36", "otuzalti": "36",
    "otuz yedi": "37", "otuzyedi": "37", "otuz sekiz": "38", "otuzsekiz": "38",
    "otuz dokuz": "39", "otuzdokuz": "39",
    "kırk bir": "41", "kirk bir": "41", "kirkbir": "41",
    "kırk iki": "42", "kirk iki": "42", "kirkiki": "42",
    "kırk üç": "43", "kirk uc": "43", "kirkuc": "43",
    "kırk dört": "44", "kirk dort": "44", "kirkdort": "44",
    "kırk beş": "45", "kirk bes": "45", "kirkbes": "45",
    "kırk altı": "46", "kirk alti": "46", "kirkalti": "46",
    "kırk yedi": "47", "kirk yedi": "47", "kirkyedi": "47",
    "kırk sekiz": "48", "kirk sekiz": "48", "kirksekiz": "48",
    "kırk dokuz": "49", "kirk dokuz": "49", "kirkdokuz": "49",
    "elli bir": "51", "ellibir": "51",
}

_TR_SINGLE_MAP: dict[str, str] = {
    "bir": "1", "iki": "2", "üç": "3", "uc": "3", "dört": "4", "dort": "4",
    "beş": "5", "bes": "5", "altı": "6", "alti": "6", "yedi": "7",
    "sekiz": "8", "dokuz": "9", "on": "10", "yirmi": "20", "otuz": "30",
    "kırk": "40", "kirk": "40", "elli": "50",
}


def _convert_tr_numbers(text: str) -> str:
    t = text.lower()
    for k, v in sorted(_TR_COMPOUND_MAP.items(), key=lambda x: -len(x[0])):
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
    for k, v in sorted(_TR_SINGLE_MAP.items(), key=lambda x: -len(x[0])):
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
    return re.sub(r"\s+", " ", t).strip()


# ─────────────────────────────────────────────
# Numeric sequence collapse
# ─────────────────────────────────────────────

def _collapse_numeric_sequences(text: str) -> str:
    """Join digit-only chunks into a single number (TC/phone pattern)."""
    if not text:
        return ""
    # If any non-numeric, non-separator chars remain, leave as-is
    if re.sub(r"[\d\s.,;:!?\-()/ ]+", "", text):
        return text

    chunks = re.findall(r"\d+", text)
    if len(chunks) < 3:
        return text

    merged = _merge_decade_unit(chunks)
    joined = "".join(merged)
    return joined if len(joined) in (10, 11) else text


# ─────────────────────────────────────────────
# Gemini STT
# ─────────────────────────────────────────────

_MIME_MAP: dict[str, str] = {
    ".webm": "audio/webm",
    ".wav":  "audio/wav",
    ".mp3":  "audio/mpeg",
    ".ogg":  "audio/ogg",
}

async def _elevenlabs_transcribe(audio_bytes: bytes, filename: str, lang: str) -> str:
    """ElevenLabs Scribe v2 kullanarak sesi metne çevir."""
    from elevenlabs.client import AsyncElevenLabs
    import io

    if not settings.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY ayarlanmamış. STT işlemi yapılamaz.")

    # language_code: "tr" veya "en" → ElevenLabs ISO-639-1 destekliyor
    language_code = lang if lang in ("tr", "en") else None

    client = AsyncElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

    # ElevenLabs SDK file parametresi: (filename, bytes, mime_type) tuple'ı kabul ediyor
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".webm"
    mime_type = _MIME_MAP.get(ext, "audio/webm")

    audio_file = (filename, io.BytesIO(audio_bytes), mime_type)

    result = await client.speech_to_text.convert(
        file=audio_file,
        model_id=settings.ELEVENLABS_STT_MODEL,
        language_code=language_code,
        tag_audio_events=False,
    )

    transcript = (result.text or "").strip()

    # Non-Latin karakter filtresi (güvenlik)
    non_latin = re.findall(
        r'[\u0900-\u097F\u0600-\u06FF\u0400-\u04FF\u4E00-\u9FFF\u3040-\u30FF]',
        transcript,
    )
    if transcript and len(non_latin) / max(len(transcript), 1) > 0.3:
        print(f"[STT] Non-Latin karakter tespit edildi, transkript reddedildi: {transcript!r}")
        return ""

    return transcript


async def _gemini_transcribe(audio_bytes: bytes, filename: str, lang: str) -> str:
    """Gemini 2.5 Flash ile ses transkripsiyon (ElevenLabs fallback)."""
    import base64
    import httpx

    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY ayarlanmamış. Gemini STT kullanılamaz.")

    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".webm"
    mime_type = _MIME_MAP.get(ext, "audio/webm")

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    lang_hint = "Türkçe" if lang == "tr" else "English"
    prompt = (
        f"Transcribe the following audio exactly as spoken in {lang_hint}. "
        "Return only the transcription text, no explanations or formatting."
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": audio_b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 512,
        },
    }

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_STT_MODEL}:generateContent"
        f"?key={settings.GEMINI_API_KEY}"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini STT boş yanıt döndürdü: {data}")

    parts = candidates[0].get("content", {}).get("parts", [])
    transcript = " ".join(p.get("text", "") for p in parts).strip()

    # Non-Latin karakter filtresi (güvenlik)
    non_latin = re.findall(
        r'[\u0900-\u097F\u0600-\u06FF\u0400-\u04FF\u4E00-\u9FFF\u3040-\u30FF]',
        transcript,
    )
    if transcript and len(non_latin) / max(len(transcript), 1) > 0.3:
        print(f"[STT-Gemini] Non-Latin karakter tespit edildi, transkript reddedildi: {transcript!r}")
        return ""

    return transcript

def _postprocess(text: str, lang: str, last_assistant: str = "") -> str:
    """Apply context-aware normalization to raw transcript."""
    if _is_email_context(text):
        from services.tools import _normalize_email_input
        return _normalize_email_input(text)

    # İsim bağlamında normalizasyon yapma — rakama çevirme
    if _is_name_context(last_assistant.lower()):
        return text

    if _is_numeric_context(text):
        if lang == "en":
            pre = _convert_en_numbers(text)
            digits = extract_digit_stream(pre)
            return digits if digits else pre
        return extract_digit_stream(text) or text

    normalized = _convert_tr_numbers(text) if lang == "tr" else _convert_en_numbers(text)
    return _collapse_numeric_sequences(normalized)


async def transcribe_audio(audio_bytes: bytes, filename: str, lang: str = settings.DEFAULT_LANG, last_assistant: str = "") -> dict:
    """Transcribe audio via ElevenLabs Scribe (primary) → Gemini 2.5 Flash (fallback)."""
    if not audio_bytes:
        raise ValueError("Gönderilen ses verisi boş.")

    last_error: Exception | None = None

    # ── Primary: ElevenLabs Scribe ──────────────────────────────────────────
    if settings.ELEVENLABS_API_KEY:
        try:
            raw = await _elevenlabs_transcribe(audio_bytes, filename, lang)
            cleaned = _clean_asr_text(raw)
            result = _postprocess(cleaned, lang, last_assistant)
            print(f"[STT/ElevenLabs] raw={raw!r} → cleaned={cleaned!r} → final={result!r}")
            return {"text": result, "display_text": cleaned, "lang": lang, "provider": "elevenlabs"}
        except Exception as e:
            last_error = e
            print(f"[STT] ElevenLabs başarısız ({e!r}), Gemini fallback deneniyor…")
    else:
        print("[STT] ELEVENLABS_API_KEY yok, doğrudan Gemini fallback kullanılıyor.")

    # ── Fallback: Gemini 2.5 Flash ───────────────────────────────────────────
    if settings.GEMINI_API_KEY:
        try:
            raw = await _gemini_transcribe(audio_bytes, filename, lang)
            cleaned = _clean_asr_text(raw)
            result = _postprocess(cleaned, lang, last_assistant)
            print(f"[STT/Gemini] raw={raw!r} → cleaned={cleaned!r} → final={result!r}")
            return {"text": result, "display_text": cleaned, "lang": lang, "provider": "gemini"}
        except Exception as e:
            last_error = e
            print(f"[STT] Gemini fallback da başarısız: {e!r}")

    # ── Her iki provider da başarısız ────────────────────────────────────────
    raise RuntimeError(f"STT başarısız (tüm provider'lar denendi): {last_error}") from last_error

