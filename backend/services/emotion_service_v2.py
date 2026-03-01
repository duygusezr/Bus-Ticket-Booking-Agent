import re
import torch
from transformers import pipeline

# ---------------------------------------------------------------------------
# Strateji:
#   1. LLM yanıtındaki <|ACT:...|> token'ını parse et  →  en güvenilir kaynak
#   2. Yoksa çokdilli transformer modeli kullan (Türkçe destekli)
#   3. Her ikisi de başarısız olursa "neutral" döndür
# ---------------------------------------------------------------------------

# Geçerli duygu etiketleri (avatar sistemiyle uyumlu)
VALID_EMOTIONS = {"happy", "sad", "angry", "think", "surprised", "awkward", "curious", "neutral"}

# ACT token regex: <|ACT:"emotion":{"name":"awkward",...}|> formatı
_ACT_PATTERN_JSON = re.compile(r'<\|ACT:.*?"name"\s*:\s*"(\w+)".*?\|>', re.IGNORECASE | re.DOTALL)
# Fallback: <|ACT:happy|> basit format
_ACT_PATTERN_SIMPLE = re.compile(r'<\|ACT:(\w+)\|>', re.IGNORECASE)

# ---------------------------------------------------------------------------
# 1. ACT Token Parser
# ---------------------------------------------------------------------------
def extract_act_emotion(text: str) -> str | None:
    """
    LLM yanıtından ACT token'ını bulur. JSON ve basit format desteklenir.
    """
    # Önce JSON formatını dene: <|ACT:"emotion":{"name":"happy"}|>
    match = _ACT_PATTERN_JSON.search(text)
    if match:
        emotion = match.group(1).lower()
        if emotion in VALID_EMOTIONS:
            print(f"[EMOTION] ACT JSON token → {emotion}")
            return emotion

    # Fallback: basit format <|ACT:happy|>
    match = _ACT_PATTERN_SIMPLE.search(text)
    if match:
        emotion = match.group(1).lower()
        if emotion in VALID_EMOTIONS:
            print(f"[EMOTION] ACT simple token → {emotion}")
            return emotion

    return None

# ---------------------------------------------------------------------------
# 2. Çokdilli Transformer Modeli (Türkçe dahil 100+ dil)
# ---------------------------------------------------------------------------
_emotion_pipe = None

# Çokdilli XLM-RoBERTa tabanlı duygu modeli
# Türkçe dahil 8 dili destekler, GPU/CPU otomatik seçer
_MODEL_NAME = "cardiffnlp/twitter-xlm-roberta-base-sentiment"

# Bu model 3 sınıf üretir: Positive, Negative, Neutral
# Bunları ELA'nın duygu sistemine mapliyoruz
_SENTIMENT_TO_EMOTION = {
    "positive": "happy",
    "negative": "sad",
    "neutral":  "neutral",
}

def get_emotion_pipe():
    global _emotion_pipe
    if _emotion_pipe is None:
        try:
            device = 0 if torch.cuda.is_available() else -1
            _emotion_pipe = pipeline(
                "text-classification",
                model=_MODEL_NAME,
                top_k=1,
                device=device,
            )
            print(f"[EMOTION] Model yüklendi: {_MODEL_NAME} | device={'GPU' if device == 0 else 'CPU'}")
        except Exception as e:
            print(f"[EMOTION] Model yüklenemedi: {e}")
    return _emotion_pipe

# ---------------------------------------------------------------------------
# 3. Ana Fonksiyon
# ---------------------------------------------------------------------------
async def analyze_sentiment_v2(text: str) -> str:
    """
    Türkçe uyumlu duygu analizi.

    Öncelik sırası:
      1. <|ACT:...|> token'ı varsa onu kullan (Gemini'nin kendi kararı)
      2. Çokdilli transformer modeline sor
      3. Fallback: neutral
    """
    if not text or len(text.strip()) < 2:
        return "neutral"

    # --- Adım 1: ACT Token ---
    act_emotion = extract_act_emotion(text)
    if act_emotion:
        print(f"[EMOTION] ACT token bulundu → {act_emotion}")
        return act_emotion

    # --- Adım 2: Transformer ---
    pipe = get_emotion_pipe()
    if pipe is None:
        return "neutral"

    try:
        results = pipe(text[:512])  # Model max 512 token alır
        if results:
            top = results[0]
            if isinstance(top, list):
                top = top[0]
            label = top.get("label", "neutral").lower()
            emotion = _SENTIMENT_TO_EMOTION.get(label, "neutral")
            print(f"[EMOTION] Transformer → label={label}, emotion={emotion}")
            return emotion
    except Exception as e:
        print(f"[EMOTION] Transformer hatası: {e}")

    return "neutral"
