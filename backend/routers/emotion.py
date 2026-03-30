from fastapi import APIRouter
from pydantic import BaseModel
import google.genai as genai
from config import settings

router = APIRouter()

class EmotionRequest(BaseModel):
    text: str

@router.post("/api/emotion")
async def analyze_emotion(request: EmotionRequest):
    """Metnin duygu analizini yapar."""
    try:
        if not settings.GOOGLE_API_KEY or "YOUR_GEMINI" in settings.GOOGLE_API_KEY:
            return {"emotion": "neutral"}

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        prompt = f"""Gelen metnin aşağıdaki duygulardan hangisine ait olduğunu sadece TEK BİR KELİME ile cevapla.
Duygular: happy, sad, angry, think, surprised, awkward, curious, neutral

Metin: "{request.text}"
Duygu:"""
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_CHAT_MODEL,
            contents=prompt,
        )
        raw = response.text
        emotion = raw.strip().lower() if raw else "neutral"
        
        # Geçerli olmayan bir duygu dönerse nötre düşür
        valid_emotions = ["happy", "sad", "angry", "think", "surprised", "awkward", "curious", "neutral"]
        if emotion not in valid_emotions:
            emotion = "neutral"
            
        return {"emotion": emotion}
    except Exception as e:
        return {"emotion": "neutral", "error": str(e)}