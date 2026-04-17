import sqlite3

def check():
    # Sefer 643 durumu
    conn = sqlite3.connect('backend/database/bilet_sistemi.db')
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id, available_seats FROM seferler WHERE id = 643").fetchone()
    if row:
        print(f"Sefer 643 available_seats: {row['available_seats']}")
    else:
        print("Sefer 643 bulunamadı")
    conn.close()

    # Son rezervasyonlar
    conn2 = sqlite3.connect('backend/database/rezervasyonlar.db')
    conn2.row_factory = sqlite3.Row
    print("\nSon 5 rezervasyon:")
    rows = conn2.execute(
        "SELECT pnr_code, sefer_id, passenger_full_name, seat_number, reservation_status "
        "FROM rezervasyonlar ORDER BY id DESC LIMIT 5"
    ).fetchall()
    for r in rows:
        print(dict(r))
    conn2.close()

if __name__ == '__main__':
    check()
