import logging
import warnings
import sys
from contextlib import asynccontextmanager

# Suppress noisy third-party loggers before any imports
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
# Sadece gürültülü üçüncü taraf kütüphanelerinin UserWarning'lerini sustur
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")
warnings.filterwarnings("ignore", category=UserWarning, module="sentence_transformers")
warnings.filterwarnings("ignore", category=UserWarning, module="torch")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
import uvicorn

from config import settings
from routers.chat import router as chat_router
from routers.stt import router as stt_router
from routers.tts import router as tts_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB at startup — not at import time
    from services.tools import init_db
    from services.llm_service import GEMINI_MODEL
    init_db()
    logger.info("Gemini model: %s", GEMINI_MODEL)
    logger.info("CORS origins: %s", settings.CORS_ORIGINS)
    yield


app = FastAPI(
    title="Bus Ticket Booking API",
    description="LLM + TTS + STT backend for the Ela avatar chatbot",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(chat_router)
app.include_router(stt_router)
app.include_router(tts_router)


@app.get("/")
async def health_check():
    return {"status": "ok"}


@app.get("/api/reservations")
async def list_reservations():
    """Son rezervasyonları listele (debug/doğrulama amaçlı)."""
    import sqlite3
    from services.tools import REZ_DB_PATH
    try:
        conn = sqlite3.connect(REZ_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT pnr_code, sefer_id, passenger_full_name, seat_number, "
            "email_address, transaction_datetime, reservation_status "
            "FROM rezervasyonlar ORDER BY id DESC LIMIT 20"
        ).fetchall()
        conn.close()
        return {"count": len(rows), "reservations": [dict(r) for r in rows]}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/reservations/{pnr}")
async def get_reservation(pnr: str):
    """PNR koduna göre rezervasyon sorgula."""
    import sqlite3
    from services.tools import REZ_DB_PATH
    try:
        conn = sqlite3.connect(REZ_DB_PATH)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT pnr_code, sefer_id, passenger_full_name, seat_number, "
            "email_address, transaction_datetime, reservation_status "
            "FROM rezervasyonlar WHERE pnr_code = ?", (pnr.upper(),)
        ).fetchone()
        conn.close()
        if row:
            return {"found": True, "reservation": dict(row)}
        return {"found": False, "message": f"PNR '{pnr}' bulunamadı."}
    except Exception as e:
        return {"error": str(e)}


@app.websocket("/ws")
async def _dummy_ws(websocket):
    """Absorb stray HMR / Railway health-check WebSocket connections silently."""
    await websocket.accept()
    await websocket.close()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=False,
        ws_ping_interval=20,
        ws_ping_timeout=20,
    )
