import sys
import os
import sqlite3
from pathlib import Path

base_dir = Path(__file__).parent.resolve()
backend_dir = base_dir / "backend"
sys.path.append(str(backend_dir))

from services.tools import make_reservation, DB_PATH, REZ_DB_PATH

def test_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Find a trip and its available seats
    cursor.execute("SELECT id, available_seats FROM seferler LIMIT 1")
    trip = cursor.fetchone()
    if not trip:
        print("Test için sefer bulunamadı.")
        return
        
    sefer_id = trip[0]
    seats = trip[1].split(',')
    
    if not seats:
        print(f"Sefer ID {sefer_id} için boş koltuk yok: {trip[1]}")
        return
        
    koltuk_no = seats[0]
    print(f"Sefer ID {sefer_id} üzerinde {koltuk_no} numaralı koltuğu rezerve ediyoruz...")
    
    # Test yap!
    result = make_reservation(
        sefer_id=sefer_id,
        yolcu_ad_soyad="Test Yolcu",
        tc_no="12345678901",
        telefon="05554443322",
        eposta="test@mail.com",
        koltuk_no=koltuk_no
    )
    
    print("\nSonuç:", result)
    
    # Veritabanında güncelleme oldu mu kontrol et
    cursor.execute("SELECT available_seats FROM seferler WHERE id = ?", (sefer_id,))
    yeni_koltuklar = cursor.fetchone()[0]
    print(f"Eski Koltuklar: {trip[1]}")
    print(f"Yeni Koltuklar: {yeni_koltuklar}")
    conn.close()

    # Rezervasyonlar veritabanını test et
    conn_rez = sqlite3.connect(REZ_DB_PATH)
    cursor_rez = conn_rez.cursor()
    cursor_rez.execute("SELECT pnr_code, passenger_full_name FROM rezervasyonlar ORDER BY id DESC LIMIT 1")
    rez_kaydi = cursor_rez.fetchone()
    print(f"Son Eklenen Rezervasyonlar (rezervasyonlar.db): {rez_kaydi}")
    conn_rez.close()

if __name__ == "__main__":
    test_db()
