"""
Temel unit testler — pytest ile çalıştır:
    cd backend && python -m pytest test_core.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))


# ─────────────────────────────────────────────
# number_utils tests
# ─────────────────────────────────────────────

from services.number_utils import extract_digit_stream, normalize_phone_digits, normalize_text


def test_extract_digit_stream_units():
    assert extract_digit_stream("bir iki uc") == "123"
    assert extract_digit_stream("sifir") == "0"


def test_extract_digit_stream_tens():
    assert extract_digit_stream("yirmi uc") == "23"
    assert extract_digit_stream("otuz yedi") == "37"
    assert extract_digit_stream("altmis bir") == "61"


def test_extract_digit_stream_hundreds():
    assert extract_digit_stream("bes yuz otuz yedi") == "537"
    assert extract_digit_stream("iki yuz") == "200"


def test_extract_digit_stream_mixed():
    assert extract_digit_stream("37 50 6") == "37506"


def test_extract_digit_stream_stt_split():
    # STT splits "71" into "70 1" — should be merged
    assert extract_digit_stream("yetmis 1") == "71"
    assert extract_digit_stream("altmis 1") == "61"


def test_extract_digit_stream_empty():
    assert extract_digit_stream("") == ""
    assert extract_digit_stream("merhaba dunya") == ""


def test_normalize_phone_country_code():
    assert normalize_phone_digits("905372791437") == "05372791437"
    assert normalize_phone_digits("0905372791437") == "05372791437"


def test_normalize_phone_10digit():
    assert normalize_phone_digits("5372791437") == "05372791437"


def test_normalize_text_turkish_chars():
    assert normalize_text("Istanbul") == "istanbul"
    assert normalize_text("CANKAYA") == "cankaya"
    assert normalize_text("  bosluk  ") == "bosluk"


# ─────────────────────────────────────────────
# TC validation tests
# ─────────────────────────────────────────────

from services.tools import validate_tc_kimlik, _tc_checksum_ok


def test_tc_checksum_valid():
    assert _tc_checksum_ok("10000000146") is True


def test_tc_checksum_invalid_starts_with_zero():
    assert _tc_checksum_ok("01234567890") is False


def test_tc_checksum_wrong_length():
    assert _tc_checksum_ok("1234567890") is False
    assert _tc_checksum_ok("123456789012") is False


def test_tc_validate_kimlik_short():
    valid, msg = validate_tc_kimlik("12345")
    assert valid is False
    assert "11 rakam" in msg


def test_tc_validate_kimlik_starts_zero():
    valid, msg = validate_tc_kimlik("01234567890")
    assert valid is False
    assert "0 ile" in msg


def test_tc_validate_kimlik_valid():
    valid, msg = validate_tc_kimlik("10000000146")
    assert valid is True
    assert msg == "Geçerli"


def test_tc_validate_word_input():
    # Voice input normalized via extract_digit_stream
    valid, msg = validate_tc_kimlik("bir sifir sifir sifir sifir sifir sifir sifir bir dort alti")
    assert valid is True


# ─────────────────────────────────────────────
# Email normalization tests
# ─────────────────────────────────────────────

from services.tools import _normalize_email_input, validate_email_address


def test_email_at_substitution():
    assert _normalize_email_input("test at gmail nokta com") == "test@gmail.com"


def test_email_domain_merge():
    result = _normalize_email_input("duygu at gmail com")
    assert result == "duygu@gmail.com"


def test_email_stt_gmail_misread():
    result = _normalize_email_input("ahmet ci mail nokta com")
    assert result == "ahmet@gmail.com"


def test_email_already_valid():
    result = _normalize_email_input("user@hotmail.com")
    assert result == "user@hotmail.com"


def test_validate_email_valid():
    result = validate_email_address("test@gmail.com")
    assert "dogruland" in result.lower() or "doğrulandı" in result


def test_validate_email_invalid():
    result = validate_email_address("not-an-email")
    assert "Hata" in result


# ─────────────────────────────────────────────
# Phone validation tests
# ─────────────────────────────────────────────

from services.tools import validate_phone_number


def test_phone_valid_11digit():
    result = validate_phone_number("05372791437")
    assert "doğrulandı" in result


def test_phone_valid_10digit():
    result = validate_phone_number("5372791437")
    assert "doğrulandı" in result


def test_phone_too_short():
    result = validate_phone_number("0537")
    assert "Hata" in result


# ─────────────────────────────────────────────
# PII hashing tests
# ─────────────────────────────────────────────

from services.tools import _hash_pii


def test_hash_pii_deterministic():
    assert _hash_pii("12345678901") == _hash_pii("12345678901")


def test_hash_pii_different_inputs():
    assert _hash_pii("12345678901") != _hash_pii("10987654321")


def test_hash_pii_not_plaintext():
    result = _hash_pii("12345678901")
    assert "12345678901" not in result
    assert len(result) == 64  # SHA-256 hex


# ─────────────────────────────────────────────
# PNR generation tests
# ─────────────────────────────────────────────

from services.tools import _generate_unique_pnr
import sqlite3


def test_pnr_length_and_charset():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE rezervasyonlar (pnr_code TEXT UNIQUE)")
    pnr = _generate_unique_pnr(conn, table="rezervasyonlar", length=8)
    assert len(pnr) == 8
    assert pnr.isalnum()
    assert pnr == pnr.upper()
    conn.close()


def test_pnr_uniqueness():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE rezervasyonlar (pnr_code TEXT UNIQUE)")
    seen = set()
    for _ in range(50):
        pnr = _generate_unique_pnr(conn, table="rezervasyonlar", length=8)
        conn.execute("INSERT INTO rezervasyonlar VALUES (?)", (pnr,))
        conn.commit()
        assert pnr not in seen
        seen.add(pnr)
    conn.close()
