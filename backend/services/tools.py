import os
import sqlite3
import csv
import random
import string
import re
import hashlib
from contextlib import contextmanager
from typing import Optional
from datetime import datetime
from pathlib import Path

from services.number_utils import extract_digit_stream, normalize_phone_digits, normalize_text, UNIT_MAP, TEN_MAP

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "bilet_sistemi.db"
CSV_PATH = BASE_DIR / "database" / "bilet_sistemi.csv"
REZ_DB_PATH = BASE_DIR / "database" / "rezervasyonlar.db"
REZ_CSV_PATH = BASE_DIR / "database" / "rezervasyonlar.csv"


# ─────────────────────────────────────────────
# DB helpers
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
    """Initialize both databases. Called once at application startup via lifespan."""
    with _db(DB_PATH) as conn:
        conn.execute('''
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
        ''')
        if conn.execute("SELECT COUNT(*) FROM seferler").fetchone()[0] == 0 and CSV_PATH.exists():
            print(f"[TOOLS] Loading trips from {CSV_PATH}...")
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                records = [
                    (r['departure_city'], r['destination_city'], r['bus_plate'],
                     r['travel_datetime'], float(r['price']), r['bus_type'], r['available_seats'])
                    for r in csv.DictReader(f)
                ]
            conn.executemany(
                'INSERT INTO seferler (departure_city, destination_city, bus_plate, travel_datetime, price, bus_type, available_seats) VALUES (?, ?, ?, ?, ?, ?, ?)',
                records,
            )

    with _db(REZ_DB_PATH) as conn:
        conn.execute('''
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
        ''')
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_pnr_unique ON rezervasyonlar(pnr_code)"
        )
        if conn.execute("SELECT COUNT(*) FROM rezervasyonlar").fetchone()[0] == 0 and REZ_CSV_PATH.exists():
            print(f"[TOOLS] Loading reservations from {REZ_CSV_PATH}...")
            with open(REZ_CSV_PATH, 'r', encoding='utf-8') as f:
                records = [
                    (r['pnr_code'], int(r['sefer_id']), r['passenger_full_name'],
                     r.get('tc_identity_hash', ''), r.get('phone_hash', ''),
                     r['email_address'], r['seat_number'],
                     r['transaction_datetime'], r['reservation_status'])
                    for r in csv.DictReader(f)
                ]
            conn.executemany(
                '''INSERT OR IGNORE INTO rezervasyonlar
                   (pnr_code, sefer_id, passenger_full_name, tc_identity_hash, phone_hash,
                    email_address, seat_number, transaction_datetime, reservation_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                records,
            )


def _sync_csv(conn: sqlite3.Connection, table: str, path: Path, headers: list[str]) -> None:
    """Overwrite CSV from current DB state. Called inside an existing transaction."""
    try:
        rows = conn.execute(f"SELECT * FROM {table}").fetchall()
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
    except Exception as e:
        print(f"[TOOLS] CSV sync error ({path}): {e}")


def _hash_pii(value: str) -> str:
    """One-way SHA-256 hash for PII fields (TC, phone). NOT reversible."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_unique_pnr(conn: sqlite3.Connection, table: str = "rez.rezervasyonlar", length: int = 8) -> str:
    """Generate a PNR code guaranteed unique in the given table (supports attached DB alias)."""
    charset = string.ascii_uppercase + string.digits
    for _ in range(20):
        pnr = ''.join(random.choices(charset, k=length))
        exists = conn.execute(
            f"SELECT 1 FROM {table} WHERE pnr_code = ?", (pnr,)
        ).fetchone()
        if not exists:
            return pnr
    raise RuntimeError("PNR generation failed after 20 attempts.")


# ─────────────────────────────────────────────
# TC validation
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
    """Algorithmically validate a Turkish National ID number."""
    stream = extract_digit_stream(str(tc_no).strip())

    if len(stream) < 11:
        return False, "T.C. Kimlik numarası tam olarak 11 rakamdan oluşmalıdır."

    if len(stream) > 11:
        for i in range(len(stream) - 10):
            cand = stream[i:i + 11]
            if _tc_checksum_ok(cand):
                stream = cand
                break
        else:
            stream = stream[:11]

    if stream[0] == '0':
        return False, "T.C. Kimlik numarası 0 ile başlayamaz."

    d = [int(x) for x in stream]
    odd_sum = d[0] + d[2] + d[4] + d[6] + d[8]
    even_sum = d[1] + d[3] + d[5] + d[7]
    tenth = ((odd_sum * 7) - even_sum) % 10
    eleventh = sum(d[:10]) % 10

    # Log only a masked version — never log raw TC numbers
    masked = stream[:3] + "*" * 5 + stream[-3:]
    print(f"[TC_LOG] Input={masked} Valid={d[9]==tenth and d[10]==eleventh}")

    if d[10] % 2 != 0:
        return False, "T.C. Kimlik numarası çift sayı ile bitmelidir."
    if d[9] != tenth or d[10] != eleventh:
        return False, "Girdiğiniz numara T.C. Kimlik algoritmasına uygun değil."
    return True, "Geçerli"


# ─────────────────────────────────────────────
# City normalization
# ─────────────────────────────────────────────

def normalize_city(name: str) -> str:
    return normalize_text(name)


# ─────────────────────────────────────────────
# Tools (called by LLM)
# ─────────────────────────────────────────────

def get_bus_trips(departure_city: str, destination_city: str, travel_date: Optional[str] = None) -> str:
    """Gets bus trips between cities. If travel_date (YYYY-MM-DD) given, searches that date; otherwise returns nearest available dates."""
    try:
        norm_dep = normalize_city(departure_city)
        norm_dest = normalize_city(destination_city)
        today = datetime.now().date()

        # SQL-level filter to avoid full table scan; Python filter handles Turkish char normalization
        with _db(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT * FROM seferler WHERE LOWER(departure_city) LIKE ? AND LOWER(destination_city) LIKE ?",
                (f"%{norm_dep}%", f"%{norm_dest}%"),
            ).fetchall()

        matched = [
            r for r in rows
            if norm_dep in normalize_city(r['departure_city'])
            and norm_dest in normalize_city(r['destination_city'])
        ]

        if not matched:
            return f"Maalesef {departure_city} - {destination_city} arasında kayıtlı hiç sefer bulunamadı."

        target_dt = None
        if travel_date:
            try:
                target_dt = datetime.strptime(travel_date.split()[0], "%Y-%m-%d").date()
            except ValueError:
                pass

        future_rows: list[tuple] = []
        for row in matched:
            try:
                row_dt = datetime.strptime(row['travel_datetime'], "%m/%d/%Y").date()
            except ValueError:
                continue
            if row_dt >= today:
                future_rows.append((row, row_dt))

        if target_dt:
            exact = [(r, dt) for r, dt in future_rows if dt == target_dt]
            if exact:
                result = [f"{travel_date} tarihinde {departure_city} → {destination_city} için seferler:"]
                for row, _ in exact[:3]:
                    result.append(
                        f"- Sefer_ID: {row['id']}, Tarih: {row['travel_datetime']}, "
                        f"Tip: {row['bus_type']}, Fiyat: {row['price']} TL, Boş Koltuklar: {row['available_seats']}"
                    )
                return "\n".join(result)

            close = [(r, dt) for r, dt in future_rows if abs((dt - target_dt).days) <= 3]
            candidates = sorted(close or future_rows, key=lambda x: abs((x[1] - target_dt).days))
            msg = (
                f"{target_dt.strftime('%d.%m.%Y')} tarihinde sefer bulunamadı, en yakın tarihler:"
                if close else
                f"{target_dt.strftime('%d.%m.%Y')} yakınlarında sefer yok, genel olarak şu tarihler mevcut:"
            )
        else:
            candidates = sorted(future_rows, key=lambda x: x[1])
            msg = f"{departure_city} - {destination_city} güzergahı için en yakın seferler:"

        if not candidates:
            return f"{departure_city} - {destination_city} güzergahında uygun sefer bulunamadı."

        result = [msg]
        seen: set[str] = set()
        for row, dt in candidates:
            ds = dt.strftime("%d.%m.%Y")
            if ds not in seen:
                result.append(f"- {ds}")
                seen.add(ds)
            if len(seen) >= 3:
                break

        return "\n".join(result)

    except Exception as e:
        return f"Veritabanı hatası: {e}"


def validate_seat_selection(user_input: str, available_seats_str: str) -> str:
    """Check if a seat number (word or digit) is in the available seats list."""
    text = normalize_text(str(user_input))

    word_seat_map = {
        "bir": 1, "iki": 2, "uc": 3, "dort": 4, "bes": 5, "alti": 6,
        "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "onbir": 11, "on bir": 11,
        "oniki": 12, "on iki": 12, "onuc": 13, "on uc": 13,
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
        "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16,
        "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
        "twenty one": 21, "twenty-one": 21, "twenty two": 22, "twenty-two": 22,
        "thirty": 30, "forty": 40, "fifty": 50,
    }

    extracted = None
    for word, num in word_seat_map.items():
        if word in text:
            extracted = num
            break

    if extracted is None:
        m = re.search(r'\b(\d{1,2})\b', text)
        if m:
            extracted = int(m.group(1))

    if extracted is None:
        return "Hata: Geçerli bir koltuk numarası bulunamadı. Lütfen 1-50 arası bir rakam belirtin."

    try:
        valid_seats = [int(s.strip()) for s in str(available_seats_str).split(",") if s.strip().isdigit()]
    except Exception:
        return f"Hata: Koltuk listesi okunamadı: {available_seats_str}"

    print(f"[SEAT_LOG] Extracted={extracted} Available={valid_seats}")

    if extracted in valid_seats:
        return f"Koltuk {extracted} uygun. Devam etmek istiyor musunuz?"
    return f"Hata: {extracted} numaralı koltuk mevcut değil veya dolu. Lütfen şunlardan birini seçin: {available_seats_str}"


def validate_tc_number(tc_no: str) -> str:
    """Validate a Turkish National ID number."""
    is_valid, msg = validate_tc_kimlik(tc_no)
    return "T.C. Kimlik numarası başarıyla doğrulandı." if is_valid else f"Hata: {msg}"


def validate_phone_number(phone: str) -> str:
    """Normalize and validate a Turkish phone number."""
    phone = str(phone).strip()
    normalized = normalize_phone_digits(phone)

    if not normalized.isdigit() or len(normalized) not in (10, 11):
        digit_count = len(normalized) if normalized.isdigit() else 0
        return f"Hata: {digit_count} hane algılandı. Lütfen 05XX XXX XX XX formatında tekrar dener misiniz?"

    if len(normalized) == 10 and normalized[0] == "5":
        normalized = "0" + normalized
    if not normalized.startswith("0"):
        return "Hata: Telefon numarası 0 ile başlamalıdır."

    formatted = f"{normalized[0:4]} {normalized[4:7]} {normalized[7:9]} {normalized[9:11]}"
    return f"Telefon numarası doğrulandı: {formatted}"


def _normalize_email_input(text: str) -> str:
    """Normalize a voice-dictated email address into standard format."""
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
                hundreds += TEN_MAP[tokens[i]]; i += 1
                if i < len(tokens) and (tokens[i] in UNIT_MAP or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                    hundreds += int(UNIT_MAP.get(tokens[i], tokens[i])); i += 1
            elif i < len(tokens) and (tokens[i] in UNIT_MAP or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                hundreds += int(UNIT_MAP.get(tokens[i], tokens[i])); i += 1
            result_tokens.append(str(hundreds)); continue

        if tok == "yuz": result_tokens.append("100"); i += 1; continue

        if tok in TEN_MAP:
            if nxt in UNIT_MAP:
                result_tokens.append(str(TEN_MAP[tok] + UNIT_MAP[nxt])); i += 2; continue
            elif nxt.isdigit() and len(nxt) == 1:
                result_tokens.append(str(TEN_MAP[tok] + int(nxt))); i += 2; continue
            result_tokens.append(str(TEN_MAP[tok])); i += 1; continue

        if tok in UNIT_MAP: result_tokens.append(str(UNIT_MAP[tok])); i += 1; continue

        result_tokens.append(tok); i += 1

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
        if t[:half] == t[half:]:
            t = t[:half]

    return t


def validate_email_address(email: str) -> str:
    """Normalize and validate an email address (supports voice input)."""
    normalized = _normalize_email_input(email)
    print(f"[EMAIL_LOG] Normalized={normalized!r}")

    if re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", normalized):
        return f"E-posta doğrulandı: {normalized}"
    return f"Hata: E-posta doğrulanamadı. Algılanan: '{normalized}'. Örnek format: adsoyad@gmail.com"


def make_reservation(
    sefer_id: int,
    yolcu_ad_soyad: str,
    tc_no: str,
    telefon: str,
    eposta: str,
    koltuk_no: str,
) -> str:
    """
    Reserve a bus seat atomically across both databases using ATTACH DATABASE.
    TC and phone are hashed (SHA-256) before storage — never stored plaintext.
    Both the seat update and the reservation insert are committed in a single transaction.
    """
    try:
        is_valid, msg = validate_tc_kimlik(tc_no)
        if not is_valid:
            return f"Rezervasyon yapılamadı: {msg}"

        tc_hash = _hash_pii(tc_no)
        phone_hash = _hash_pii(telefon)

        # ATTACH DATABASE lets us write to both DB files in one atomic transaction.
        with _db(DB_PATH) as conn:
            conn.execute(f"ATTACH DATABASE '{REZ_DB_PATH}' AS rez")

            row = conn.execute("SELECT * FROM seferler WHERE id = ?", (sefer_id,)).fetchone()
            if not row:
                return f"Hata: Sefer ID {sefer_id} bulunamadı."

            seats = [s.strip() for s in row['available_seats'].split(',') if s.strip()]
            if str(koltuk_no) not in seats:
                return f"Hata: {koltuk_no} numaralı koltuk boş değil. Uygun koltuklar: {row['available_seats']}"

            seats.remove(str(koltuk_no))
            new_seats = ",".join(seats)
            conn.execute("UPDATE seferler SET available_seats = ? WHERE id = ?", (new_seats, sefer_id))

            pnr_code = _generate_unique_pnr(conn, table="rez.rezervasyonlar")
            transaction_time = datetime.now().strftime("%m/%d/%Y")

            conn.execute(
                '''INSERT INTO rez.rezervasyonlar
                   (pnr_code, sefer_id, passenger_full_name, tc_identity_hash, phone_hash,
                    email_address, seat_number, transaction_datetime, reservation_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (pnr_code, sefer_id, yolcu_ad_soyad, tc_hash, phone_hash,
                 eposta, koltuk_no, transaction_time, "completed"),
            )

            _sync_csv(
                conn, "seferler", CSV_PATH,
                ['id', 'departure_city', 'destination_city', 'bus_plate',
                 'travel_datetime', 'price', 'bus_type', 'available_seats'],
            )
            _sync_csv(
                conn, "rez.rezervasyonlar", REZ_CSV_PATH,
                ['id', 'pnr_code', 'sefer_id', 'passenger_full_name', 'tc_identity_hash',
                 'phone_hash', 'email_address', 'seat_number', 'transaction_datetime', 'reservation_status'],
            )

        print(f"[DB_SUCCESS] PNR={pnr_code} Sefer={sefer_id} Yolcu={yolcu_ad_soyad}")
        return f"Başarılı! PNR Kodu: {pnr_code}"

    except Exception as e:
        return f"Rezervasyon sırasında hata: {e}"
