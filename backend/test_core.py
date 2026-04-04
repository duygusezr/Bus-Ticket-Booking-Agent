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
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "doğruland" in result.message.lower()


def test_validate_email_invalid():
    result = validate_email_address("not-an-email")
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "Hata" in result.message


# ─────────────────────────────────────────────
# Phone validation tests
# ─────────────────────────────────────────────

from services.tools import validate_phone_number


def test_phone_valid_11digit():
    result = validate_phone_number("05372791437")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "doğrulandı" in result.message


def test_phone_valid_10digit():
    result = validate_phone_number("5372791437")
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert "doğrulandı" in result.message


def test_phone_too_short():
    result = validate_phone_number("0537")
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "Hata" in result.message


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


# ─────────────────────────────────────────────
# ToolResult tests
# ─────────────────────────────────────────────

from services.types import ToolResult


def test_tool_result_str():
    """ToolResult.__str__ Gemini'ye gönderilecek mesajı döndürmeli."""
    r = ToolResult(message="Koltuk 5 uygun.", success=True, data={"seat": 5})
    assert str(r) == "Koltuk 5 uygun."


def test_tool_result_failure_has_no_data():
    r = ToolResult(message="Hata: geçersiz", success=False)
    assert r.success is False
    assert r.data == {}


# ─────────────────────────────────────────────
# session_state tests
# ─────────────────────────────────────────────

from services.session_state import (
    get_session, clear_session, update_session_from_tool_result, build_truth_injection
)


def test_session_get_creates_new():
    sid = "test_new_session_x1"
    clear_session(sid)
    s = get_session(sid)
    assert s.sefer_id is None
    assert s.seat is None
    clear_session(sid)


def test_session_clear():
    sid = "test_clear_x2"
    s = get_session(sid)
    s.sefer_id = 99
    clear_session(sid)
    s2 = get_session(sid)
    assert s2.sefer_id is None
    clear_session(sid)


def test_update_session_seat():
    sid = "test_seat_x3"
    clear_session(sid)
    result = ToolResult(message="Koltuk 7 uygun.", success=True, data={"seat": 7})
    update_session_from_tool_result(sid, "validate_seat_selection", {}, result)
    assert get_session(sid).seat == "7"
    clear_session(sid)


def test_update_session_phone():
    sid = "test_phone_x4"
    clear_session(sid)
    result = ToolResult(
        message="Telefon doğrulandı: 0537 123 45 67",
        success=True,
        data={"formatted": "0537 123 45 67"},
    )
    update_session_from_tool_result(sid, "validate_phone_number", {}, result)
    assert get_session(sid).validated_phone == "0537 123 45 67"
    clear_session(sid)


def test_update_session_email():
    sid = "test_email_x5"
    clear_session(sid)
    result = ToolResult(
        message="E-posta doğrulandı: test@gmail.com",
        success=True,
        data={"email": "test@gmail.com"},
    )
    update_session_from_tool_result(sid, "validate_email_address", {}, result)
    assert get_session(sid).validated_email == "test@gmail.com"
    clear_session(sid)


def test_update_session_tc_verified():
    sid = "test_tc_x6"
    clear_session(sid)
    result = ToolResult(message="T.C. doğrulandı.", success=True)
    update_session_from_tool_result(sid, "validate_tc_number", {}, result)
    assert get_session(sid).tc_verified is True
    clear_session(sid)


def test_update_session_failure_ignored():
    """Başarısız araç sonucu oturum güncellememelidir."""
    sid = "test_fail_x7"
    clear_session(sid)
    result = ToolResult(message="Hata", success=False)
    update_session_from_tool_result(sid, "validate_seat_selection", {}, result)
    assert get_session(sid).seat is None
    clear_session(sid)


def test_update_session_get_bus_trips():
    sid = "test_trips_x8"
    clear_session(sid)
    args = {"departure_city": "Ankara", "destination_city": "Istanbul", "travel_date": "2025-06-01"}
    result = ToolResult(message="Seferler:", success=True, data={"sefer_id": 42})
    update_session_from_tool_result(sid, "get_bus_trips", args, result)
    s = get_session(sid)
    assert s.departure == "Ankara"
    assert s.destination == "Istanbul"
    assert s.travel_date == "2025-06-01"
    assert s.sefer_id == 42
    clear_session(sid)


def test_make_reservation_clears_session():
    sid = "test_pnr_clear_x9"
    s = get_session(sid)
    s.sefer_id = 1
    s.seat = "5"
    result = ToolResult(message="Başarılı! PNR Kodu: ABC12345", success=True, data={"pnr": "ABC12345"})
    update_session_from_tool_result(sid, "make_reservation", {}, result)
    # Oturum temizlenmiş olmali
    fresh = get_session(sid)
    assert fresh.sefer_id is None
    clear_session(sid)


def test_build_truth_injection_empty():
    sid = "test_truth_empty_x10"
    clear_session(sid)
    assert build_truth_injection(get_session(sid)) == ""
    clear_session(sid)


def test_build_truth_injection_full():
    sid = "test_truth_full_x11"
    clear_session(sid)
    s = get_session(sid)
    s.sefer_id = 7
    s.departure = "Bursa"
    s.destination = "Istanbul"
    s.travel_date = "2025-07-15"
    s.seat = "12"
    s.validated_phone = "0537 123 45 67"
    s.validated_email = "ali@gmail.com"
    injection = build_truth_injection(s)
    assert "STRICT_ID=7" in injection
    assert "STRICT_ROUTE=Bursa -> Istanbul" in injection
    assert "STRICT_DATE=2025-07-15" in injection
    assert "STRICT_SEAT=12" in injection
    assert "STRICT_PHONE=0537 123 45 67" in injection
    assert "STRICT_EMAIL=ali@gmail.com" in injection
    clear_session(sid)


# ─────────────────────────────────────────────
# ToolResult döndüren araç testleri
# ─────────────────────────────────────────────

from services.tools import (
    validate_seat_selection as vss,
    validate_tc_number as vtc,
    validate_phone_number as vpn,
    validate_email_address as vem,
)


def test_vss_returns_tool_result_success():
    r = vss("5", "3, 5, 7, 10")
    assert isinstance(r, ToolResult)
    assert r.success is True
    assert r.data["seat"] == 5


def test_vss_returns_tool_result_failure():
    r = vss("99", "3, 5, 7")
    assert isinstance(r, ToolResult)
    assert r.success is False


def test_vtc_returns_tool_result_valid():
    r = vtc("10000000146")
    assert isinstance(r, ToolResult)
    assert r.success is True


def test_vtc_returns_tool_result_invalid():
    r = vtc("12345")
    assert isinstance(r, ToolResult)
    assert r.success is False


def test_vpn_returns_tool_result_valid():
    r = vpn("05371234567")
    assert isinstance(r, ToolResult)
    assert r.success is True
    assert "formatted" in r.data


def test_vpn_returns_tool_result_invalid():
    r = vpn("123")
    assert isinstance(r, ToolResult)
    assert r.success is False


def test_vem_returns_tool_result_valid():
    r = vem("test@gmail.com")
    assert isinstance(r, ToolResult)
    assert r.success is True
    assert r.data["email"] == "test@gmail.com"


def test_vem_returns_tool_result_invalid():
    r = vem("not-an-email")
    assert isinstance(r, ToolResult)
    assert r.success is False


# ─────────────────────────────────────────────
# preprocessing_service tests
# ─────────────────────────────────────────────

from services.preprocessing_service import (
    preprocess_request,
    _try_seat_validation,
    _try_phone_validation,
    _try_email_validation,
)


def test_preprocess_appends_truth_injection():
    """Dolu oturum varsa truth injection metne eklenmeli."""
    sid = "test_preprocess_truth_p1"
    clear_session(sid)
    s = get_session(sid)
    s.sefer_id = 10
    s.departure = "Ankara"
    s.destination = "Istanbul"
    s.travel_date = "2025-08-01"

    result = preprocess_request("Evet", [], "tr", sid)
    assert "STRICT_ID=10" in result
    assert "STRICT_ROUTE=Ankara -> Istanbul" in result
    assert "STRICT_DATE=2025-08-01" in result
    clear_session(sid)


def test_preprocess_empty_session_no_injection():
    """Boş oturum varsa truth injection eklenmemeli."""
    sid = "test_preprocess_empty_p2"
    clear_session(sid)
    result = preprocess_request("Merhaba", [], "tr", sid)
    assert "ABSOLUTE SYSTEM TRUTH" not in result
    assert result.strip() == "Merhaba"
    clear_session(sid)


def test_preprocess_no_duplicate_injection():
    """Aynı injection iki kez eklenmemeli."""
    sid = "test_preprocess_dedup_p3"
    clear_session(sid)
    s = get_session(sid)
    s.sefer_id = 5
    s.departure = "Bursa"
    s.destination = "Izmir"

    result = preprocess_request("Tamam", [], "tr", sid)
    count = result.count("ABSOLUTE SYSTEM TRUTH")
    assert count == 1
    clear_session(sid)


def test_try_seat_validation_returns_tool_result():
    """Geçerli koltuk girişi ToolResult döndürmeli."""
    history = [
        {"role": "assistant", "content": "Boş koltuklar: 3, 7, 12"}
    ]
    result = _try_seat_validation("7", history)
    assert result is not None
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data["seat"] == 7


def test_try_seat_validation_no_seat_list():
    """Asistan koltuk listesi göstermediyse None dönmeli."""
    history = [{"role": "assistant", "content": "Merhaba, nasıl yardımcı olabilirim?"}]
    result = _try_seat_validation("5", history)
    assert result is None


def test_try_seat_validation_invalid_seat():
    """Listede olmayan koltuk seçilince None dönmeli (success=False ToolResult gizleniyor)."""
    history = [
        {"role": "assistant", "content": "Boş koltuklar: 3, 7, 12"}
    ]
    result = _try_seat_validation("99", history)
    # Başarısız ToolResult None olarak dönütürülür (preprocessing_service filtreler)
    assert result is None


def test_try_phone_validation_context_match():
    """Asistan telefon istiyorsa ve geçerli telefon girildiğinde ToolResult dönmeli."""
    history = [{"role": "assistant", "content": "Telefon numaranızı girer misiniz? 05XX formatında"}]
    result = _try_phone_validation("05371234567", history)
    assert result is not None
    assert isinstance(result, ToolResult)
    assert result.success is True


def test_try_phone_validation_wrong_context():
    """Asistan telefon istemiyorsa None dönmeli."""
    history = [{"role": "assistant", "content": "Ad soyadınızı söyler misiniz?"}]
    result = _try_phone_validation("05371234567", history)
    assert result is None


def test_try_email_validation_context_match():
    """Asistan e-posta istiyorsa ve geçerli e-posta girildiğinde ToolResult dönmeli."""
    history = [{"role": "assistant", "content": "E-posta adresinizi alır mıyım?"}]
    result = _try_email_validation("test@gmail.com", history)
    assert result is not None
    assert isinstance(result, ToolResult)
    assert result.success is True
    assert result.data["email"] == "test@gmail.com"


def test_try_email_validation_wrong_context():
    """Asistan e-posta istemiyorsa None dönmeli."""
    history = [{"role": "assistant", "content": "Kalkış şehrinizi söyleyin."}]
    result = _try_email_validation("test@gmail.com", history)
    assert result is None


def test_try_email_validation_no_email_pattern():
    """Asistan e-posta istiyor ama girdi e-posta gibi görünmüyorsa None dönmeli."""
    history = [{"role": "assistant", "content": "E-posta adresinizi alır mıyım?"}]
    result = _try_email_validation("sadece bir cümle", history)
    assert result is None
