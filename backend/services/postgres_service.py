"""
PostgreSQL dual-write servisi.

SQLite ana veritabanı olmaya devam eder; PostgreSQL ikincil (async) kopya olarak
her yazma işleminde güncellenir. PostgreSQL bağlantısı yoksa veya hata olursa
uygulama çalışmaya devam eder — sadece log uyarısı verir.

Kullanım:
  1. .env dosyasına DATABASE_URL ekle:
     DATABASE_URL=postgresql://user:pass@host:5432/dbname
  2. Uygulama başlangıcında init_postgres() çağrılır (lifespan içinde).
  3. Her rezervasyonda sync_reservation_to_pg() çağrılır.

Bağımlılık: pip install asyncpg
"""

import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# asyncpg opsiyonel — yoksa PostgreSQL devre dışı kalır
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    asyncpg = None  # type: ignore[assignment]
    HAS_ASYNCPG = False
    logger.info("asyncpg yüklü değil — PostgreSQL desteği devre dışı.")

_pool: Optional["asyncpg.Pool"] = None  # type: ignore[name-defined]


async def init_postgres(database_url: Optional[str] = None) -> bool:
    """
    PostgreSQL bağlantı havuzunu başlat ve tabloları oluştur.
    Başarılıysa True, değilse False döndürür.
    """
    global _pool

    if not HAS_ASYNCPG:
        logger.warning("asyncpg yüklü değil. PostgreSQL senkronizasyonu devre dışı.")
        return False

    if not database_url:
        logger.info("DATABASE_URL tanımlı değil — PostgreSQL devre dışı.")
        return False

    try:
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=5,
            command_timeout=10,
        )

        async with _pool.acquire() as conn:
            # Seferler tablosu
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS seferler (
                    id SERIAL PRIMARY KEY,
                    departure_city TEXT,
                    destination_city TEXT,
                    bus_plate TEXT,
                    travel_datetime TEXT,
                    price REAL,
                    bus_type TEXT,
                    available_seats TEXT
                )
            """)

            # Rezervasyonlar tablosu
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS rezervasyonlar (
                    id SERIAL PRIMARY KEY,
                    pnr_code TEXT UNIQUE NOT NULL,
                    sefer_id INTEGER,
                    passenger_full_name TEXT,
                    tc_identity_hash TEXT,
                    phone_hash TEXT,
                    email_address TEXT,
                    seat_number TEXT,
                    transaction_datetime TEXT,
                    reservation_status TEXT
                )
            """)

            # Index
            await conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_pg_pnr_unique
                ON rezervasyonlar(pnr_code)
            """)

        logger.info("PostgreSQL bağlantısı ve tablolar hazır.")
        return True

    except Exception as e:
        logger.error("PostgreSQL başlatma hatası: %s", e)
        _pool = None
        return False


async def close_postgres() -> None:
    """Bağlantı havuzunu kapat (shutdown sırasında)."""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("PostgreSQL bağlantı havuzu kapatıldı.")


def is_pg_active() -> bool:
    """PostgreSQL bağlantısı aktif mi?"""
    return _pool is not None


async def sync_reservation_to_pg(
    pnr_code: str,
    sefer_id: int,
    passenger_full_name: str,
    tc_identity_hash: str,
    phone_hash: str,
    email_address: str,
    seat_number: str,
    transaction_datetime: str,
    reservation_status: str,
) -> bool:
    """
    Tek bir rezervasyonu PostgreSQL'e yaz.
    Başarılıysa True, hata olursa False döndürür (uygulama durmaz).
    """
    if not _pool:
        return False

    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rezervasyonlar
                    (pnr_code, sefer_id, passenger_full_name, tc_identity_hash,
                     phone_hash, email_address, seat_number,
                     transaction_datetime, reservation_status)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (pnr_code) DO NOTHING
                """,
                pnr_code, sefer_id, passenger_full_name, tc_identity_hash,
                phone_hash, email_address, seat_number,
                transaction_datetime, reservation_status,
            )
        logger.info("PG sync başarılı: PNR=%s", pnr_code)
        return True
    except Exception as e:
        logger.error("PG sync hatası (PNR=%s): %s", pnr_code, e)
        return False


async def sync_seat_update_to_pg(sefer_id: int, new_available_seats: str) -> bool:
    """Koltuk güncellemesini PostgreSQL'e yansıt."""
    if not _pool:
        return False

    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "UPDATE seferler SET available_seats = $1 WHERE id = $2",
                new_available_seats, sefer_id,
            )
        return True
    except Exception as e:
        logger.error("PG koltuk güncelleme hatası (sefer=%s): %s", sefer_id, e)
        return False


async def seed_seferler_to_pg(rows: list[dict]) -> bool:
    """
    SQLite'daki seferler tablosunu PostgreSQL'e aktar (ilk kurulum için).
    Mevcut kayıtlar varsa atlanır.
    """
    if not _pool or not rows:
        return False

    try:
        async with _pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM seferler")
            if count and count > 0:
                logger.info("PG seferler tablosu zaten dolu (%d kayıt), seed atlanıyor.", count)
                return True

            for row in rows:
                await conn.execute(
                    """
                    INSERT INTO seferler
                        (id, departure_city, destination_city, bus_plate,
                         travel_datetime, price, bus_type, available_seats)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT DO NOTHING
                    """,
                    row["id"], row["departure_city"], row["destination_city"],
                    row["bus_plate"], row["travel_datetime"], row["price"],
                    row["bus_type"], row["available_seats"],
                )

        logger.info("PG'ye %d sefer aktarıldı.", len(rows))
        return True
    except Exception as e:
        logger.error("PG seed hatası: %s", e)
        return False


async def seed_rezervasyonlar_to_pg(rows: list[dict]) -> bool:
    """
    SQLite'daki mevcut rezervasyonları PostgreSQL'e aktar.
    Zaten mevcut olan PNR'ler atlanır (ON CONFLICT DO NOTHING).
    Her uygulama başlangıcında çağrılır — eksik kayıtları tamamlar.
    """
    if not _pool or not rows:
        return False

    try:
        inserted = 0
        async with _pool.acquire() as conn:
            for row in rows:
                result = await conn.execute(
                    """
                    INSERT INTO rezervasyonlar
                        (pnr_code, sefer_id, passenger_full_name, tc_identity_hash,
                         phone_hash, email_address, seat_number,
                         transaction_datetime, reservation_status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    ON CONFLICT (pnr_code) DO NOTHING
                    """,
                    row["pnr_code"],
                    row["sefer_id"],
                    row["passenger_full_name"],
                    row.get("tc_identity_hash", ""),
                    row.get("phone_hash", ""),
                    row["email_address"],
                    row["seat_number"],
                    row["transaction_datetime"],
                    row["reservation_status"],
                )
                # asyncpg returns "INSERT 0 1" on success, "INSERT 0 0" on conflict
                if result and result.endswith("1"):
                    inserted += 1

        logger.info(
            "PG rezervasyon seed: %d yeni kayıt eklendi, %d zaten mevcuttu.",
            inserted, len(rows) - inserted,
        )
        return True
    except Exception as e:
        logger.error("PG rezervasyon seed hatası: %s", e)
        return False


async def get_pg_reservations(limit: int = 50) -> list[dict]:
    """PostgreSQL'den son rezervasyonları getir (debug/API için)."""
    if not _pool:
        return []

    try:
        async with _pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT pnr_code, sefer_id, passenger_full_name, seat_number, "
                "email_address, transaction_datetime, reservation_status "
                "FROM rezervasyonlar ORDER BY id DESC LIMIT $1",
                limit,
            )
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error("PG okuma hatası: %s", e)
        return []
