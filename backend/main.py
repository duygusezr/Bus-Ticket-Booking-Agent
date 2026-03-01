import logging
import warnings
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Gereksiz uyarıları sustur
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=UserWarning)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn

from config import settings
from routers.chat import router as chat_router
from routers.stt import router as stt_router
from routers.tts import router as tts_router


# DeprecationWarning FIX: on_event → lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    from services.llm_service import GEMINI_MODEL
    print("Google Gemini chat model:", GEMINI_MODEL)
    yield  # Uygulama burada çalışır
    # Kapatma işlemleri buraya (gerekirse)


app = FastAPI(
    title="VRM Avatar Chatbot API",
    description="LLM, TTS ve STT servislerini birleştiren backend servisi",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Response sıkıştırma (Gzip)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Router'lar
app.include_router(chat_router)
app.include_router(stt_router)
app.include_router(tts_router)


@app.get("/")
async def root():
    """Çalışma durumu kontrol endpoint'i."""
    return {"status": "ok", "message": "Avatar Backend API çalışıyor."}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
