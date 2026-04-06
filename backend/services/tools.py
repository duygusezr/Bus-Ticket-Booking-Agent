import logging
import sqlite3
import asyncio
import csv
import random
import string
import re
import hashlib
from contextlib import contextmanager
from typing import Optional
from datetime import datetime
from pathlib import Path

from services.number_utils import (
    extract_digit_stream,
    normalize_phone_digits,
    normalize_text,
    UNIT_MAP,
    TEN_MAP,
)
from services.types import ToolResult

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "bilet_sistemi.db"
CSV_PATH = BASE_DIR / "database" / "bilet_sistemi.csv"
REZ_DB_PATH = BASE_DIR / "database" / "rezervasyonlar.db"
REZ_CSV_PATH = BASE_DIR / "database" / "rezervasyonlar.csv"

# Rezervasyon işlemi iki ayrı DB'ye yazdığından, eş zamanlı yazmaları
# önlemek için process-level bir kilit kullanılır.
# Not: Bu kilit tek process için yeterlidir. Yatay ölçekleme gerektiğinde
# Redis tabanlı dağıtık bir kilit ile değiştirilmeli.
_reservation_lock = asyncio.Lock()


# ─────────────────────────────────────────────
# DB yardımcıları
# ─────────────────────────────────────────────

@contextmanager
def _db(path: Path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Her iki veritabanını başlat. Uygulama başlangıcında lifespan üzerinden bir kez çağrılır."""
    with _db(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seferler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                departure_city TEXT,
                destination_city TEXT,
                bus_plate TEXT,
                travel_datetime TEXT,
                price REAL,
                bus_type TEXT,
                available_seats TEXT
            )
        """)
        if conn.execute("SELECT COUNT(*) FROM seferler").fetchone()[0] == 0 and CSV_PATH.exists():
            logger.info("Seferler CSV'den yükleniyor: %s", CSV_PATH)
            with open(CSV_PATH, "r", encoding="utf-8") as f:
                records = [
                    (
                        r["departure_city"], r["destination_city"], r["bus_plate"],
                        r["travel_datetime"], float(r["price"]), r["bus_type"], r["available_seats"],
                    )
                    for r in csv.DictReader(f)
                ]
            conn.executemany(
                "INSERT INTO seferler (departure_city, destination_city, bus_plate, "
                "travel_datetime, price, bus_type, available_seats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                records,
            )

    with _db(REZ_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rezervasyonlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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

        # Migration: eski sütun adlarını yenilere çevir
        try:
            cols = [row[1] for row in conn.execute("PRAGMA table_info(rezervasyonlar)").fetchall()]
            if "tc_identity_no" in cols and "tc_identity_hash" not in cols:
                conn.execute("ALTER TABLE rezervasyonlar RENAME COLUMN tc_identity_no TO tc_identity_hash")
                logger.info("Migration: tc_identity_no → tc_identity_hash")
            if "phone_number" in cols and "phone_hash" not in cols:
                conn.execute("ALTER TABLE rezervasyonlar RENAME COLUMN phone_number TO phone_hash")
                logger.info("Migration: phone_number → phone_hash")
        except Exception as mig_err:
            logger.warning("Kolon migration başarısız: %s", mig_err)

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_pnr_unique ON rezervasyonlar(pnr_code)"
        )
        if conn.execute("SELECT COUNT(*) FROM rezervasyonlar").fetchone()[0] == 0 and REZ_CSV_PATH.exists():
            logger.info("Rezervasyonlar CSV'den yükleniyor: %s", REZ_CSV_PATH)
            with open(REZ_CSV_PATH, "r", encoding="utf-8") as f:
                records = [
                    (
                        r["pnr_code"], int(r["sefer_id"]), r["passenger_full_name"],
                        r.get("tc_identity_hash") or r.get("tc_identity_no", ""),
                        r.get("phone_hash") or r.get("phone_number", ""),
                        r["email_address"], r["seat_number"],
                        r["transaction_datetime"], r["reservation_status"],
                    )
                    for r in csv.DictReader(f)
                ]
            conn.executemany(
                "INSERT OR IGNORE INTO rezervasyonlar "
                "(pnr_code, sefer_id, passenger_full_name, tc_identity_hash, phone_hash, "
                "email_address, seat_number, transaction_datetime, reservation_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                records,
            )


def get_all_seferler() -> list[dict]:
    """SQLite'daki tüm seferleri dict listesi olarak döndür (PG seed için)."""
    with _db(DB_PATH) as conn:
        rows = conn.execute("SELECT * FROM seferler").fetchall()
    return [dict(r) for r in rows]


def get_all_rezervasyonlar() -> list[dict]:
    """SQLite'daki tüm rezervasyonları dict listesi olarak döndür (PG seed için)."""
    with _db(REZ_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT pnr_code, sefer_id, passenger_full_name, tc_identity_hash, "
            "phone_hash, email_address, seat_number, transaction_datetime, "
            "reservation_status FROM rezervasyonlar ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def _hash_pii(value: str) -> str:
    """PII alanları için tek yönlü SHA-256 hash (TC, telefon). Geri döndürülemez."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_unique_pnr(conn: sqlite3.Connection, length: int = 8) -> str:
    """Verilen bağlantıda benzersizliği garantilenmiş PNR kodu üret."""
    charset = string.ascii_uppercase + string.digits
    for _ in range(20):
        pnr = "".join(random.choices(charset, k=length))
        exists = conn.execute(
            "SELECT 1 FROM rezervasyonlar WHERE pnr_code = ?", (pnr,)
        ).fetchone()
        if not exists:
            return pnr
    raise RuntimeError("PNR üretimi 20 denemede başarısız oldu.")


# ─────────────────────────────────────────────
# CSV tam senkronizasyon
# ─────────────────────────────────────────────

def _full_csv_sync() -> None:
    """
    Rezervasyonlar DB'sinin tamamını CSV'ye yaz (üzerine yazar).
    Her rezervasyon sonrası çağrılır — CSV her zaman DB ile senkron kalır.
    """
    try:
        with _db(REZ_DB_PATH) as conn:
            rows = conn.execute(
                "SELECT id, pnr_code, sefer_id, passenger_full_name, "
                "tc_identity_hash, phone_hash, email_address, "
                "seat_number, transaction_datetime, reservation_status "
                "FROM rezervasyonlar ORDER BY id"
            ).fetchall()

        with open(REZ_CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "pnr_code", "sefer_id", "passenger_full_name",
                "tc_identity_hash", "phone_hash", "email_address",
                "seat_number", "transaction_datetime", "reservation_status",
            ])
            for row in rows:
                writer.writerow([
                    row["id"], row["pnr_code"], row["sefer_id"],
                    row["passenger_full_name"], row["tc_identity_hash"],
                    row["phone_hash"], row["email_address"],
                    row["seat_number"], row["transaction_datetime"],
                    row["reservation_status"],
                ])

        logger.info("CSV tam sync tamamlandı: %d kayıt → %s", len(rows), REZ_CSV_PATH)
    except Exception as e:
        logger.warning("CSV tam sync başarısız: %s", e)


# ─────────────────────────────────────────────
# TC doğrulama (dahili)
# ─────────────────────────────────────────────

def _tc_checksum_ok(candidate: str) -> bool:
    if len(candidate) != 11 or not candidate.isdigit() or candidate[0] == "0":
        return False
    d = [int(x) for x in candidate]
    odd_sum = d[0] + d[2] + d[4] + d[6] + d[8]
    even_sum = d[1] + d[3] + d[5] + d[7]
    tenth = ((odd_sum * 7) - even_sum) % 10
    eleventh = sum(d[:10]) % 10
    return d[9] == tenth and d[10] == eleventh and d[10] % 2 == 0


def validate_tc_kimlik(tc_no: str) -> tuple[bool, str]:
    """Türkiye Cumhuriyeti kimlik numarasını algoritmik olarak doğrula."""
    stream = extract_digit_stream(str(tc_no).strip())

    if len(stream) < 11:
        return False, "T.C. Kimlik numarası tam olarak 11 rakamdan oluşmalıdır."

    if len(stream) > 11:
        for i in range(len(stream) - 10):
            cand = stream[i : i + 11]
            if _tc_checksum_ok(cand):
                stream = cand
                break
        else:
            stream = stream[:11]

    if stream[0] == "0":
        return False, "T.C. Kimlik numarası 0 ile başlayamaz."

    d = [int(x) for x in stream]
    odd_sum = d[0] + d[2] + d[4] + d[6] + d[8]
    even_sum = d[1] + d[3] + d[5] + d[7]
    tenth = ((odd_sum * 7) - even_sum) % 10
    eleventh = sum(d[:10]) % 10

    masked = stream[:3] + "*" * 5 + stream[-3:]
    logger.debug("TC doğrulama: giriş=%s geçerli=%s", masked, d[9] == tenth and d[10] == eleventh)

    if d[10] % 2 != 0:
        return False, "T.C. Kimlik numarası çift sayı ile bitmelidir."
    if d[9] != tenth or d[10] != eleventh:
        return False, "Girdiğiniz numara T.C. Kimlik algoritmasına uygun değil."
    return True, "Geçerli"


def normalize_city(name: str) -> str:
    return normalize_text(name)


# ─────────────────────────────────────────────
# E-posta normalizasyonu (dahili)
# ─────────────────────────────────────────────

def _normalize_email_input(text: str) -> str:
    """Sesle dikte edilen e-posta adresini standart formata normalize et."""
    t = normalize_text(text)
    tokens = t.split()
    result_tokens: list[str] = []
    i = 0

    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""

        if (tok.isdigit() or tok in UNIT_MAP) and nxt == "yuz":
            val = int(tok) if tok.isdigit() else UNIT_MAP[tok]
            hundreds = val * 100
            i += 2
            if i < len(tokens) and tokens[i] in TEN_MAP:
                hundreds += TEN_MAP[tokens[i]]
                i += 1
                if i < len(tokens) and (tokens[i] in UNIT_MAP or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                    hundreds += int(UNIT_MAP.get(tokens[i], tokens[i]))
                    i += 1
            elif i < len(tokens) and (tokens[i] in UNIT_MAP or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                hundreds += int(UNIT_MAP.get(tokens[i], tokens[i]))
                i += 1
            result_tokens.append(str(hundreds))
            continue

        if tok == "yuz":
            result_tokens.append("100")
            i += 1
            continue

        if tok in TEN_MAP:
            if nxt in UNIT_MAP:
                result_tokens.append(str(TEN_MAP[tok] + UNIT_MAP[nxt]))
                i += 2
                continue
            elif nxt.isdigit() and len(nxt) == 1:
                result_tokens.append(str(TEN_MAP[tok] + int(nxt)))
                i += 2
                continue
            result_tokens.append(str(TEN_MAP[tok]))
            i += 1
            continue

        if tok in UNIT_MAP:
            result_tokens.append(str(UNIT_MAP[tok]))
            i += 1
            continue

        result_tokens.append(tok)
        i += 1

    t = " ".join(result_tokens)
    t = re.sub(r"\b(at|et)\b", "@", t)
    t = re.sub(r"\b(nokta|dot)\b", ".", t)
    t = re.sub(r"\bci\s*m[ae]il\b", "gmail", t)
    t = re.sub(r"\bcimail\b", "gmail", t)
    t = re.sub(r"\bg\s+mail\b", "gmail", t)
    t = re.sub(r"\bhot\s*mail\b", "hotmail", t)
    t = re.sub(r"\byahu\b", "yahoo", t)
    t = re.sub(r"\bout\s*look\b", "outlook", t)
    t = re.sub(r"\b(gmail|hotmail|yahoo|outlook|icloud|yandex)\s+(com|net|org|tr)\b", r"\1.\2", t)
    t = re.sub(r"\bcom\s+tr\b", "com.tr", t)
    t = re.sub(r"\b(alt\s*cizgi|alt\s*tire|underscore)\b", "_", t)
    t = re.sub(r"\btire\b", "-", t)
    t = re.sub(r"\s+", "", t)
    t = t.rstrip(".,;:!?")

    if t.count("@") == 2 and len(t) % 2 == 0:
        half = len(t) // 2
        first, second = t[:half], t[half:]
        if first == second:
            t = first

    return t


# ─────────────────────────────────────────────
# LLM tarafından çağrılan araçlar — ToolResult döndürür
# ─────────────────────────────────────────────

def get_bus_trips(departure_city: str, destination_city: str, travel_date: Optional[str] = None) -> ToolResult:
    """Şehirler arası otobüs seferlerini getirir. travel_date (YYYY-MM-DD) verilmişse o tarihi,
    verilmemişse en yakın müsait tarihleri döndürür."""
    try:
        norm_dep = normalize_city(departure_city)
        norm_dest = normalize_city(destination_city)
        today = datetime.now().date()

        with _db(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT * FROM seferler WHERE LOWER(departure_city) LIKE ? AND LOWER(destination_city) LIKE ?",
                (f"%{norm_dep}%", f"%{norm_dest}%"),
            ).fetchall()

        matched = [
            r for r in rows
            if norm_dep in normalize_city(r["departure_city"])
            and norm_dest in normalize_city(r["destination_city"])
        ]

        if not matched:
            msg = f"Maalesef {departure_city} - {destination_city} arasında kayıtlı hiç sefer bulunamadı."
            return ToolResult(message=msg, success=False)

        target_dt = None
        if travel_date:
            try:
                target_dt = datetime.strptime(travel_date.split()[0], "%Y-%m-%d").date()
            except ValueError:
                pass

        future_rows: list[tuple] = []
        for row in matched:
            try:
                row_dt = datetime.strptime(row["travel_datetime"], "%m/%d/%Y").date()
            except ValueError:
                continue
            if row_dt >= today:
                future_rows.append((row, row_dt))

        # Tam tarih eşleşmesi
        if target_dt:
            exact = [(r, dt) for r, dt in future_rows if dt == target_dt]
            if exact:
                lines = [f"{travel_date} tarihinde {departure_city} → {destination_city} için seferler:"]
                first_id = None
                all_ids: list[int] = []
                for row, _ in exact[:3]:
                    if first_id is None:
                        first_id = row["id"]
                    all_ids.append(row["id"])
                    lines.append(
                        f"- Sefer_ID: {row['id']}, Tarih: {row['travel_datetime']}, "
                        f"Tip: {row['bus_type']}, Fiyat: {row['price']} TL, Boş Koltuklar: {row['available_seats']}"
                    )
                return ToolResult(
                    message="\n".join(lines),
                    success=True,
                    data={"sefer_ids": all_ids, "sefer_id": first_id},
                )

            close = [(r, dt) for r, dt in future_rows if abs((dt - target_dt).days) <= 3]
            candidates = sorted(close or future_rows, key=lambda x: abs((x[1] - target_dt).days))
            msg = (
                f"{target_dt.strftime('%d.%m.%Y')} tarihinde sefer bulunamadı, en yakın tarihler:"
                if close
                else f"{target_dt.strftime('%d.%m.%Y')} yakınlarında sefer yok, genel olarak şu tarihler mevcut:"
            )
        else:
            candidates = sorted(future_rows, key=lambda x: x[1])
            msg = f"{departure_city} - {destination_city} güzergahı için en yakın seferler:"

        if not candidates:
            return ToolResult(
                message=f"{departure_city} - {destination_city} güzergahında uygun sefer bulunamadı.",
                success=False,
            )

        lines = [msg]
        seen: set[str] = set()
        for row, dt in candidates:
            ds = dt.strftime("%d.%m.%Y")
            if ds not in seen:
                lines.append(f"- {ds}")
                seen.add(ds)
            if len(seen) >= 3:
                break

        return ToolResult(message="\n".join(lines), success=True)

    except Exception as e:
        return ToolResult(message=f"Veritabanı hatası: {e}", success=False)


def validate_seat_selection(user_input: str, available_seats_str: str) -> ToolResult:
    """Koltuk numarasının mevcut koltuk listesinde olup olmadığını kontrol et."""
    text = normalize_text(str(user_input))

    digit_stream = extract_digit_stream(text)
    extracted: Optional[int] = None

    if digit_stream:
        try:
            extracted = int(digit_stream[:2])
        except ValueError:
            pass

    if extracted is None:
        m = re.search(r"\b(\d{1,2})\b", text)
        if m:
            extracted = int(m.group(1))

    if extracted is None:
        return ToolResult(
            message="Hata: Geçerli bir koltuk numarası bulunamadı. Lütfen 1-50 arası bir rakam belirtin.",
            success=False,
        )

    try:
        valid_seats = [int(s.strip()) for s in str(available_seats_str).split(",") if s.strip().isdigit()]
    except Exception:
        return ToolResult(message=f"Hata: Koltuk listesi okunamadı: {available_seats_str}", success=False)

    logger.debug("Koltuk doğrulama: çıkarılan=%s mevcut=%s", extracted, valid_seats)

    if extracted in valid_seats:
        return ToolResult(
            message=f"Koltuk {extracted} uygun. Devam etmek istiyor musunuz?",
            success=True,
            data={"seat": extracted},
        )
    return ToolResult(
        message=(
            f"Hata: {extracted} numaralı koltuk mevcut değil veya dolu. "
            f"Lütfen şunlardan birini seçin: {available_seats_str}"
        ),
        success=False,
    )


def validate_tc_number(tc_no: str) -> ToolResult:
    """Türkiye Cumhuriyeti kimlik numarasını doğrula."""
    is_valid, msg = validate_tc_kimlik(tc_no)
    if is_valid:
        return ToolResult(message="T.C. Kimlik numarası başarıyla doğrulandı.", success=True)
    return ToolResult(message=f"Hata: {msg}", success=False)


def validate_phone_number(phone: str) -> ToolResult:
    """Türk telefon numarasını normalize et ve doğrula."""
    phone = str(phone).strip()
    normalized = normalize_phone_digits(phone)

    if not normalized.isdigit() or len(normalized) not in (10, 11):
        digit_count = len(normalized) if normalized.isdigit() else 0
        return ToolResult(
            message=f"Hata: {digit_count} hane algılandı. Lütfen 05XX XXX XX XX formatında tekrar dener misiniz?",
            success=False,
        )

    if len(normalized) == 10 and normalized[0] == "5":
        normalized = "0" + normalized
    if not normalized.startswith("0"):
        return ToolResult(message="Hata: Telefon numarası 0 ile başlamalıdır.", success=False)

    formatted = f"{normalized[0:4]} {normalized[4:7]} {normalized[7:9]} {normalized[9:11]}"
    return ToolResult(
        message=f"Telefon numarası doğrulandı: {formatted}",
        success=True,
        data={"formatted": formatted},
    )


def validate_email_address(email: str) -> ToolResult:
    """E-posta adresini normalize et ve doğrula (ses girişini destekler)."""
    normalized = _normalize_email_input(email)
    logger.debug("E-posta normalize: %r", normalized)

    if re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", normalized):
        return ToolResult(
            message=f"E-posta doğrulandı: {normalized}",
            success=True,
            data={"email": normalized},
        )
    return ToolResult(
        message=(
            f"Hata: E-posta doğrulanamadı. Algılanan: '{normalized}'. "
            "Örnek format: adsoyad@gmail.com"
        ),
        success=False,
    )


async def make_reservation(
    sefer_id: int,
    yolcu_ad_soyad: str,
    tc_no: str,
    telefon: str,
    eposta: str,
    koltuk_no: str,
) -> ToolResult:
    """
    Üç katmanlı yazma: SQLite (birincil) → PostgreSQL (ikincil) → CSV (yedek).

    1. SQLite: Seferler DB'de koltuk güncelle + Rezervasyonlar DB'ye kayıt ekle
    2. PostgreSQL: Aynı veriyi PG'ye async olarak yaz (varsa)
    3. CSV: Tüm rezervasyonlar tablosunu CSV'ye tam sync et
    """
    is_valid, msg = validate_tc_kimlik(tc_no)
    if not is_valid:
        return ToolResult(message=f"Rezervasyon yapılamadı: {msg}", success=False)

    tc_hash = _hash_pii(tc_no)
    phone_hash = _hash_pii(telefon)

    async with _reservation_lock:
        # ── 1. SQLite yazma ──────────────────────────────────────
        # Koltuk kontrol + güncelleme (seferler DB)
        with _db(DB_PATH) as trips_conn:
            trips_conn.execute("PRAGMA journal_mode=WAL")
            row = trips_conn.execute(
                "SELECT * FROM seferler WHERE id = ?", (sefer_id,)
            ).fetchone()
            if not row:
                return ToolResult(message=f"Hata: Sefer ID {sefer_id} bulunamadı.", success=False)

            seats = [s.strip() for s in row["available_seats"].split(",") if s.strip()]
            if str(koltuk_no) not in seats:
                return ToolResult(
                    message=(
                        f"Hata: {koltuk_no} numaralı koltuk boş değil. "
                        f"Uygun koltuklar: {row['available_seats']}"
                    ),
                    success=False,
                )

            seats.remove(str(koltuk_no))
            new_available_seats = ",".join(seats)
            trips_conn.execute(
                "UPDATE seferler SET available_seats = ? WHERE id = ?",
                (new_available_seats, sefer_id),
            )

        # Rezervasyon kaydı (rezervasyonlar DB)
        with _db(REZ_DB_PATH) as rez_conn:
            rez_conn.execute("PRAGMA journal_mode=WAL")
            pnr_code = _generate_unique_pnr(rez_conn)
            transaction_time = datetime.now().strftime("%m/%d/%Y")
            rez_conn.execute(
                "INSERT INTO rezervasyonlar "
                "(pnr_code, sefer_id, passenger_full_name, tc_identity_hash, phone_hash, "
                "email_address, seat_number, transaction_datetime, reservation_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pnr_code, sefer_id, yolcu_ad_soyad, tc_hash, phone_hash,
                    eposta, koltuk_no, transaction_time, "completed",
                ),
            )

    logger.info("Rezervasyon başarılı: PNR=%s Sefer=%s Yolcu=%s", pnr_code, sefer_id, yolcu_ad_soyad)

    # ── 2. PostgreSQL dual-write (fire-and-forget) ───────────
    try:
        from services.postgres_service import is_pg_active, sync_reservation_to_pg, sync_seat_update_to_pg
        if is_pg_active():
            # Her iki PG işlemini paralel çalıştır
            rez_task = sync_reservation_to_pg(
                pnr_code=pnr_code,
                sefer_id=sefer_id,
                passenger_full_name=yolcu_ad_soyad,
                tc_identity_hash=tc_hash,
                phone_hash=phone_hash,
                email_address=eposta,
                seat_number=koltuk_no,
                transaction_datetime=transaction_time,
                reservation_status="completed",
            )
            seat_task = sync_seat_update_to_pg(sefer_id, new_available_seats)
            pg_results = await asyncio.gather(rez_task, seat_task, return_exceptions=True)
            for i, result in enumerate(pg_results):
                if isinstance(result, Exception):
                    logger.error("PG sync görev %d hatası: %s", i, result)
    except ImportError:
        pass  # asyncpg yüklü değilse sessizce atla
    except Exception as pg_err:
        logger.warning("PostgreSQL sync hatası (uygulama devam ediyor): %s", pg_err)

    # ── 3. CSV tam senkronizasyon ────────────────────────────
    _full_csv_sync()

    return ToolResult(
        message=f"Başarılı! PNR Kodu: {pnr_code}",
        success=True,
        data={"pnr": pnr_code},
    )
