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

        for row in all_rows:
            # DB formatı: M/D/YYYY (Örn: 3/22/2026)
            try:
                row_dt = datetime.strptime(row['travel_datetime'], "%m/%d/%Y").date()
            except:
                continue
            
            if target_dt and row_dt == target_dt:
                exact_matches.append(row)
            else:
                # Sadece gelecekteki seferleri veya bugüne yakın olanları tutalım
                others.append((row, row_dt))

        # 1. Tam eşleşme varsa onları dön
        if exact_matches:
            result = [f"{travel_date} tarihinde {departure_city} -> {destination_city} için bulunan seferler:"]
            for row in exact_matches[:3]:
                result.append(
                    f"- Sefer ID: {row['id']}, Tarih: {row['travel_datetime']}, Tipi: {row['bus_type']}, Fiyat: {row['price']} Lira. (Koltuklar: {row['available_seats']})"
                )
            return "\n".join(result)

        # 2. Tam eşleşme yoksa veya tarih verilmemişse EN YAKIN 3 günü bul
        today = datetime.now().date()
        
        # Sadece bugünden itibaren olan gelecek seferleri filtrele
        future_others = [x for x in others if x[1] >= today]
        
        if target_dt:
            # Belirlenen tarihe en yakın GELECEK seferler
            future_others.sort(key=lambda x: abs((x[1] - target_dt).days))
            msg = f"{travel_date} tarihinde sefer bulamadım ancak en yakın şu gelecek tarihlerde seferler var:"
        else:
            # Bugünden itibaren en yakınlar
            future_others.sort(key=lambda x: x[1])
            msg = f"{departure_city} - {destination_city} güzergahı için en yakın sefer tarihleri şunlardır:"

        if not future_others:
            return f"Maalesef {departure_city} - {destination_city} güzergahında gelecek bir tarihe ait hiç sefer bulunamadı."

        result = [msg]
        seen_dates = set()
        count = 0
        for row, dt in future_others:
            date_str = row['travel_datetime']
            if date_str not in seen_dates:
                result.append(f"- {date_str} tarihinde Sefer ID {row['id']} ({row['price']} Lira)")
                seen_dates.add(date_str)
                count += 1
            if count >= 3: break
            
        return "\n".join(result)
        
    except Exception as e:
        return f"Veritabanı hatası: {str(e)}"

def make_reservation(sefer_id: int, yolcu_ad_soyad: str, tc_no: str, telefon: str, eposta: str, koltuk_no: str) -> str:
    """Makes a bus ticket reservation. Updates the available seats and returns a PNR code upon success."""
    try:
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
