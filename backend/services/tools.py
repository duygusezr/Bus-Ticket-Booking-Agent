import os
import sqlite3
import csv
import random
import string
import re
from typing import Optional
from datetime import datetime
from pathlib import Path

# DB ve CSV dosya yolları
# BASE_DIR burada 'backend' dizinini temsil eder
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "database" / "bilet_sistemi.db"
CSV_PATH = BASE_DIR / "database" / "bilet_sistemi.csv"

REZ_DB_PATH = BASE_DIR / "database" / "rezervasyonlar.db"
REZ_CSV_PATH = BASE_DIR / "database" / "rezervasyonlar.csv"

def init_db():
    # --- 1. SEFERLER VERİTABANI (bilet_sistemi.db) ---
    conn_seferler = sqlite3.connect(DB_PATH)
    cursor_seferler = conn_seferler.cursor()
    
    cursor_seferler.execute('''
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
    
    cursor_seferler.execute("SELECT COUNT(*) FROM seferler")
    if cursor_seferler.fetchone()[0] == 0 and CSV_PATH.exists():
        print(f"[TOOLS] {CSV_PATH} dosyasından seferler yükleniyor...")
        with open(CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            records = [(r['departure_city'], r['destination_city'], r['bus_plate'], r['travel_datetime'], float(r['price']), r['bus_type'], r['available_seats']) for r in reader]
            cursor_seferler.executemany('INSERT INTO seferler (departure_city, destination_city, bus_plate, travel_datetime, price, bus_type, available_seats) VALUES (?, ?, ?, ?, ?, ?, ?)', records)
    
    conn_seferler.commit()
    conn_seferler.close()

    # --- 2. REZERVASYONLAR VERİTABANI Ayrı Dosya (rezervasyonlar.db) ---
    conn_rez = sqlite3.connect(REZ_DB_PATH)
    cursor_rez = conn_rez.cursor()
    
    cursor_rez.execute('''
        CREATE TABLE IF NOT EXISTS rezervasyonlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pnr_code TEXT,
            sefer_id INTEGER,
            passenger_full_name TEXT,
            tc_identity_no TEXT,
            phone_number TEXT,
            email_address TEXT,
            seat_number TEXT,
            transaction_datetime TEXT,
            reservation_status TEXT
        )
    ''')
    
    cursor_rez.execute("SELECT COUNT(*) FROM rezervasyonlar")
    if cursor_rez.fetchone()[0] == 0 and REZ_CSV_PATH.exists():
        print(f"[TOOLS] {REZ_CSV_PATH} dosyasından eski rezervasyonlar yükleniyor...")
        with open(REZ_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            records = [(r['pnr_code'], int(r['sefer_id']), r['passenger_full_name'], r['tc_identity_no'], r['phone_number'], r['email_address'], r['seat_number'], r['transaction_datetime'], r['reservation_status']) for r in reader]
            cursor_rez.executemany('INSERT INTO rezervasyonlar (pnr_code, sefer_id, passenger_full_name, tc_identity_no, phone_number, email_address, seat_number, transaction_datetime, reservation_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', records)

    conn_rez.commit()
    conn_rez.close()

# Başlangıçta veritabanını kontrol et
init_db()

def normalize_city(city_name: str) -> str:
    """Turkish character normalization for better matching."""
    if not city_name: return ""
    rep = {
        'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G', 'ü': 'u', 'Ü': 'U',
        'ş': 's', 'Ş': 'S', 'ö': 'o', 'Ö': 'O', 'ç': 'c', 'Ç': 'C'
    }
    for search, replace in rep.items():
        city_name = city_name.replace(search, replace)
    return city_name.lower().strip()


def validate_tc_kimlik(tc_no: str) -> tuple[bool, str]:
    """
    T.C. Kimlik numarasını algoritmik olarak doğrular.
    """
    def _normalize_tokens(text: str) -> list[str]:
        t = (text or "").lower()
        t = t.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
        t = re.sub(r"[^0-9a-zA-Z\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t.split(" ") if t else []

    def _extract_numeric_stream(text: str) -> str:
        # Yazıyla ve rakamla gelen sayı ifadelerini sırayla rakama çevirir.
        unit_map = {
            "sifir": 0, "bir": 1, "iki": 2, "uc": 3, "dort": 4,
            "bes": 5, "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9
        }
        ten_map = {"on": 10, "yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50, "altmis": 60, "atmis": 60, "almis": 60, "yetmis": 70, "yemis": 70, "seksen": 80, "seksan": 80, "doksan": 90}
        compound_map = {
            "onbir": 11, "oniki": 12, "onuc": 13, "ondort": 14, "onbes": 15, "onalti": 16, "onyedi": 17, "onsekiz": 18, "ondokuz": 19
        }

        tokens = _normalize_tokens(text)
        parts: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            
            # 0. Yüzler parçası (N yüz ...) - Örn: "beş yüz otuz yedi" -> 537
            is_digit_or_unit = tok.isdigit() or tok in unit_map
            if is_digit_or_unit and i + 1 < len(tokens) and tokens[i + 1] == "yuz":
                val = int(tok) if tok.isdigit() else int(unit_map[tok])
                hundreds = val * 100
                i += 2
                # Onluk kontrolü (örn: otuz)
                if i < len(tokens) and tokens[i] in ten_map:
                    hundreds += ten_map[tokens[i]]
                    i += 1
                    # Birlik kontrolü (örn: yedi)
                    if i < len(tokens) and (tokens[i] in unit_map or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                        hundreds += int(unit_map.get(tokens[i], tokens[i]))
                        i += 1
                # Sadece birlik varsa (örn: beş yüz iki)
                elif i < len(tokens) and (tokens[i] in unit_map or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                    hundreds += int(unit_map.get(tokens[i], tokens[i]))
                    i += 1
                parts.append(str(hundreds))
                continue
                
            # 0.5 Tek başına yüz
            if tok == "yuz":
                parts.append("100")
                i += 1
                continue

            if tok.isdigit():
                parts.append(tok)
                i += 1
                continue
            if tok in compound_map:
                parts.append(str(compound_map[tok]))
                i += 1
                continue
            if tok in ten_map:
                nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
                if nxt in unit_map:
                    parts.append(str(ten_map[tok] + unit_map[nxt]))  # "yetmis iki" -> 72
                    i += 2
                    continue
                parts.append(str(ten_map[tok]))
                i += 1
                continue
            if tok in unit_map:
                parts.append(str(unit_map[tok]))
                i += 1
                continue
            i += 1

        # STT'de sık görülen parçalanma: "60 1" -> "61", "70 4" -> "74"
        merged: list[str] = []
        i = 0
        while i < len(parts):
            cur = parts[i]
            nxt = parts[i + 1] if i + 1 < len(parts) else None
            if (
                nxt is not None
                and cur.isdigit()
                and nxt.isdigit()
                and int(cur) in {20, 30, 40, 50, 60, 70, 80, 90}
                and len(nxt) == 1
            ):
                merged.append(str(int(cur) + int(nxt)))
                i += 2
                continue
            merged.append(cur)
            i += 1

        return "".join(merged)

    def _tc_checksum_ok(candidate: str) -> bool:
        if len(candidate) != 11 or not candidate.isdigit() or candidate[0] == "0":
            return False
        d = [int(x) for x in candidate]
        odd = d[0] + d[2] + d[4] + d[6] + d[8]
        even = d[1] + d[3] + d[5] + d[7]
        tenth = ((odd * 7) - even) % 10
        eleventh = sum(d[:10]) % 10
        return d[9] == tenth and d[10] == eleventh and (d[10] % 2 == 0)

    stream = _extract_numeric_stream(str(tc_no).strip())

    if len(stream) < 11:
        return False, "T.C. Kimlik numarası tam olarak 11 rakamdan oluşmalıdır. Lütfen rakam rakam (ör. 1 0 0 0 ...) söyleyin veya klavyeden yazın."

    if len(stream) > 11:
        # Fazla hanede en mantıklı 11'liyi bulmak için kayan pencere dener.
        for i in range(0, len(stream) - 10):
            cand = stream[i:i + 11]
            if _tc_checksum_ok(cand):
                stream = cand
                break
        else:
            stream = stream[:11]

    tc_no = stream
    if tc_no[0] == '0':
        return False, "T.C. Kimlik numarası 0 ile başlayamaz."

    digits = [int(d) for d in tc_no]
    sum_odd = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
    sum_even = digits[1] + digits[3] + digits[5] + digits[7]
    tenth_digit = ((sum_odd * 7) - sum_even) % 10
    eleventh_digit = sum(digits[:10]) % 10
    is_valid = (digits[9] == tenth_digit and digits[10] == eleventh_digit)
    is_even_last_digit = (digits[10] % 2 == 0)

    print(
        f"[TC_LOG] Input: {tc_no}, Odd: {sum_odd}, Even: {sum_even}, "
        f"Exp10: {tenth_digit}, Exp11: {eleventh_digit}, EvenLast: {is_even_last_digit}, Valid: {is_valid}"
    )

    if not is_even_last_digit:
        return False, "T.C. Kimlik numarası çift sayı ile bitmelidir."
    if not is_valid:
        return False, "Girdiğiniz numara T.C. Kimlik algoritmasına uygun değil. Lütfen rakamları kontrol edin."
    return True, "Geçerli"


def get_bus_trips(departure_city: str, destination_city: str, travel_date: Optional[str] = None) -> str:
    """Gets bus trips between departure_city and destination_city. 
    If travel_date is provided (YYYY-MM-DD), searches for that date. 
    If no trips found or no date provided, returns nearest 3 available dates."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Tüm seferleri çek (Güzergah filtresini Python tarafında normalize ederek yapacağız)
        cursor.execute('SELECT * FROM seferler')
        all_rows_db = cursor.fetchall()
        conn.close()
        
        norm_dep = normalize_city(departure_city)
        norm_dest = normalize_city(destination_city)
        
        # Güzergaha uyanları bul
        all_rows = []
        for row in all_rows_db:
            if norm_dep in normalize_city(row['departure_city']) and norm_dest in normalize_city(row['destination_city']):
                all_rows.append(row)
        
        if not all_rows:
            return f"Maalesef {departure_city} - {destination_city} arasında kayıtlı hiç sefer bulunamadı."

        # Tarih normalizasyonu ve filtreleme
        target_dt = None
        if travel_date:
            try:
                # LLM genellikle YYYY-MM-DD gönderir
                target_dt = datetime.strptime(travel_date.split(' ')[0], "%Y-%m-%d").date()
            except:
                pass

        exact_matches = []
        others = []
        today = datetime.now().date()

        for row in all_rows:
            # DB formatı: M/D/YYYY (Örn: 3/22/2026)
            try:
                row_dt = datetime.strptime(row['travel_datetime'], "%m/%d/%Y").date()
            except:
                continue
            
            # Geçmiş seferleri atla
            if row_dt < today:
                continue
            
            if target_dt and row_dt == target_dt:
                exact_matches.append(row)
            else:
                others.append((row, row_dt))

        # 1. Tam eşleşme varsa onları dön
        if exact_matches:
            result = [f"{travel_date} tarihinde {departure_city} -> {destination_city} için bulunan seferler:"]
            for row in exact_matches[:3]:
                result.append(
                    f"- Sefer_ID: {row['id']}, Tarih: {row['travel_datetime']}, Tipi: {row['bus_type']}, Fiyat: {row['price']} TL, Boş Koltuklar: {row['available_seats']}"
                )
            return "\n".join(result)

        # 2. Tam eşleşme yoksa yakın tarihleri bul
        # Kullanıcı tarih verdiyse sadece +/- 3 gün penceresinde öneri sun.
        # Uzak tarihlere sıçrama yapma.
        if target_dt:
            close_window = [x for x in others if abs((x[1] - target_dt).days) <= 3]
            if close_window:
                sorted_others = sorted(close_window, key=lambda x: (abs((x[1] - target_dt).days), x[1]))
                msg = f"{target_dt.strftime('%d.%m.%Y')} tarihinde tam uyan bir sefer bulamadım ama en yakın şu tarihlerde yardımcı olabilirim:"
            else:
                # +/- 3 gün içinde yoksa, genel en yakın 3 taneyi ver.
                sorted_others = sorted(others, key=lambda x: abs((x[1] - target_dt).days))
                msg = f"{target_dt.strftime('%d.%m.%Y')} yakınlarında seferimiz yok, ancak genel olarak şu tarihlerde seferlerimiz bulunuyor:"
        else:
            sorted_others = sorted(others, key=lambda x: x[1])
            msg = f"{departure_city} - {destination_city} güzergahı için en yakın seferlerimiz şunlar:"

        if not sorted_others:
            return f"Maalesef {departure_city} - {destination_city} güzergahında sistemde kayıtlı hiçbir sefer görünmüyor."

        result = [msg]
        seen_dates = set()
        count = 0
        for row, dt in sorted_others:
            date_str = dt.strftime("%d.%m.%Y")
            if date_str not in seen_dates:
                # Sadece tarihi veriyoruz ki kullanıcı boğulmasın. Seçtiğinde tekrar arama yapıp detayı çekecek.
                result.append(f"- {date_str}")
                seen_dates.add(date_str)
                count += 1
            if count >= 3: break
            
        return "\n".join(result)
        
    except Exception as e:
        return f"Veritabanı hatası: {str(e)}"

def validate_seat_selection(user_input: str, available_seats_str: str) -> str:
    """
    Extracts a seat number from user input and checks if it's available.
    Supports both numeric and Turkish word-based inputs (e.g., '5', 'beş').
    """
    import re
    
    text = str(user_input).strip().lower()
    
    # Word -> Number converter (Supports both Turkish and English)
    word_to_num = {
        # Turkish
        "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4,
        "beş": 5, "bes": 5, "altı": 6, "alti": 6, "yedi": 7,
        "sekiz": 8, "dokuz": 9, "on": 10, "onbir": 11, "on bir": 11,
        "oniki": 12, "on iki": 12, "onüç": 13, "on üç": 13,
        # English
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
        "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
        "twenty one": 21, "twenty-one": 21, "twenty two": 22, "twenty-two": 22,
        "thirty": 30, "forty": 40, "fifty": 50
    }
    
    extracted_seat = None
    
    # 1. First check with word-based input (case insensitive)
    for word, num in word_to_num.items():
        if word in text:
            extracted_seat = num
            break
    
    # 2. Eğer yazı bulunamadıysa rakamla tam eşleşme dene
    if extracted_seat is None:
        match = re.search(r'\b(\d{1,2})\b', text)
        if match:
            extracted_seat = int(match.group(1))

    if extracted_seat is None:
        return "Hata: Mesajınızda geçerli bir koltuk numarası bulamadım. Lütfen 1-50 arası bir rakam belirtin."
    
    seat = extracted_seat
    
    # Mevcut koltukları listeye çevir
    try:
        if isinstance(available_seats_str, str):
            valid_seats = [int(s.strip()) for s in available_seats_str.split(",") if s.strip().isdigit()]
        else:
            valid_seats = [int(s) for s in available_seats_str]
    except:
        return f"Hata: Koltuk listesi okunamadı. Lütfen şu listeden birini seçin: {available_seats_str}"

    print(f"[SEAT_LOG] User: {user_input} -> Extracted: {seat}, Avail: {valid_seats}")

    if seat in valid_seats:
        return f"Koltuk {seat} uygun. Devam etmek istiyor musunuz?"
    else:
        return f"Hata: {seat} numaralı koltuk mevcut değil veya zaten dolu. Lütfen şunlardan birini seçin: {available_seats_str}"

def validate_tc_number(tc_no: str) -> str:
    """Validates a Turkish Identity Number (T.C. Kimlik No) using the official checksum algorithm."""
    is_valid, msg = validate_tc_kimlik(tc_no)
    if is_valid:
        return "T.C. Kimlik numarası başarıyla doğrulandı. İşlemlere devam edebiliriz."
    else:
        return f"Hata: {msg}"


def _normalize_phone_input(text: str) -> str:
    """Telefon numarasını rakam, yazı ve karışık ifadelerden normalize eder."""
    t = (text or "").lower()
    t = t.replace("ı", "i").replace("ş", "s").replace("ğ", "g").replace("ü", "u").replace("ö", "o").replace("ç", "c")
    t = re.sub(r"[^0-9a-zA-Z\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    unit_map = {"sifir": 0, "bir": 1, "iki": 2, "uc": 3, "dort": 4, "bes": 5, "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
    ten_map = {"on": 10, "yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50, "altmis": 60, "atmis": 60, "almis": 60, "yetmis": 70, "yemis": 70, "seksen": 80, "seksan": 80, "doksan": 90}

    parts = []
    tokens = t.split(" ") if t else []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        
        # 0. Yüzler parçası (N yüz ...) - Örn: "beş yüz otuz yedi" -> 537
        is_digit_or_unit = tok.isdigit() or tok in unit_map
        if is_digit_or_unit and i + 1 < len(tokens) and tokens[i + 1] == "yuz":
            val = int(tok) if tok.isdigit() else int(unit_map[tok])
            hundreds = val * 100
            i += 2
            # Onluk kontrolü (örn: otuz)
            if i < len(tokens) and tokens[i] in ten_map:
                hundreds += ten_map[tokens[i]]
                i += 1
                # Birlik kontrolü (örn: yedi)
                if i < len(tokens) and (tokens[i] in unit_map or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                    hundreds += int(unit_map.get(tokens[i], tokens[i]))
                    i += 1
            # Sadece birlik varsa (örn: beş yüz iki)
            elif i < len(tokens) and (tokens[i] in unit_map or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                hundreds += int(unit_map.get(tokens[i], tokens[i]))
                i += 1
            parts.append(str(hundreds))
            continue
            
        # 0.5 Tek başına yüz
        if tok == "yuz":
            parts.append("100")
            i += 1
            continue

        if tok.isdigit():
            parts.append(tok)
            i += 1
            continue
        if tok in ten_map:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt in unit_map:
                parts.append(str(ten_map[tok] + unit_map[nxt]))
                i += 2
                continue
            parts.append(str(ten_map[tok]))
            i += 1
            continue
        if tok in unit_map:
            parts.append(str(unit_map[tok]))
            i += 1
            continue
        i += 1

    # "60 1" -> "61" benzeri parçalanmaları toparla
    merged_parts = []
    i = 0
    while i < len(parts):
        cur = parts[i]
        nxt = parts[i + 1] if i + 1 < len(parts) else None
        if (
            nxt is not None
            and cur.isdigit()
            and nxt.isdigit()
            and int(cur) in {20, 30, 40, 50, 60, 70, 80, 90}
            and len(nxt) == 1
        ):
            merged_parts.append(str(int(cur) + int(nxt)))
            i += 2
            continue
        merged_parts.append(cur)
        i += 1

    parts = merged_parts
    digits = "".join(parts)
    
    # +90 / 90 ülke kodu varsa kaldır
    if len(digits) == 12 and digits.startswith("90") and digits[2] == "5":
        digits = "0" + digits[2:]  # 905372791437 -> 05372791437
    elif len(digits) == 13 and digits.startswith("090"):
        digits = digits[1:]  # 0905372791437 -> 05372791437
    
    if len(digits) == 10 and digits.startswith("5"):
        digits = "0" + digits
    
    print(f"[PHONE_NORM] Input: '{text}' -> Digits: '{digits}' (len={len(digits)})")
    return digits


def validate_phone_number(phone: str) -> str:
    """Türkiye telefon numarasını normalize eder ve doğrular."""
    # LLM bazen int olarak gönderebilir (leading 0 düşer)
    phone = str(phone).strip()
    normalized = _normalize_phone_input(phone)
    print(f"[PHONE_VAL] Raw: '{phone}' (type={type(phone).__name__}) -> Normalized: '{normalized}'")
    
    if not normalized.isdigit() or len(normalized) not in (10, 11):
        return f"Hata: Telefon numarası {len(normalized) if normalized.isdigit() else 0} hane algılandı. Lütfen 05XX XXX XX XX formatında tekrar dener misiniz?"
    if len(normalized) == 10 and normalized[0] == "5":
        normalized = "0" + normalized
    if len(normalized) == 11 and not normalized.startswith("0"):
        return "Hata: Telefon numarası 0 ile başlamalıdır. Lütfen 05XX XXX XX XX formatında tekrar dener misiniz?"

    formatted = f"{normalized[0:4]} {normalized[4:7]} {normalized[7:9]} {normalized[9:11]}"
    return f"Telefon numarası doğrulandı: {formatted}"


def _normalize_email_input(text: str) -> str:
    """Sesli söylenen e-posta adresini normalleştirir."""
    t = (text or "").strip().lower()
    
    # 1. Türkçe karakter normalizasyonu
    t = t.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    t = t.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    
    # 2. Türkçe sayı kelimelerini rakamlara çevir ("yüz" dahil)
    unit_map = {"sifir": "0", "bir": "1", "iki": "2", "uc": "3", "dort": "4",
                "bes": "5", "alti": "6", "yedi": "7", "sekiz": "8", "dokuz": "9"}
    ten_map = {"on": 10, "yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50,
               "altmis": 60, "atmis": 60, "almis": 60, "yetmis": 70, "yemis": 70, "seksen": 80, "seksan": 80, "doksan": 90}
    
    tokens = t.split()
    result_tokens = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        
        # "N yuz ..." kalıbı (yüzler)
        is_digit_or_unit = tok.isdigit() or tok in unit_map
        if is_digit_or_unit and i + 1 < len(tokens) and tokens[i + 1] == "yuz":
            val = int(tok) if tok.isdigit() else int(unit_map[tok])
            hundreds = val * 100
            i += 2  # N ve yuz'u atla
            # Onluk
            if i < len(tokens) and tokens[i] in ten_map:
                hundreds += ten_map[tokens[i]]
                i += 1
                # Birlik (ondan sonra)
                if i < len(tokens) and (tokens[i] in unit_map or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                    hundreds += int(unit_map.get(tokens[i], tokens[i]))
                    i += 1
            elif i < len(tokens) and (tokens[i] in unit_map or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                hundreds += int(unit_map.get(tokens[i], tokens[i]))
                i += 1
            result_tokens.append(str(hundreds))
            continue
        
        # Tek başına "yuz" = 100
        if tok == "yuz":
            result_tokens.append("100")
            i += 1
            continue
        
        # Onluk + birlik
        if tok in ten_map:
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt in unit_map:
                result_tokens.append(str(ten_map[tok] + int(unit_map[nxt])))
                i += 2
                continue
            elif nxt.isdigit() and len(nxt) == 1:
                result_tokens.append(str(ten_map[tok] + int(nxt)))
                i += 2
                continue
            result_tokens.append(str(ten_map[tok]))
            i += 1
            continue
        
        # Birlik
        if tok in unit_map:
            result_tokens.append(unit_map[tok])
            i += 1
            continue
        
        # Sayı olmayan token
        result_tokens.append(tok)
        i += 1
    
    t = " ".join(result_tokens)
    
    # 3. @ işareti dönüşümleri
    t = re.sub(r"\b(at|et)\b", "@", t)
    
    # 4. Nokta dönüşümleri
    t = re.sub(r"\bnokta\b", ".", t)
    t = re.sub(r"\bdot\b", ".", t)
    
    # 5. STT domain düzeltmeleri (yaygın yanlış duyma kalıpları)
    t = re.sub(r"\bci\s*mail\b", "gmail", t)
    t = re.sub(r"\bci\s*meil\b", "gmail", t)
    t = re.sub(r"\bcimail\b", "gmail", t)
    t = re.sub(r"\bcimeil\b", "gmail", t)
    t = re.sub(r"\bg\s+mail\b", "gmail", t)
    t = re.sub(r"\bhot\s*mail\b", "hotmail", t)
    t = re.sub(r"\byahu\b", "yahoo", t)
    t = re.sub(r"\bout\s*look\b", "outlook", t)
    
    # 6. Domain+TLD birleştirme
    t = re.sub(r"\b(gmail|hotmail|yahoo|outlook|icloud|yandex)\s+(com|net|org|tr)\b", r"\1.\2", t)
    t = re.sub(r"\bcom\s+tr\b", "com.tr", t)
    
    # 7. Özel karakter dönüşümleri
    t = re.sub(r"\b(alt\s*cizgi|alt\s*tire|underscore)\b", "_", t)
    t = re.sub(r"\btire\b", "-", t)
    
    # 8. Boşlukları kaldır
    t = re.sub(r"\s+", "", t)
    
    # 9. Sondaki noktalama temizliği (STT cümle sonuna "." ekler)
    t = t.rstrip(".,;:!?")
    
    # 10. Çift tekrar temizliği (LLM bazen maili iki kez gönderir)
    if t.count("@") == 2 and len(t) % 2 == 0:
        half = len(t) // 2
        if t[:half] == t[half:]:
            t = t[:half]
    
    return t


def validate_email_address(email: str) -> str:
    """E-posta adresini sesli biçimden normalize eder ve doğrular."""
    t = _normalize_email_input(email)
    
    print(f"[EMAIL_LOG] Input: '{email}' -> Normalized: '{t}'")
    
    if re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", t):
        return f"E-posta doğrulandı: {t}"
    return f"Hata: E-posta adresini doğrulayamadım. Algılanan: '{t}'. Lütfen örnekteki gibi tekrar yazar mısınız: adsoyad@gmail.com"


def make_reservation(sefer_id: int, yolcu_ad_soyad: str, tc_no: str, telefon: str, eposta: str, koltuk_no: str) -> str:
    """Makes a bus ticket reservation. Validates TC identity number, updates available seats, and returns a PNR code upon success."""
    try:
        # TC Kimlik doğrulaması
        is_valid, validation_msg = validate_tc_kimlik(tc_no)
        if not is_valid:
            return f"Rezervasyon yapılamadı: {validation_msg}"
        
        # Seferler veritabanına bağlan
        conn_seferler = sqlite3.connect(DB_PATH)
        cursor_seferler = conn_seferler.cursor()
        
        # 1. Seferi bul ve koltuğu rezerve et
        cursor_seferler.execute("SELECT available_seats FROM seferler WHERE id = ?", (sefer_id,))
        row = cursor_seferler.fetchone()
        
        if not row:
            conn_seferler.close()
            return f"Hata: Belirtilen Sefer ID ({sefer_id}) veritabanında bulunamadı."
            
        available_seats_str = row[0]
        # Koltukları listeye çevir, boşlukları temizle
        seats = [s.strip() for s in available_seats_str.split(',') if s.strip()]
        
        if str(koltuk_no) not in seats:
            conn_seferler.close()
            return f"Hata: {koltuk_no} numaralı koltuk boş değil veya geçersiz. Uygun koltuklar: {available_seats_str}"
            
        seats.remove(str(koltuk_no))
        new_seats_str = ",".join(seats)
        
        # Seferi güncelle
        cursor_seferler.execute("UPDATE seferler SET available_seats = ? WHERE id = ?", (new_seats_str, sefer_id))
        conn_seferler.commit()
        conn_seferler.close()
        
        # 2. Rezervasyon kaydı oluştur (Ayrı Veritabanı)
        conn_rez = sqlite3.connect(REZ_DB_PATH)
        cursor_rez = conn_rez.cursor()
        
        pnr_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        transaction_time = datetime.now().strftime("%m/%d/%Y")
        
        cursor_rez.execute('''
            INSERT INTO rezervasyonlar (pnr_code, sefer_id, passenger_full_name, tc_identity_no, phone_number, email_address, seat_number, transaction_datetime, reservation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pnr_code, sefer_id, yolcu_ad_soyad, tc_no, telefon, eposta, koltuk_no, transaction_time, "completed"))
        
        conn_rez.commit()
        conn_rez.close()
        
        return f"Başarılı! PNR Kodu: {pnr_code}"
        
    except Exception as e:
        return f"Rezervasyon sırasında hata oluştu: {str(e)}"
