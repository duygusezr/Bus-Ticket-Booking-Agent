import sqlite3

def check():
    conn = sqlite3.connect('backend/database/rezervasyonlar.db')
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM rezervasyonlar WHERE pnr_code = '5LHHFIWG'").fetchone()
    if row:
        print("FOUND PNR '5LHHFIWG':")
        print(dict(row))
    else:
        print("PNR NOT FOUND")
        print("Total rows:", conn.execute("SELECT count(*) FROM rezervasyonlar").fetchone()[0])
        print("Last row:")
        print(dict(conn.execute("SELECT * FROM rezervasyonlar ORDER BY id DESC LIMIT 1").fetchone()))
    
if __name__ == '__main__':
    check()
