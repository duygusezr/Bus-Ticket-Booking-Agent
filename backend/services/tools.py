import os
import sqlite3
import csv
import random
import string
from datetime import datetime
from pathlib import Path

# DB ve CSV dosya yolları
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "bilet_sistemi.db"
CSV_PATH = BASE_DIR / "bilet_sistemi.csv"

REZ_DB_PATH = BASE_DIR / "rezervasyonlar.db"
REZ_CSV_PATH = BASE_DIR / "backend" / "rezervasyonlar.csv"

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
    # Temizlik ve temel kontrol
    tc_no = str(tc_no).strip().replace(" ", "")
    
    if len(tc_no) != 11 or not tc_no.isdigit():
        return False, "T.C. Kimlik numarası tam olarak 11 rakamdan oluşmalıdır."
    
    if tc_no[0] == '0':
        return False, "T.C. Kimlik numarası 0 ile başlayamaz."
    
    digits = [int(d) for d in tc_no]
    
    # 10. hane: ((1,3,5,7,9. haneler toplamı * 7) - (2,4,6,8. haneler toplamı)) % 10
    sum_odd = digits[0] + digits[2] + digits[4] + digits[6] + digits[8]
    sum_even = digits[1] + digits[3] + digits[5] + digits[7]
    
    tenth_digit = ((sum_odd * 7) - sum_even) % 10
    
    # 11. hane: ilk 10 hanenin toplamı % 10
    eleventh_digit = sum(digits[:10]) % 10
    
    is_valid = (digits[9] == tenth_digit and digits[10] == eleventh_digit)
    
    print(f"[TC_LOG] Input: {tc_no}, Odd: {sum_odd}, Even: {sum_even}, Exp10: {tenth_digit}, Exp11: {eleventh_digit}, Valid: {is_valid}")
    
    if not is_valid:
        return False, "Girdiğiniz numara T.C. Kimlik algoritmasına uygun değil. Lütfen rakamları kontrol edin."
        
    return True, "Geçerli"


def get_bus_trips(departure_city: str, destination_city: str, travel_date: str = None) -> str:
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
                    f"- Sefer ID: {row['id']}, Tarih: {row['travel_datetime']}, Tipi: {row['bus_type']}, Fiyat: {row['price']} TL, Boş Koltuklar: {row['available_seats']}"
                )
            return "\n".join(result)

        # 2. Tam eşleşme yoksa EN YAKIN gelecek tarihleri bul
        # Eğer kullanıcı bir tarih verdiyse o tarihe en yakın olanları,
        # vermemişse bugüne en yakın olanları sırala
        if target_dt:
            sorted_others = sorted(others, key=lambda x: abs((x[1] - target_dt).days))
            msg = f"{target_dt.strftime('%d.%m.%Y')} tarihinde tam uyan bir sefer bulamadım ama en yakın şu tarihlerde yardımcı olabilirim:"
        else:
            sorted_others = sorted(others, key=lambda x: x[1])
            msg = f"{departure_city} - {destination_city} güzergahı için en yakın seferlerimiz şunlar:"

        if not sorted_others:
            return f"Maalesef {departure_city} - {destination_city} güzergahında yakın zamanda bir seferimiz görünmüyor."

        result = [msg]
        seen_dates = set()
        count = 0
        for row, dt in sorted_others:
            date_str = dt.strftime("%d.%m.%Y")
            if date_str not in seen_dates:
                # Sefer ID'yi parantez içinde sona koyuyoruz ki LLM onu bilsin ama kullanıcıya yansıtmasın
                result.append(f"- {date_str} (Fiyat: {row['price']} TL, Tip: {row['bus_type']}, ID: {row['id']})")
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
    
    # Türkçe sayı -> Rakam dönüştürücü (Daha kapsamlı)
    tr_to_num = {
        "bir": 1, "iki": 2, "üç": 3, "uc": 3, "dört": 4, "dort": 4,
        "beş": 5, "bes": 5, "altı": 6, "alti": 6, "yedi": 7,
        "sekiz": 8, "dokuz": 9, "on": 10, "onbir": 11, "on bir": 11,
        "oniki": 12, "on iki": 12, "onüç": 13, "on üç": 13
    }
    
    extracted_seat = None
    
    # 1. Önce Türkçe yazıyla kontrol et
    for word, num in tr_to_num.items():
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
        return f"Koltuk {seat} uygun. Rezervasyon işlemine devam edebiliriz."
    else:
        return f"Hata: {seat} numaralı koltuk mevcut değil veya zaten dolu. Lütfen şunlardan birini seçin: {available_seats_str}"

def validate_tc_number(tc_no: str) -> str:
    """Validates a Turkish Identity Number (T.C. Kimlik No) using the official checksum algorithm."""
    is_valid, msg = validate_tc_kimlik(tc_no)
    if is_valid:
        return f"T.C. Kimlik numarası ({tc_no}) doğrulandı. İşlemlere devam edebiliriz."
    else:
        return f"Hata: {msg}"

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
            return "Hata: Belirtilen Sefer ID bulunamadı."
            
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
