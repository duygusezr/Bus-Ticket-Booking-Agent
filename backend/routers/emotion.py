from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
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

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_CHAT_MODEL,
        )
        
        prompt = f"""Gelen metnin aşağıdaki duygulardan hangisine ait olduğunu sadece TEK BİR KELİME ile cevapla.
Duygular: happy, sad, angry, think, surprised, awkward, curious, neutral

Metin: "{request.text}"
Duygu:"""
        
        response = await model.generate_content_async(prompt)
        emotion = response.text.strip().lower()
        
        # Geçerli olmayan bir duygu dönerse nötre düşür
        valid_emotions = ["happy", "sad", "angry", "think", "surprised", "awkward", "curious", "neutral"]
        if emotion not in valid_emotions:
            emotion = "neutral"
            
        return {"emotion": emotion}
    except Exception as e:
        return {"emotion": "neutral", "error": str(e)}