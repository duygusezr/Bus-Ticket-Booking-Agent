import logging
import os
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
    # ── Startup ──────────────────────────────────────────────
    from services.tools import init_db, get_all_seferler, get_all_rezervasyonlar
    from services.llm_service import GEMINI_MODEL
    from services.postgres_service import (
        init_postgres, close_postgres, seed_seferler_to_pg, seed_rezervasyonlar_to_pg,
    )

    # SQLite başlat
    init_db()
    logger.info("Gemini model: %s", GEMINI_MODEL)
    logger.info("CORS origins: %s", settings.CORS_ORIGINS)

    # PostgreSQL başlat (opsiyonel — DATABASE_URL yoksa devre dışı kalır)
    database_url = os.getenv("DATABASE_URL")
    pg_ok = await init_postgres(database_url)
    if pg_ok:
        logger.info("PostgreSQL aktif — dual-write modu etkin.")
        # Seferleri PG'ye seed et (ilk seferde)
        seferler = get_all_seferler()
        await seed_seferler_to_pg(seferler)
        # Mevcut rezervasyonları PG'ye aktar (eksik olanları tamamlar)
        rezervasyonlar = get_all_rezervasyonlar()
        await seed_rezervasyonlar_to_pg(rezervasyonlar)
    else:
        logger.info("PostgreSQL devre dışı — sadece SQLite + CSV kullanılıyor.")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    await close_postgres()


app = FastAPI(
    title="Bus Ticket Booking API",
    description="LLM + TTS + STT backend for the avatar chatbot",
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
    from services.postgres_service import is_pg_active
    return {
        "status": "ok",
        "postgres": "active" if is_pg_active() else "disabled",
    }


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


@app.get("/api/pg/reservations")
async def list_pg_reservations():
    """PostgreSQL'deki rezervasyonları listele."""
    from services.postgres_service import is_pg_active, get_pg_reservations
    if not is_pg_active():
        return {"error": "PostgreSQL aktif değil. DATABASE_URL tanımlı mı?"}
    rows = await get_pg_reservations(limit=50)
    return {"count": len(rows), "source": "postgresql", "reservations": rows}


@app.get("/api/pg/status")
async def pg_status():
    """PostgreSQL bağlantı durumunu kontrol et."""
    from services.postgres_service import is_pg_active
    return {
        "postgresql_active": is_pg_active(),
        "database_url_set": bool(os.getenv("DATABASE_URL")),
    }


@app.get("/api/db/download/{db_name}")
async def download_db(db_name: str):
    """Railway'deki güncel DB dosyasını indir."""
    from fastapi.responses import FileResponse
    from services.tools import REZ_DB_PATH, DB_PATH

    db_map = {
        "rezervasyonlar": REZ_DB_PATH,
        "bilet_sistemi": DB_PATH,
    }
    path = db_map.get(db_name)
    if not path or not path.exists():
        return {"error": f"'{db_name}' bulunamadı. Geçerli: {list(db_map.keys())}"}
    return FileResponse(
        path=str(path),
        filename=f"{db_name}.db",
        media_type="application/x-sqlite3",
    )


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
