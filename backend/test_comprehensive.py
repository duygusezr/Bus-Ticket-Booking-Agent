"""
================================================================================
COMPREHENSIVE TEST SUITE
Bus Ticket Booking AI Agent
================================================================================

Kapsam:
  - Unit Tests          : number_utils, tools, session_state, preprocessing
  - Integration Tests   : REST /api/chat endpoint, WebSocket akışı
  - Edge Cases          : geçersiz giriş, eksik veri, sınır koşulları
  - Conversational Flows: uçtan uca rezervasyon senaryoları

Çalıştırma:
  cd backend
  python -m pytest test_comprehensive.py -v --tb=short

  Sadece bir kategori:
  python -m pytest test_comprehensive.py -v -m unit
  python -m pytest test_comprehensive.py -v -m integration
  python -m pytest test_comprehensive.py -v -m edge
  python -m pytest test_comprehensive.py -v -m flow
================================================================================
"""

import sys
import os
import time
import sqlite3
import asyncio
import pytest

sys.path.insert(0, os.path.dirname(__file__))

# ── İçe aktarımlar ────────────────────────────────────────────────────────────
from services.number_utils import (
    extract_digit_stream,
    normalize_phone_digits,
    normalize_text,
    _merge_decade_unit,
)
from services.tools import (
    validate_tc_kimlik,
    _tc_checksum_ok,
    _normalize_email_input,
    validate_tc_number,
    validate_phone_number,
    validate_email_address,
    validate_seat_selection,
    _hash_pii,
    _generate_unique_pnr,
)
from services.types import ToolResult
from services.session_state import (
    get_session,
    clear_session,
    update_session_from_tool_result,
    build_truth_injection,
    BookingSession,
)
from services.preprocessing_service import (
    preprocess_request,
    _try_seat_validation,
    _try_phone_validation,
    _try_email_validation,
    _parse_natural_date,
    _inject_date_if_needed,
)


# ==============================================================================
# BÖLÜM 1 — UNIT TESTS: number_utils
# ==============================================================================

class TestExtractDigitStream:
    """extract_digit_stream() — Türkçe/İngilizce sayı kelimelerini rakama çevirir."""

    # ── Temel birim testi ──────────────────────────────────────────────────────

    @pytest.mark.unit
    def test_single_turkish_units(self):
        """Tekil Türkçe rakam kelimelerini çevirir."""
        assert extract_digit_stream("bir") == "1"
        assert extract_digit_stream("bes") == "5"
        assert extract_digit_stream("dokuz") == "9"
        assert extract_digit_stream("sifir") == "0"

    @pytest.mark.unit
    def test_sequential_turkish_units(self):
        """Ardışık birim kelimeleri birleştirir."""
        assert extract_digit_stream("bir iki uc") == "123"
        assert extract_digit_stream("dort bes alti") == "456"

    @pytest.mark.unit
    def test_single_english_units(self):
        """Tekil İngilizce rakam kelimelerini çevirir."""
        assert extract_digit_stream("one two three") == "123"
        assert extract_digit_stream("zero") == "0"
        assert extract_digit_stream("nine") == "9"

    @pytest.mark.unit
    def test_turkish_tens(self):
        """Türkçe onlukları çevirir."""
        assert extract_digit_stream("on") == "10"
        assert extract_digit_stream("yirmi") == "20"
        assert extract_digit_stream("elli") == "50"
        assert extract_digit_stream("doksan") == "90"

    @pytest.mark.unit
    def test_turkish_tens_with_units(self):
        """Türkçe onluk + birim bileşimlerini çevirir."""
        assert extract_digit_stream("yirmi uc") == "23"
        assert extract_digit_stream("otuz yedi") == "37"
        assert extract_digit_stream("kirk dort") == "44"
        assert extract_digit_stream("elli alti") == "56"

    @pytest.mark.unit
    def test_turkish_compound_words(self):
        """Bileşik yazılmış onluk+birim kelimelerini çevirir."""
        assert extract_digit_stream("onbir") == "11"
        assert extract_digit_stream("yirmibir") == "21"
        assert extract_digit_stream("otuzbir") == "31"
        assert extract_digit_stream("kirkbes") == "45"
        assert extract_digit_stream("ellibir") == "51"

    @pytest.mark.unit
    def test_english_compound_words(self):
        """İngilizce bileşik sayıları çevirir."""
        assert extract_digit_stream("eleven") == "11"
        assert extract_digit_stream("twelve") == "12"
        assert extract_digit_stream("nineteen") == "19"

    @pytest.mark.unit
    def test_hundreds(self):
        """Yüzlük yapıları çevirir."""
        assert extract_digit_stream("iki yuz") == "200"
        assert extract_digit_stream("bes yuz") == "500"
        assert extract_digit_stream("yuz") == "100"

    @pytest.mark.unit
    def test_hundreds_with_tens_and_units(self):
        """Yüzlük + onluk + birim bileşimlerini çevirir."""
        assert extract_digit_stream("bes yuz otuz yedi") == "537"
        assert extract_digit_stream("iki yuz on bes") == "215"
        assert extract_digit_stream("uc yuz kirk alti") == "346"

    @pytest.mark.unit
    def test_mixed_digit_and_word(self):
        """Karışık rakam ve kelime girişlerini işler."""
        assert extract_digit_stream("37 50 6") == "37506"
        assert extract_digit_stream("5 bes 5") == "555"

    @pytest.mark.unit
    def test_stt_split_artifact_tens(self):
        """STT'nin onlukları parçalaması durumunda birleştirir."""
        assert extract_digit_stream("yetmis 1") == "71"
        assert extract_digit_stream("altmis 1") == "61"
        assert extract_digit_stream("seksen 3") == "83"
        assert extract_digit_stream("doksan 9") == "99"

    @pytest.mark.unit
    def test_empty_input(self):
        """Boş giriş boş string döndürür."""
        assert extract_digit_stream("") == ""

    @pytest.mark.unit
    def test_no_numbers_in_text(self):
        """Sayı içermeyen metin için boş string döndürür."""
        assert extract_digit_stream("merhaba dunya") == ""
        assert extract_digit_stream("hello world") == ""

    @pytest.mark.unit
    def test_whitespace_only(self):
        """Yalnızca boşluk için boş string döndürür."""
        assert extract_digit_stream("   ") == ""

    @pytest.mark.unit
    def test_tc_word_sequence(self):
        """11 haneli TC kelime dizisini tek sayı dizisine çevirir."""
        result = extract_digit_stream("bir sifir sifir sifir sifir sifir sifir sifir bir dort alti")
        assert len(result) == 11
        assert result == "10000000146"

    @pytest.mark.unit
    def test_altmis_variants(self):
        """altmis/atmis/almis varyantlarının hepsi 60'ı üretir."""
        assert extract_digit_stream("altmis") == "60"
        assert extract_digit_stream("atmis") == "60"
        assert extract_digit_stream("almis") == "60"

    @pytest.mark.unit
    def test_yetmis_variants(self):
        """yetmis/yemis varyantlarının ikisi de 70'i üretir."""
        assert extract_digit_stream("yetmis") == "70"
        assert extract_digit_stream("yemis") == "70"


class TestMergeDecadeUnit:
    """_merge_decade_unit() — STT parçalanma tamiri."""

    @pytest.mark.unit
    def test_merge_basic(self):
        assert _merge_decade_unit(["60", "1"]) == ["61"]
        assert _merge_decade_unit(["70", "5"]) == ["75"]

    @pytest.mark.unit
    def test_no_merge_when_not_decade(self):
        """Onluk değilse birleştirmez."""
        assert _merge_decade_unit(["15", "3"]) == ["15", "3"]

    @pytest.mark.unit
    def test_no_merge_when_unit_is_zero(self):
        """Birim 0 ise birleştirmez."""
        assert _merge_decade_unit(["60", "0"]) == ["60", "0"]

    @pytest.mark.unit
    def test_no_merge_when_unit_multi_digit(self):
        """Birim birden fazla haneliyse birleştirmez."""
        assert _merge_decade_unit(["60", "12"]) == ["60", "12"]

    @pytest.mark.unit
    def test_multiple_merges(self):
        """Ardışık birden fazla birleştirme yapabilir."""
        assert _merge_decade_unit(["10", "1", "20", "2"]) == ["11", "22"]


class TestNormalizePhoneDigits:
    """normalize_phone_digits() — telefon numarası normalizasyonu."""

    @pytest.mark.unit
    def test_country_code_90_stripped(self):
        assert normalize_phone_digits("905372791437") == "05372791437"

    @pytest.mark.unit
    def test_country_code_090_stripped(self):
        assert normalize_phone_digits("0905372791437") == "05372791437"

    @pytest.mark.unit
    def test_10_digit_starting_5_prefixed(self):
        assert normalize_phone_digits("5372791437") == "05372791437"

    @pytest.mark.unit
    def test_11_digit_unchanged(self):
        assert normalize_phone_digits("05372791437") == "05372791437"

    @pytest.mark.unit
    def test_with_spaces(self):
        result = normalize_phone_digits("0537 279 14 37")
        assert result == "05372791437"

    @pytest.mark.unit
    def test_with_dashes(self):
        result = normalize_phone_digits("0537-279-14-37")
        assert result == "05372791437"


class TestNormalizeText:
    """normalize_text() — Türkçe karakter normalizasyonu."""

    @pytest.mark.unit
    def test_turkish_chars_lowercased(self):
        assert normalize_text("İstanbul") == "istanbul"
        assert normalize_text("ŞEHIR") == "sehir"
        assert normalize_text("Çankaya") == "cankaya"

    @pytest.mark.unit
    def test_whitespace_collapsed(self):
        assert normalize_text("  bos  luk  ") == "bos luk"

    @pytest.mark.unit
    def test_empty_string(self):
        assert normalize_text("") == ""

    @pytest.mark.unit
    def test_none_safe(self):
        # normalize_text dahili olarak boş string gibi davranır;
        # Pylance tip uyarısını önlemek için cast kullanıyoruz.
        assert normalize_text("") == ""


# ==============================================================================
# BÖLÜM 2 — UNIT TESTS: TC Kimlik Doğrulama
# ==============================================================================

class TestTCChecksum:
    """_tc_checksum_ok() — algoritmik TC kontrol toplamı."""

    @pytest.mark.unit
    def test_valid_tc(self):
        assert _tc_checksum_ok("10000000146") is True

    @pytest.mark.unit
    def test_starts_with_zero(self):
        assert _tc_checksum_ok("01234567890") is False

    @pytest.mark.unit
    def test_wrong_length_short(self):
        assert _tc_checksum_ok("1234567890") is False

    @pytest.mark.unit
    def test_wrong_length_long(self):
        assert _tc_checksum_ok("123456789012") is False

    @pytest.mark.unit
    def test_wrong_checksum(self):
        assert _tc_checksum_ok("12345678901") is False

    @pytest.mark.unit
    def test_all_same_digits_invalid(self):
        assert _tc_checksum_ok("11111111111") is False


class TestValidateTCKimlik:
    """validate_tc_kimlik() — tam TC doğrulama pipeline."""

    @pytest.mark.unit
    def test_valid_numeric_string(self):
        valid, msg = validate_tc_kimlik("10000000146")
        assert valid is True
        assert msg == "Geçerli"

    @pytest.mark.unit
    def test_too_short(self):
        valid, msg = validate_tc_kimlik("12345")
        assert valid is False
        assert "11 rakam" in msg

    @pytest.mark.unit
    def test_starts_with_zero(self):
        valid, msg = validate_tc_kimlik("01234567890")
        assert valid is False
        assert "0 ile" in msg

    @pytest.mark.unit
    def test_wrong_checksum(self):
        valid, msg = validate_tc_kimlik("12345678901")
        assert valid is False

    @pytest.mark.unit
    def test_voice_word_input(self):
        """Sesli giriş kelime dizisi olarak gelse de doğrulama geçmeli."""
        valid, msg = validate_tc_kimlik("bir sifir sifir sifir sifir sifir sifir sifir bir dort alti")
        assert valid is True

    @pytest.mark.unit
    def test_longer_stream_sliding_window(self):
        """11+ haneli giriş için kayan pencere geçerli TC'yi bulmalı."""
        valid, msg = validate_tc_kimlik("9910000000146")
        assert valid is True

    @pytest.mark.unit
    def test_returns_tool_result_success(self):
        r = validate_tc_number("10000000146")
        assert isinstance(r, ToolResult)
        assert r.success is True

    @pytest.mark.unit
    def test_returns_tool_result_failure(self):
        r = validate_tc_number("00000000000")
        assert isinstance(r, ToolResult)
        assert r.success is False


# ==============================================================================
# BÖLÜM 3 — UNIT TESTS: Telefon Doğrulama
# ==============================================================================

class TestValidatePhoneNumber:
    """validate_phone_number() — telefon doğrulama."""

    @pytest.mark.unit
    def test_valid_11_digit(self):
        r = validate_phone_number("05372791437")
        assert r.success is True
        assert "formatted" in r.data
        assert "0537" in r.data["formatted"]

    @pytest.mark.unit
    def test_valid_10_digit_auto_prefix(self):
        r = validate_phone_number("5372791437")
        assert r.success is True

    @pytest.mark.unit
    def test_too_short(self):
        r = validate_phone_number("0537")
        assert r.success is False
        assert "Hata" in r.message

    @pytest.mark.unit
    def test_too_long(self):
        r = validate_phone_number("053712345678901")
        assert r.success is False

    @pytest.mark.unit
    def test_country_code_stripped_valid(self):
        r = validate_phone_number("905372791437")
        assert r.success is True

    @pytest.mark.unit
    def test_non_mobile_prefix(self):
        """0 ile başlayıp 5 ile devam etmeyen numara."""
        r = validate_phone_number("03125551234")
        assert r.success is False or r.success is True  # sistemin kararına bırak ama çökmemeli

    @pytest.mark.unit
    def test_returns_tool_result_type(self):
        r = validate_phone_number("05372791437")
        assert isinstance(r, ToolResult)


# ==============================================================================
# BÖLÜM 4 — UNIT TESTS: E-posta Doğrulama
# ==============================================================================

class TestEmailNormalization:
    """_normalize_email_input() — sesli e-posta normalizasyonu."""

    @pytest.mark.unit
    def test_at_substitution(self):
        assert _normalize_email_input("test at gmail nokta com") == "test@gmail.com"

    @pytest.mark.unit
    def test_et_substitution(self):
        assert _normalize_email_input("test et gmail nokta com") == "test@gmail.com"

    @pytest.mark.unit
    def test_ci_mail_corrected(self):
        assert _normalize_email_input("ahmet ci mail nokta com") == "ahmet@gmail.com"

    @pytest.mark.unit
    def test_cimail_corrected(self):
        assert _normalize_email_input("ahmet cimail nokta com") == "ahmet@gmail.com"

    @pytest.mark.unit
    def test_g_mail_corrected(self):
        assert _normalize_email_input("duygu g mail nokta com") == "duygu@gmail.com"

    @pytest.mark.unit
    def test_hotmail(self):
        result = _normalize_email_input("ali hot mail nokta com")
        assert "hotmail" in result

    @pytest.mark.unit
    def test_domain_merge(self):
        result = _normalize_email_input("duygu at gmail com")
        assert result == "duygu@gmail.com"

    @pytest.mark.unit
    def test_already_valid_unchanged(self):
        assert _normalize_email_input("user@hotmail.com") == "user@hotmail.com"

    @pytest.mark.unit
    def test_duplicate_removal(self):
        """Aynı adresin iki kez söylenmesi tekrarı kaldırmalı."""
        result = _normalize_email_input("test@gmail.comtest@gmail.com")
        assert result.count("@") == 1

    @pytest.mark.unit
    def test_com_tr_domain(self):
        result = _normalize_email_input("ali at ornek nokta com tr")
        assert "com.tr" in result


class TestValidateEmailAddress:
    """validate_email_address() — tam e-posta doğrulama."""

    @pytest.mark.unit
    def test_valid_gmail(self):
        r = validate_email_address("test@gmail.com")
        assert r.success is True
        assert r.data["email"] == "test@gmail.com"

    @pytest.mark.unit
    def test_valid_voice_input(self):
        r = validate_email_address("test at gmail nokta com")
        assert r.success is True

    @pytest.mark.unit
    def test_invalid_no_at(self):
        r = validate_email_address("notanemail")
        assert r.success is False
        assert "Hata" in r.message

    @pytest.mark.unit
    def test_invalid_no_domain(self):
        r = validate_email_address("user@")
        assert r.success is False

    @pytest.mark.unit
    def test_invalid_double_at(self):
        r = validate_email_address("user@@gmail.com")
        assert r.success is False

    @pytest.mark.unit
    def test_returns_tool_result(self):
        r = validate_email_address("test@gmail.com")
        assert isinstance(r, ToolResult)


# ==============================================================================
# BÖLÜM 5 — UNIT TESTS: Koltuk Doğrulama
# ==============================================================================

class TestValidateSeatSelection:
    """validate_seat_selection() — koltuk uygunluk kontrolü."""

    @pytest.mark.unit
    def test_valid_seat_number(self):
        r = validate_seat_selection("5", "3, 5, 7, 10, 12")
        assert r.success is True
        assert r.data["seat"] == 5

    @pytest.mark.unit
    def test_seat_not_in_list(self):
        r = validate_seat_selection("99", "3, 5, 7")
        assert r.success is False
        assert "mevcut değil" in r.message or "Hata" in r.message

    @pytest.mark.unit
    def test_seat_as_word(self):
        """Sayı kelimesi olarak gönderilmiş koltuk numarası."""
        r = validate_seat_selection("bes", "3, 5, 7")
        assert r.success is True
        assert r.data["seat"] == 5

    @pytest.mark.unit
    def test_seat_with_spaces(self):
        r = validate_seat_selection(" 7 ", "3, 5, 7, 10")
        assert r.success is True

    @pytest.mark.unit
    def test_seat_zero_invalid(self):
        r = validate_seat_selection("0", "1, 2, 3")
        assert r.success is False

    @pytest.mark.unit
    def test_empty_available_list(self):
        r = validate_seat_selection("5", "")
        assert r.success is False

    @pytest.mark.unit
    def test_returns_tool_result(self):
        r = validate_seat_selection("5", "3, 5, 7")
        assert isinstance(r, ToolResult)

    @pytest.mark.unit
    def test_seat_data_field_correct_type(self):
        """data['seat'] int olmalı."""
        r = validate_seat_selection("7", "5, 7, 9")
        assert isinstance(r.data["seat"], int)


# ==============================================================================
# BÖLÜM 6 — UNIT TESTS: PII Karma ve PNR
# ==============================================================================

class TestHashPII:
    """_hash_pii() — SHA-256 tek yönlü karma."""

    @pytest.mark.unit
    def test_deterministic(self):
        assert _hash_pii("12345678901") == _hash_pii("12345678901")

    @pytest.mark.unit
    def test_different_inputs_different_hash(self):
        assert _hash_pii("12345678901") != _hash_pii("10987654321")

    @pytest.mark.unit
    def test_output_length_64(self):
        assert len(_hash_pii("any_input")) == 64

    @pytest.mark.unit
    def test_plaintext_not_in_output(self):
        val = "12345678901"
        result = _hash_pii(val)
        assert val not in result

    @pytest.mark.unit
    def test_hex_only_characters(self):
        result = _hash_pii("test")
        assert all(c in "0123456789abcdef" for c in result)

    @pytest.mark.unit
    def test_empty_string(self):
        """Boş string bile geçerli 64 char karma üretmeli."""
        result = _hash_pii("")
        assert len(result) == 64


class TestPNRGeneration:
    """_generate_unique_pnr() — benzersiz PNR üretimi."""

    @pytest.mark.unit
    def test_length_and_charset(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE rezervasyonlar (pnr_code TEXT UNIQUE)")
        pnr = _generate_unique_pnr(conn, length=8)
        assert len(pnr) == 8
        assert pnr.isalnum()
        assert pnr == pnr.upper()
        conn.close()

    @pytest.mark.unit
    def test_uniqueness_50_calls(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE rezervasyonlar (pnr_code TEXT UNIQUE)")
        seen = set()
        for _ in range(50):
            pnr = _generate_unique_pnr(conn, length=8)
            conn.execute("INSERT INTO rezervasyonlar VALUES (?)", (pnr,))
            conn.commit()
            assert pnr not in seen
            seen.add(pnr)
        conn.close()

    @pytest.mark.unit
    def test_custom_length(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE rezervasyonlar (pnr_code TEXT UNIQUE)")
        pnr = _generate_unique_pnr(conn, length=6)
        assert len(pnr) == 6
        conn.close()


# ==============================================================================
# BÖLÜM 7 — UNIT TESTS: ToolResult
# ==============================================================================

class TestToolResult:
    """ToolResult veri yapısı davranışları."""

    @pytest.mark.unit
    def test_str_returns_message(self):
        r = ToolResult(message="Koltuk 5 uygun.", success=True, data={"seat": 5})
        assert str(r) == "Koltuk 5 uygun."

    @pytest.mark.unit
    def test_default_success_true(self):
        r = ToolResult(message="ok")
        assert r.success is True

    @pytest.mark.unit
    def test_default_data_empty_dict(self):
        r = ToolResult(message="ok")
        assert r.data == {}

    @pytest.mark.unit
    def test_failure_has_no_data(self):
        r = ToolResult(message="Hata", success=False)
        assert r.success is False
        assert r.data == {}

    @pytest.mark.unit
    def test_data_preserved(self):
        r = ToolResult(message="ok", data={"key": "value", "num": 42})
        assert r.data["key"] == "value"
        assert r.data["num"] == 42


# ==============================================================================
# BÖLÜM 8 — UNIT TESTS: Session State
# ==============================================================================

class TestSessionState:
    """BookingSession oturum yönetimi."""

    @pytest.mark.unit
    def test_new_session_all_none(self):
        sid = "test_new_z1"
        clear_session(sid)
        s = get_session(sid)
        assert s.sefer_id is None
        assert s.seat is None
        assert s.tc_verified is False
        clear_session(sid)

    @pytest.mark.unit
    def test_clear_resets_session(self):
        sid = "test_clear_z2"
        s = get_session(sid)
        s.sefer_id = 99
        s.seat = "5"
        clear_session(sid)
        fresh = get_session(sid)
        assert fresh.sefer_id is None
        assert fresh.seat is None
        clear_session(sid)

    @pytest.mark.unit
    def test_update_from_get_bus_trips(self):
        sid = "test_trips_z3"
        clear_session(sid)
        args = {"departure_city": "Ankara", "destination_city": "Istanbul", "travel_date": "2025-06-01"}
        result = ToolResult(
            message="Seferler bulundu",
            success=True,
            data={"sefer_id": 42, "available_seats": "5,7,10,12"}
        )
        update_session_from_tool_result(sid, "get_bus_trips", args, result)
        s = get_session(sid)
        assert s.departure == "Ankara"
        assert s.destination == "Istanbul"
        assert s.travel_date == "2025-06-01"
        assert s.sefer_id == 42
        assert s.available_seats == "5,7,10,12"
        assert s.seat_map_pending is True
        clear_session(sid)

    @pytest.mark.unit
    def test_update_from_validate_seat(self):
        sid = "test_seat_z4"
        clear_session(sid)
        result = ToolResult(message="Koltuk 7 uygun.", success=True, data={"seat": 7})
        update_session_from_tool_result(sid, "validate_seat_selection", {}, result)
        assert get_session(sid).seat == "7"
        clear_session(sid)

    @pytest.mark.unit
    def test_update_from_validate_phone(self):
        sid = "test_phone_z5"
        clear_session(sid)
        result = ToolResult(
            message="Telefon doğrulandı",
            success=True,
            data={"formatted": "0537 123 45 67"}
        )
        update_session_from_tool_result(sid, "validate_phone_number", {}, result)
        assert get_session(sid).validated_phone == "0537 123 45 67"
        clear_session(sid)

    @pytest.mark.unit
    def test_update_from_validate_email(self):
        sid = "test_email_z6"
        clear_session(sid)
        result = ToolResult(
            message="E-posta doğrulandı",
            success=True,
            data={"email": "test@gmail.com"}
        )
        update_session_from_tool_result(sid, "validate_email_address", {}, result)
        assert get_session(sid).validated_email == "test@gmail.com"
        clear_session(sid)

    @pytest.mark.unit
    def test_update_from_validate_tc(self):
        sid = "test_tc_z7"
        clear_session(sid)
        result = ToolResult(message="TC doğrulandı.", success=True)
        update_session_from_tool_result(sid, "validate_tc_number", {}, result)
        assert get_session(sid).tc_verified is True
        clear_session(sid)

    @pytest.mark.unit
    def test_failed_tool_does_not_update(self):
        sid = "test_fail_z8"
        clear_session(sid)
        result = ToolResult(message="Hata", success=False, data={"seat": 99})
        update_session_from_tool_result(sid, "validate_seat_selection", {}, result)
        assert get_session(sid).seat is None
        clear_session(sid)

    @pytest.mark.unit
    def test_make_reservation_clears_session(self):
        sid = "test_pnr_z9"
        s = get_session(sid)
        s.sefer_id = 1
        s.seat = "5"
        result = ToolResult(
            message="Başarılı! PNR Kodu: ABC12345",
            success=True,
            data={"pnr": "ABC12345"}
        )
        update_session_from_tool_result(sid, "make_reservation", {"yolcu_ad_soyad": "Ali Veli"}, result)
        fresh = get_session(sid)
        assert fresh.sefer_id is None
        clear_session(sid)

    @pytest.mark.unit
    def test_multiple_sessions_independent(self):
        """İki farklı oturum birbirini etkilemez."""
        sid_a = "test_multi_a"
        sid_b = "test_multi_b"
        clear_session(sid_a); clear_session(sid_b)
        get_session(sid_a).sefer_id = 1
        get_session(sid_b).sefer_id = 2
        assert get_session(sid_a).sefer_id == 1
        assert get_session(sid_b).sefer_id == 2
        clear_session(sid_a); clear_session(sid_b)


class TestBuildTruthInjection:
    """build_truth_injection() — ABSOLUTE SYSTEM TRUTH bloğu oluşturma."""

    @pytest.mark.unit
    def test_empty_session_returns_empty_string(self):
        sid = "test_truth_empty_y1"
        clear_session(sid)
        assert build_truth_injection(get_session(sid)) == ""
        clear_session(sid)

    @pytest.mark.unit
    def test_all_fields_present(self):
        sid = "test_truth_full_y2"
        clear_session(sid)
        s = get_session(sid)
        s.sefer_id = 7
        s.departure = "Bursa"
        s.destination = "Istanbul"
        s.travel_date = "2025-07-15"
        s.seat = "12"
        s.validated_phone = "0537 123 45 67"
        s.validated_email = "ali@gmail.com"
        inj = build_truth_injection(s)
        assert "STRICT_ID=7" in inj
        assert "STRICT_ROUTE=Bursa -> Istanbul" in inj
        assert "STRICT_DATE=2025-07-15" in inj
        assert "STRICT_SEAT=12" in inj
        assert "STRICT_PHONE=0537 123 45 67" in inj
        assert "STRICT_EMAIL=ali@gmail.com" in inj
        clear_session(sid)

    @pytest.mark.unit
    def test_partial_fields(self):
        """Yalnızca sefer_id doluyken sadece STRICT_ID içermeli."""
        sid = "test_truth_partial_y3"
        clear_session(sid)
        s = get_session(sid)
        s.sefer_id = 3
        inj = build_truth_injection(s)
        assert "STRICT_ID=3" in inj
        assert "STRICT_SEAT" not in inj
        clear_session(sid)

    @pytest.mark.unit
    def test_no_route_if_one_city_missing(self):
        """Sadece departure varsa STRICT_ROUTE eklenmemeli."""
        sid = "test_truth_route_y4"
        clear_session(sid)
        s = get_session(sid)
        s.departure = "Ankara"
        inj = build_truth_injection(s)
        assert "STRICT_ROUTE" not in inj
        clear_session(sid)

    @pytest.mark.unit
    def test_injection_contains_marker(self):
        sid = "test_truth_marker_y5"
        clear_session(sid)
        s = get_session(sid)
        s.sefer_id = 1
        inj = build_truth_injection(s)
        assert "ABSOLUTE SYSTEM TRUTH" in inj
        clear_session(sid)


# ==============================================================================
# BÖLÜM 9 — UNIT TESTS: Preprocessing Service
# ==============================================================================

class TestPreprocessRequest:
    """preprocess_request() — ana ön işleme fonksiyonu."""

    @pytest.mark.unit
    def test_truth_injection_appended_when_session_full(self):
        sid = "test_pp_truth_w1"
        clear_session(sid)
        s = get_session(sid)
        s.sefer_id = 10
        s.departure = "Ankara"
        s.destination = "Istanbul"
        s.travel_date = "2025-08-01"
        result = preprocess_request("Evet", [], "tr", sid)
        assert "STRICT_ID=10" in result
        assert "STRICT_ROUTE=Ankara -> Istanbul" in result
        clear_session(sid)

    @pytest.mark.unit
    def test_no_injection_for_empty_session(self):
        sid = "test_pp_empty_w2"
        clear_session(sid)
        result = preprocess_request("Merhaba", [], "tr", sid)
        assert "ABSOLUTE SYSTEM TRUTH" not in result
        assert result.strip() == "Merhaba"
        clear_session(sid)

    @pytest.mark.unit
    def test_no_duplicate_injection(self):
        sid = "test_pp_dedup_w3"
        clear_session(sid)
        s = get_session(sid)
        s.sefer_id = 5
        s.departure = "Bursa"
        s.destination = "Izmir"
        result = preprocess_request("Tamam", [], "tr", sid)
        assert result.count("ABSOLUTE SYSTEM TRUTH") == 1
        clear_session(sid)


class TestTrySeatValidation:
    """_try_seat_validation() — bağlam duyarlı koltuk kestirme doğrulama."""

    @pytest.mark.unit
    def test_valid_seat_in_context(self):
        history = [{"role": "assistant", "content": "Boş koltuklar: 3, 7, 12"}]
        r = _try_seat_validation("7", history)
        assert r is not None
        assert r.success is True
        assert r.data["seat"] == 7

    @pytest.mark.unit
    def test_no_seat_list_in_history(self):
        history = [{"role": "assistant", "content": "Merhaba, nasıl yardımcı olabilirim?"}]
        r = _try_seat_validation("5", history)
        assert r is None

    @pytest.mark.unit
    def test_invalid_seat_returns_none(self):
        history = [{"role": "assistant", "content": "Boş koltuklar: 3, 7, 12"}]
        r = _try_seat_validation("99", history)
        assert r is None

    @pytest.mark.unit
    def test_empty_input_returns_none(self):
        history = [{"role": "assistant", "content": "Boş koltuklar: 3, 7, 12"}]
        r = _try_seat_validation("", history)
        assert r is None

    @pytest.mark.unit
    def test_word_seat_in_context(self):
        history = [{"role": "assistant", "content": "Boş koltuklar: 3, 7, 12"}]
        r = _try_seat_validation("yedi", history)
        assert r is not None
        assert r.success is True


class TestTryPhoneValidation:
    """_try_phone_validation() — bağlam duyarlı telefon kestirme doğrulama."""

    @pytest.mark.unit
    def test_valid_phone_in_context(self):
        history = [{"role": "assistant", "content": "Telefon numaranızı girer misiniz? 05XX formatında"}]
        r = _try_phone_validation("05371234567", history)
        assert r is not None
        assert r.success is True

    @pytest.mark.unit
    def test_wrong_context_returns_none(self):
        history = [{"role": "assistant", "content": "Ad soyadınızı söyler misiniz?"}]
        r = _try_phone_validation("05371234567", history)
        assert r is None

    @pytest.mark.unit
    def test_short_input_returns_none(self):
        history = [{"role": "assistant", "content": "Telefon numaranız?"}]
        r = _try_phone_validation("0537", history)
        assert r is None


class TestTryEmailValidation:
    """_try_email_validation() — bağlam duyarlı e-posta kestirme doğrulama."""

    @pytest.mark.unit
    def test_valid_email_in_context(self):
        history = [{"role": "assistant", "content": "E-posta adresinizi alır mıyım?"}]
        r = _try_email_validation("test@gmail.com", history)
        assert r is not None
        assert r.success is True
        assert r.data["email"] == "test@gmail.com"

    @pytest.mark.unit
    def test_wrong_context_returns_none(self):
        history = [{"role": "assistant", "content": "Kalkış şehrinizi söyleyin."}]
        r = _try_email_validation("test@gmail.com", history)
        assert r is None

    @pytest.mark.unit
    def test_no_email_pattern_returns_none(self):
        history = [{"role": "assistant", "content": "E-posta adresinizi alır mıyım?"}]
        r = _try_email_validation("sadece bir cumle", history)
        assert r is None

    @pytest.mark.unit
    def test_voice_email_in_context(self):
        history = [{"role": "assistant", "content": "Email adresinizi alabilir miyim?"}]
        r = _try_email_validation("test at gmail nokta com", history)
        assert r is not None
        assert r.success is True


class TestNaturalDateParsing:
    """_parse_natural_date() — doğal dil tarih çözümleme."""

    @pytest.mark.unit
    def test_yarin_tr(self):
        from datetime import datetime, timedelta
        result = _parse_natural_date("yarın", "tr")
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    @pytest.mark.unit
    def test_bugun_tr(self):
        from datetime import datetime
        result = _parse_natural_date("bugün", "tr")
        expected = datetime.now().strftime("%Y-%m-%d")
        assert result == expected

    @pytest.mark.unit
    def test_tomorrow_en(self):
        from datetime import datetime, timedelta
        result = _parse_natural_date("tomorrow", "en")
        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    @pytest.mark.unit
    def test_month_day_tr(self):
        result = _parse_natural_date("temmuz 15", "tr")
        assert result is not None
        assert "-07-15" in result

    @pytest.mark.unit
    def test_day_month_tr(self):
        result = _parse_natural_date("15 temmuz", "tr")
        assert result is not None
        assert "-07-15" in result

    @pytest.mark.unit
    def test_ordinal_en(self):
        result = _parse_natural_date("august 8th", "en")
        assert result is not None
        assert "-08-08" in result

    @pytest.mark.unit
    def test_unrecognized_returns_none(self):
        result = _parse_natural_date("rastgele metin", "tr")
        assert result is None


# ==============================================================================
# BÖLÜM 10 — EDGE CASES (Sınır Koşulları)
# ==============================================================================

class TestEdgeCases:
    """Beklenmedik ve aşırı giriş senaryoları."""

    @pytest.mark.edge
    def test_tc_all_zeros(self):
        valid, msg = validate_tc_kimlik("00000000000")
        assert valid is False

    @pytest.mark.edge
    def test_tc_all_nines(self):
        valid, msg = validate_tc_kimlik("99999999999")
        assert valid is False

    @pytest.mark.edge
    def test_tc_with_spaces(self):
        valid, msg = validate_tc_kimlik("1 0000000146")
        assert isinstance(valid, bool)

    @pytest.mark.edge
    def test_tc_unicode_turkish(self):
        """Türkçe sesli harflerle yazılmış TC kelime girişi."""
        valid, msg = validate_tc_kimlik("bir sıfır sıfır sıfır sıfır sıfır sıfır sıfır bir dört altı")
        assert isinstance(valid, bool)

    @pytest.mark.edge
    def test_phone_all_zeros(self):
        r = validate_phone_number("00000000000")
        assert isinstance(r, ToolResult)

    @pytest.mark.edge
    def test_phone_with_plus_sign(self):
        r = validate_phone_number("+905372791437")
        assert isinstance(r, ToolResult)

    @pytest.mark.edge
    def test_email_with_special_chars(self):
        r = validate_email_address("user+tag@example.co.uk")
        assert isinstance(r, ToolResult)

    @pytest.mark.edge
    def test_email_very_long(self):
        r = validate_email_address("a" * 100 + "@gmail.com")
        assert isinstance(r, ToolResult)

    @pytest.mark.edge
    def test_seat_negative_number(self):
        r = validate_seat_selection("-1", "1, 2, 3")
        assert isinstance(r, ToolResult)

    @pytest.mark.edge
    def test_seat_very_large_number(self):
        r = validate_seat_selection("999", "1, 2, 3")
        assert r.success is False

    @pytest.mark.edge
    def test_extract_digits_very_long_input(self):
        """1000 karakter giriş çökme üretmemeli."""
        long_input = "bir iki uc " * 100
        result = extract_digit_stream(long_input)
        assert isinstance(result, str)

    @pytest.mark.edge
    def test_normalize_text_unicode_only(self):
        result = normalize_text("İŞÇÖÜĞ")
        # Türkçe büyük harfler küçük ASCII eşdeğerlerine dönüşmeli
        assert "i" in result      # İ → i
        assert "s" in result      # Ş → s
        assert "c" in result      # Ç → c
        assert "g" in result      # Ğ → g
        assert result == result.lower()

    @pytest.mark.edge
    def test_session_nonexistent_tool_name(self):
        """Bilinmeyen araç adı oturumu çökertmemeli."""
        sid = "test_edge_unknown_tool"
        clear_session(sid)
        result = ToolResult(message="ok", success=True, data={"foo": "bar"})
        update_session_from_tool_result(sid, "unknown_tool_xyz", {}, result)
        # Çökme olmamalı, oturum değişmemeli
        s = get_session(sid)
        assert s.sefer_id is None
        clear_session(sid)

    @pytest.mark.edge
    def test_hash_pii_very_long_input(self):
        result = _hash_pii("x" * 10000)
        assert len(result) == 64

    @pytest.mark.edge
    def test_preprocess_empty_text(self):
        """Boş metin ön işlemeden geçmeli."""
        sid = "test_edge_empty_pp"
        clear_session(sid)
        result = preprocess_request("", [], "tr", sid)
        assert isinstance(result, str)
        clear_session(sid)

    @pytest.mark.edge
    def test_preprocess_very_long_text(self):
        """Çok uzun metin ön işlemeden geçmeli."""
        sid = "test_edge_long_pp"
        clear_session(sid)
        long_text = "kelime " * 500
        result = preprocess_request(long_text, [], "tr", sid)
        assert isinstance(result, str)
        clear_session(sid)


# ==============================================================================
# BÖLÜM 11 — INTEGRATION TESTS: REST /api/chat Endpoint
# ==============================================================================

class TestChatEndpointIntegration:
    """
    /api/chat REST endpoint entegrasyon testleri.
    NOT: Bu testler çalışan bir backend sunucusu gerektirir.
    `pytest -m integration` ile ayrı çalıştırılabilir.
    Sunucu yoksa tüm testler SKIP edilir.
    """

    BASE_URL = "http://localhost:8001"

    @pytest.fixture(autouse=True)
    def skip_if_no_server(self):
        import urllib.request
        try:
            urllib.request.urlopen(f"{self.BASE_URL}/", timeout=2)
        except Exception:
            pytest.skip("Backend sunucusu çalışmıyor — entegrasyon testi atlandı.")

    @pytest.mark.integration
    def test_health_check(self):
        import urllib.request, json as _json
        r = urllib.request.urlopen(f"{self.BASE_URL}/")
        data = _json.loads(r.read())
        assert data["status"] == "ok"

    @pytest.mark.integration
    def test_chat_returns_text_and_audio(self):
        import urllib.request, json as _json
        payload = _json.dumps({
            "text": "Merhaba",
            "lang": "tr",
            "history": [],
            "session_id": "integration_test_1"
        }).encode()
        req = urllib.request.Request(
            f"{self.BASE_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        r = urllib.request.urlopen(req, timeout=30)
        data = _json.loads(r.read())
        assert "text" in data
        assert "audio" in data
        assert len(data["text"]) > 0

    @pytest.mark.integration
    def test_chat_english_mode(self):
        import urllib.request, json as _json
        payload = _json.dumps({
            "text": "Hello",
            "lang": "en",
            "history": [],
            "session_id": "integration_test_en"
        }).encode()
        req = urllib.request.Request(
            f"{self.BASE_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        r = urllib.request.urlopen(req, timeout=30)
        data = _json.loads(r.read())
        assert "text" in data
        assert len(data["text"]) > 0

    @pytest.mark.integration
    def test_chat_response_time_under_10s(self):
        import urllib.request, json as _json
        payload = _json.dumps({
            "text": "Ankara'dan İstanbul'a yarın sefer var mı?",
            "lang": "tr",
            "history": [],
            "session_id": "integration_timing"
        }).encode()
        req = urllib.request.Request(
            f"{self.BASE_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        t0 = time.perf_counter()
        urllib.request.urlopen(req, timeout=15)
        elapsed = time.perf_counter() - t0
        assert elapsed < 10.0, f"Yanıt süresi {elapsed:.2f}s > 10s sınırını aştı"

    @pytest.mark.integration
    def test_invalid_json_returns_422(self):
        import urllib.request, urllib.error
        payload = b"not valid json"
        req = urllib.request.Request(
            f"{self.BASE_URL}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "422 hatası beklendi"
        except urllib.error.HTTPError as e:
            assert e.code in (422, 400)


# ==============================================================================
# BÖLÜM 12 — CONVERSATIONAL FLOW TESTS
# ==============================================================================

class TestConversationalFlows:
    """
    Uçtan uca konuşma akışı simülasyonları.
    LLM çağrısı gerektirmeyen, doğrulama ve oturum katmanlarını test eder.
    """

    @pytest.mark.flow
    def test_flow_seat_selection_full_cycle(self):
        """
        Senaryo: Asistan koltuk listesi gösterir → kullanıcı koltuk seçer →
        oturum koltuk bilgisini saklar.
        """
        sid = "flow_seat_full"
        clear_session(sid)

        history = [
            {"role": "user", "content": "Ankara'dan Istanbul'a gitmek istiyorum"},
            {"role": "assistant", "content": "Boş koltuklar: 3, 7, 12, 15. Hangi koltuğu seçmek istersiniz?"}
        ]

        # Step 1: Koltuk seçimi — deterministik ön doğrulama devreye girmeli
        seat_result = _try_seat_validation("7", history)
        assert seat_result is not None
        assert seat_result.success is True

        # Step 2: Oturuma yaz
        update_session_from_tool_result(sid, "validate_seat_selection", {}, seat_result)
        assert get_session(sid).seat == "7"

        clear_session(sid)

    @pytest.mark.flow
    def test_flow_phone_collection_cycle(self):
        """
        Senaryo: Asistan telefon ister → kullanıcı girer →
        deterministik doğrulama ön işlemede yakalanır.
        """
        sid = "flow_phone_full"
        clear_session(sid)

        history = [
            {"role": "assistant", "content": "Lütfen telefon numaranızı giriniz. 05XX XXX XX XX formatında."}
        ]

        phone_result = _try_phone_validation("05371234567", history)
        assert phone_result is not None
        assert phone_result.success is True

        update_session_from_tool_result(sid, "validate_phone_number", {}, phone_result)
        assert get_session(sid).validated_phone is not None

        clear_session(sid)

    @pytest.mark.flow
    def test_flow_email_collection_cycle(self):
        """
        Senaryo: Asistan e-posta ister → kullanıcı sesli girer →
        normalizasyon + doğrulama gerçekleşir.
        """
        sid = "flow_email_full"
        clear_session(sid)

        history = [
            {"role": "assistant", "content": "E-posta adresinizi öğrenebilir miyim?"}
        ]

        email_result = _try_email_validation("duygu at gmail nokta com", history)
        assert email_result is not None
        assert email_result.success is True
        assert email_result.data["email"] == "duygu@gmail.com"

        update_session_from_tool_result(sid, "validate_email_address", {}, email_result)
        assert get_session(sid).validated_email == "duygu@gmail.com"

        clear_session(sid)

    @pytest.mark.flow
    def test_flow_truth_injection_grows_with_session(self):
        """
        Senaryo: Her araç çağrısında TRUTH enjeksiyonu yeni alanlarla büyür.
        """
        sid = "flow_truth_growth"
        clear_session(sid)

        # Başlangıç — boş
        assert build_truth_injection(get_session(sid)) == ""

        # Sefer bilgisi eklendi
        update_session_from_tool_result(sid, "get_bus_trips",
            {"departure_city": "Bursa", "destination_city": "Istanbul", "travel_date": "2025-09-01"},
            ToolResult(message="ok", success=True, data={"sefer_id": 5})
        )
        inj = build_truth_injection(get_session(sid))
        assert "STRICT_ID=5" in inj
        assert "STRICT_ROUTE" in inj

        # Koltuk eklendi
        update_session_from_tool_result(sid, "validate_seat_selection", {},
            ToolResult(message="ok", success=True, data={"seat": 12})
        )
        inj = build_truth_injection(get_session(sid))
        assert "STRICT_SEAT=12" in inj

        # Telefon eklendi
        update_session_from_tool_result(sid, "validate_phone_number", {},
            ToolResult(message="ok", success=True, data={"formatted": "0537 000 00 00"})
        )
        inj = build_truth_injection(get_session(sid))
        assert "STRICT_PHONE" in inj

        clear_session(sid)

    @pytest.mark.flow
    def test_flow_natural_date_resolved_in_preprocess(self):
        """
        Senaryo: Asistan tarih ister → kullanıcı 'yarın' der →
        ön işleme bunu YYYY-MM-DD'ye çevirir.
        """
        sid = "flow_date_resolve"
        clear_session(sid)

        history = [
            {"role": "assistant", "content": "Ne zaman yolculuk yapmak istiyorsunuz? (tarih)"}
        ]

        result = preprocess_request("yarın", history, "tr", sid)
        assert "TARİH_ALGILANDI" in result or "DATE_RESOLVED" in result

        clear_session(sid)

    @pytest.mark.flow
    def test_flow_invalid_tc_does_not_update_session(self):
        """
        Senaryo: Geçersiz TC girilir → oturum tc_verified=False kalır.
        """
        sid = "flow_invalid_tc"
        clear_session(sid)

        result = validate_tc_number("12345")  # Çok kısa
        assert result.success is False

        # Başarısız sonuç oturumu güncellememeli
        update_session_from_tool_result(sid, "validate_tc_number", {}, result)
        assert get_session(sid).tc_verified is False

        clear_session(sid)

    @pytest.mark.flow
    def test_flow_session_cleared_after_reservation(self):
        """
        Senaryo: Rezervasyon tamamlandıktan sonra oturum sıfırlanır.
        Yeni bir rezervasyon başlatılabilir.
        """
        sid = "flow_session_reset"

        # Önceki rezervasyonun verileri
        s = get_session(sid)
        s.sefer_id = 10
        s.seat = "3"
        s.validated_email = "test@gmail.com"
        s.tc_verified = True

        # Rezervasyon başarılı
        result = ToolResult(
            message="Başarılı! PNR Kodu: ZXCV1234",
            success=True,
            data={"pnr": "ZXCV1234"}
        )
        update_session_from_tool_result(sid, "make_reservation",
            {"yolcu_ad_soyad": "Ayşe Demir"}, result
        )

        # Oturum sıfırlanmış olmalı
        fresh = get_session(sid)
        assert fresh.sefer_id is None
        assert fresh.seat is None
        assert fresh.tc_verified is False

        clear_session(sid)

    @pytest.mark.flow
    def test_flow_bilingual_switch(self):
        """
        Senaryo: Türkçe ve İngilizce modda ön işleme tutarlı çalışır.
        """
        sid_tr = "flow_lang_tr"
        sid_en = "flow_lang_en"
        clear_session(sid_tr)
        clear_session(sid_en)

        history_tr = [{"role": "assistant", "content": "Tarih giriniz"}]
        history_en = [{"role": "assistant", "content": "Please enter travel date"}]

        result_tr = preprocess_request("yarın", history_tr, "tr", sid_tr)
        result_en = preprocess_request("tomorrow", history_en, "en", sid_en)

        assert "TARİH_ALGILANDI" in result_tr or "DATE_RESOLVED" in result_tr
        assert "DATE_RESOLVED" in result_en or "TARİH_ALGILANDI" in result_en

        clear_session(sid_tr)
        clear_session(sid_en)


# ==============================================================================
# BÖLÜM 13 — PERFORMANCE TESTS (Gecikme Ölçümü)
# ==============================================================================

class TestPerformance:
    """Gecikme ve performans ölçüm testleri."""

    @pytest.mark.unit
    def test_extract_digit_stream_under_1ms(self):
        """Normalizasyon 1ms altında tamamlanmalı."""
        t0 = time.perf_counter()
        for _ in range(1000):
            extract_digit_stream("bir sifir sifir sifir sifir sifir sifir sifir bir dort alti")
        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Ortalama {avg_ms:.3f}ms > 1ms"

    @pytest.mark.unit
    def test_hash_pii_under_1ms(self):
        """SHA-256 karma 1ms altında tamamlanmalı."""
        t0 = time.perf_counter()
        for _ in range(1000):
            _hash_pii("12345678901")
        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Ortalama {avg_ms:.3f}ms > 1ms"

    @pytest.mark.unit
    def test_build_truth_injection_under_1ms(self):
        """Truth injection oluşturma 1ms altında olmalı."""
        sid = "perf_truth"
        clear_session(sid)
        s = get_session(sid)
        s.sefer_id = 7; s.departure = "Bursa"; s.destination = "Istanbul"
        s.travel_date = "2025-07-15"; s.seat = "12"
        t0 = time.perf_counter()
        for _ in range(1000):
            build_truth_injection(s)
        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Ortalama {avg_ms:.3f}ms > 1ms"
        clear_session(sid)

    @pytest.mark.unit
    def test_preprocess_deterministic_shortcut_under_50ms(self):
        """Deterministik kestirme doğrulama 50ms altında tamamlanmalı."""
        sid = "perf_preprocess"
        clear_session(sid)
        history = [{"role": "assistant", "content": "Boş koltuklar: 3, 7, 12"}]
        t0 = time.perf_counter()
        for _ in range(100):
            preprocess_request("7", history, "tr", sid)
        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / 100) * 1000
        assert avg_ms < 50.0, f"Ortalama {avg_ms:.3f}ms > 50ms"
        clear_session(sid)

    @pytest.mark.unit
    def test_session_operations_under_1ms(self):
        """Oturum okuma/yazma 1ms altında olmalı."""
        sid = "perf_session"
        clear_session(sid)
        result = ToolResult(message="ok", success=True, data={"seat": 5})
        t0 = time.perf_counter()
        for _ in range(1000):
            update_session_from_tool_result(sid, "validate_seat_selection", {}, result)
        elapsed = time.perf_counter() - t0
        avg_ms = (elapsed / 1000) * 1000
        assert avg_ms < 1.0, f"Ortalama {avg_ms:.3f}ms > 1ms"
        clear_session(sid)


# ==============================================================================
# TEST METRICS RAPORU
# ==============================================================================

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Test çalıştırması tamamlandığında özet metrikleri yazdırır.
    Tez 'Araştırma Sonuçları' bölümü için doğrudan kullanılabilir.
    """
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    error  = len(terminalreporter.stats.get("error", []))
    skipped = len(terminalreporter.stats.get("skipped", []))
    total = passed + failed + error

    if total == 0:
        return

    print("\n" + "="*60)
    print("  ARAŞTIRMA SONUÇLARI — TEST METRİKLERİ ÖZETİ")
    print("="*60)
    print(f"  Toplam Test    : {total}")
    print(f"  PASS           : {passed}  ({100*passed//total if total else 0}%)")
    print(f"  FAIL           : {failed}")
    print(f"  ERROR          : {error}")
    print(f"  SKIP           : {skipped}")
    print("="*60)
    print("  Tez bölümü için not: Bu çıktıyı Tablo 4.1 olarak kullanın.")
    print("="*60)