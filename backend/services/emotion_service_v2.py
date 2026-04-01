import re

# ---------------------------------------------------------------------------
# Strateji:
#   1. LLM yanıtındaki <|ACT:...|> token'ını parse et  →  en güvenilir kaynak
#   2. Yoksa basit Türkçe kelime (keyword) analizi yap
#   3. Her ikisi de başarısız olursa "neutral" döndür
# ---------------------------------------------------------------------------

VALID_EMOTIONS = {"happy", "sad", "angry", "think", "surprised", "awkward", "curious", "neutral"}

# ACT token regex
_ACT_PATTERN_JSON = re.compile(r'<\|ACT:.*?"name"\s*:\s*"(\w+)".*?\|>', re.IGNORECASE | re.DOTALL)
_ACT_PATTERN_SIMPLE = re.compile(r'<\|ACT:(\w+)\|>', re.IGNORECASE)

def extract_act_emotion(text: str) -> str | None:
    match = _ACT_PATTERN_JSON.search(text)
    if match:
        emotion = match.group(1).lower()
        if emotion in VALID_EMOTIONS:
            return emotion

    match = _ACT_PATTERN_SIMPLE.search(text)
    if match:
        emotion = match.group(1).lower()
        if emotion in VALID_EMOTIONS:
            return emotion

    return None

def analyze_keyword_emotion(text: str) -> str:
    """Hızlı lokal (kelime bazlı) duygu tespiti."""
    lt = text.lower()
    happy_w = ['😊', '😄', 'mutlu', 'harika', 'sevindim', 'güzel', 'iyi', 'evet', 'teşekkür', 'memnun', 'süper', 'onay']
    sad_w = ['😔', '😢', 'üzgün', 'maalesef', 'kötü', 'sorun', 'üzüldüm', 'malesef', 'hata']
    angry_w = ['😠', '😡', 'kızgın', 'sinir', 'dur', 'yeter', 'öfke', 'iptal', 'saçma']
    surprised_w = ['😲', '😮', 'inanılmaz', 'şaşırtıcı', 'aa', 'gerçekten mi']
    
    if any(w in lt for w in happy_w): return "happy"
    if any(w in lt for w in sad_w): return "sad"
    if any(w in lt for w in angry_w): return "angry"
    if any(w in lt for w in surprised_w): return "surprised"
    
    return "neutral"

async def analyze_sentiment_v2(text: str) -> str:
    if not text or len(text.strip()) < 2:
        return "neutral"

    # 1. Gemini'nin Kararı
    act_emotion = extract_act_emotion(text)
    if act_emotion:
        print(f"[EMOTION] LLM ACT token → {act_emotion}")
        return act_emotion

    # 2. Hızlı Kelime Analizi (Fallback)
    fallback = analyze_keyword_emotion(text)
    print(f"[EMOTION] Keyword fallback → {fallback}")
    return fallback
