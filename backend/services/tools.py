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
    Kurallar:
    1. 11 haneli olmalı
    2. Tamamı rakamlardan oluşmalı
    3. İlk hane 0 olamaz
    4. İlk 10 hanenin toplamının mod 10'u = 11. hane
    5. (1,3,5,7,9. haneler toplamı × 7 - 2,4,6,8. haneler toplamı) mod 10 = 10. hane
    6. (1-8. haneler toplamı) mod 10 = 9. hane değil — doğrusu aşağıda
    
    Returns: (is_valid, error_message)
    """
    # Boşlukları temizle
    tc_no = tc_no.strip().replace(" ", "")
    
    if len(tc_no) != 11:
        return False, f"T.C. Kimlik numarası 11 haneli olmalıdır. Girdiğiniz numara {len(tc_no)} haneli."
    
    if not tc_no.isdigit():
        return False, "T.C. Kimlik numarası sadece rakamlardan oluşmalıdır."
    
    if tc_no[0] == '0':
        return False, "T.C. Kimlik numarası 0 ile başlayamaz."
    
    digits = [int(d) for d in tc_no]
    
    # 10. hane kontrolü: (tek pozisyonlar toplamı × 7 - çift pozisyonlar toplamı) mod 10
    odd_sum = sum(digits[i] for i in range(0, 9, 2))   # 1,3,5,7,9. haneler (index 0,2,4,6,8)
    even_sum = sum(digits[i] for i in range(1, 8, 2))   # 2,4,6,8. haneler (index 1,3,5,7)
    
    tenth_digit = (odd_sum * 7 - even_sum) % 10
    if digits[9] != tenth_digit:
        return False, "Girdiğiniz T.C. Kimlik numarası geçerli değil. Lütfen kontrol edip tekrar giriniz."
    
    # 11. hane kontrolü: ilk 10 hanenin toplamı mod 10
    eleventh_digit = sum(digits[:10]) % 10
    if digits[10] != eleventh_digit:
        return False, "Girdiğiniz T.C. Kimlik numarası geçerli değil. Lütfen kontrol edip tekrar giriniz."
    
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
            # Kullanıcının istediği tarihe en yakın gelecek seferleri bul
            # Önce o tarihten SONRAKI en yakınlar, sonra öncekiler
            future_from_target = [(r, dt) for r, dt in others if dt > target_dt]
            past_from_target = [(r, dt) for r, dt in others if dt <= target_dt and dt >= today]
            
            future_from_target.sort(key=lambda x: x[1])
            past_from_target.sort(key=lambda x: x[1], reverse=True)
            
            # İlk önce yakın gelecek tarihleri, sonra yakın geçmiş tarihleri birleştir
            sorted_others = []
            fi, pi = 0, 0
            while len(sorted_others) < len(future_from_target) + len(past_from_target):
                f_diff = (future_from_target[fi][1] - target_dt).days if fi < len(future_from_target) else float('inf')
                p_diff = (target_dt - past_from_target[pi][1]).days if pi < len(past_from_target) else float('inf')
                
                if f_diff <= p_diff:
                    sorted_others.append(future_from_target[fi])
                    fi += 1
                else:
                    sorted_others.append(past_from_target[pi])
                    pi += 1
            
            msg = f"{travel_date} tarihinde {departure_city} -> {destination_city} seferi bulunamadı. En yakın tarihler:"
        else:
            # Bugünden itibaren en yakınlar
            sorted_others = sorted(others, key=lambda x: x[1])
            msg = f"{departure_city} -> {destination_city} güzergahı için en yakın sefer tarihleri:"

        if not sorted_others:
            return f"Maalesef {departure_city} - {destination_city} güzergahında gelecek bir tarihe ait hiç sefer bulunamadı."

        result = [msg]
        seen_dates = set()
        count = 0
        for row, dt in sorted_others:
            date_str = dt.strftime("%d.%m.%Y")
            if date_str not in seen_dates:
                result.append(f"- {date_str} tarihinde sefer mevcut (Sefer ID: {row['id']}, Fiyat: {row['price']} TL, Tip: {row['bus_type']})")
                seen_dates.add(date_str)
                count += 1
            if count >= 3: break
            
        return "\n".join(result)
        
    except Exception as e:
        return f"Veritabanı hatası: {str(e)}"

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
