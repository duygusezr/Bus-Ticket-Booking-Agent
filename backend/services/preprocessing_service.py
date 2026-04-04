"""
services/preprocessing_service.py
──────────────────────────────────
İş mantığını router'dan ayırır.

Daha önce chat.py içinde karışık halde duran tüm ön-işleme fonksiyonları
(koltuk/telefon/e-posta deterministik doğrulama, sistem enjeksiyonu, ground-truth
enjeksiyonu) buraya taşındı. Router yalnızca yönlendirme yapar.
"""
from __future__ import annotations

import re
import logging
from typing import List, Dict, Optional

from services.tools import validate_seat_selection, validate_phone_number, validate_email_address
from services.session_state import get_session, build_truth_injection
from services.types import ToolResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Yardımcı okuyucular
# ─────────────────────────────────────────────

def _last_assistant_text(history: List[Dict[str, str]]) -> str:
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            return str(msg.get("content", ""))
    return ""


# ─────────────────────────────────────────────
# Deterministik kestirme doğrulayıcılar
# Dönüş tipi Optional[ToolResult] — başarılı doğrulama veya None.
# ─────────────────────────────────────────────

def _try_seat_validation(text: str, history: List[Dict[str, str]]) -> Optional[ToolResult]:
    """Asistan son mesajında koltuk listesi gösterdiyse ve kullanıcı kısa giriş
    yaptıysa, LLM'e gitmeden doğrudan validate_seat_selection çağırır."""
    user_text = (text or "").strip()
    if not user_text:
        return None

    available_seats: Optional[str] = None
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            m = re.search(
                r"(?:Boş koltuklar|Uygun koltuklar|Boş olan şu koltuklardan birini seçin):\s*([0-9,\s]+)",
                str(msg.get("content", "")),
                flags=re.IGNORECASE,
            )
            if m:
                available_seats = m.group(1).strip()
                break

    if not available_seats:
        return None

    # Yalnızca kısa koltuk benzeri girdileri yakala
    if not re.fullmatch(r"[0-9]{1,2}|[a-zA-ZçğıöşüÇĞİÖŞÜ\s]{2,12}", user_text):
        return None

    result = validate_seat_selection(user_text, available_seats)
    return result if result.success else None


def _try_phone_validation(text: str, history: List[Dict[str, str]]) -> Optional[ToolResult]:
    """Asistan telefon istiyorsa ve girdi telefon formatına uyuyorsa doğrula."""
    user_text = (text or "").strip()
    if not user_text:
        return None

    last = _last_assistant_text(history).lower()
    if not any(kw in last for kw in ["telefon", "cep num", "05xx"]):
        return None

    clean = re.sub(r"[^0-9]", "", user_text)
    if len(clean) < 10 or len(clean) > 13:
        return None
    if len(clean) == 10 and not clean.startswith("5"):
        return None
    if len(clean) == 11 and not (clean.startswith("0") or clean.startswith("9")):
        return None

    logger.debug("Doğrudan telefon doğrulama: %r → rakamlar=%r", user_text, clean)
    result = validate_phone_number(user_text)
    return result if result.success else None


def _try_email_validation(text: str, history: List[Dict[str, str]]) -> Optional[ToolResult]:
    """Asistan e-posta istiyorsa ve giriş e-posta gibi görünüyorsa doğrula."""
    user_text = (text or "").strip()
    if not user_text:
        return None

    last = _last_assistant_text(history).lower()
    if not any(kw in last for kw in ["e-posta", "eposta", "email", "mail adres"]):
        return None

    has_at = "@" in user_text
    has_voice_at = any(w in user_text.lower().split() for w in ["at", "et"])
    has_domain = any(
        d in user_text.lower()
        for d in ["gmail", "mail", "hotmail", "yahoo", "outlook", "nokta", "com"]
    )

    if not (has_at or has_voice_at or has_domain):
        return None

    logger.debug("Doğrudan e-posta doğrulama: %r", user_text)
    result = validate_email_address(user_text)
    return result if result.success else None


# ─────────────────────────────────────────────
# Sistem enjeksiyonu
# ─────────────────────────────────────────────

def _build_validation_injection(
    lang: str,
    seat_result: Optional[ToolResult],
    phone_result: Optional[ToolResult],
    email_result: Optional[ToolResult],
    session_id: str,
) -> str:
    """Deterministik doğrulama sonuçlarını LLM'e sistem mesajı olarak enjekte et."""
    if email_result:
        session = get_session(session_id)
        sefer_id = session.sefer_id
        if lang == "en":
            base = (
                f"[SYSTEM INFORMATION: Tool result: {email_result.message}. "
                "Provide a clear SUMMARY and ask 'Do you confirm?'. Do NOT book yet!"
            )
            suffix = f" Use Trip ID={sefer_id} for Step 9.]" if sefer_id else "]"
        else:
            base = (
                f"[SİSTEM BİLGİSİ: Araç sonucu: {email_result.message}. "
                "Kullanıcıya tüm bilgilerin ÖZETİNİ sun ve 'Onaylıyor musunuz?' diye sor. Rezervasyon yapma!"
            )
            suffix = f" Onay sonrası sefer_id={sefer_id} kullanacaksın.]" if sefer_id else "]"
        return f" {base}{suffix}"

    for result in (phone_result, seat_result):
        if result:
            if lang == "en":
                return f" [SYSTEM INFORMATION: Tool result: {result.message}]"
            return f" [SİSTEM BİLGİSİ: Araç sonucu: {result.message}]"

    return ""


# ─────────────────────────────────────────────
# Ana ön-işleme giriş noktası
# ─────────────────────────────────────────────

def preprocess_request(
    text: str,
    history: List[Dict[str, str]],
    lang: str,
    session_id: str = "default",
) -> str:
    """
    Router'ın LLM'e göndermeden önce çağırdığı tek fonksiyon.

    1. Deterministik doğrulayıcıları çalıştırır (koltuk/telefon/e-posta).
    2. Doğrulama sonuçlarını sistem enjeksiyonu olarak ekler.
    3. Oturum durumundan ABSOLUTE SYSTEM TRUTH bloğunu ekler.
    """
    seat_result = _try_seat_validation(text, history)
    phone_result = _try_phone_validation(text, history)
    email_result = _try_email_validation(text, history)

    validation_injection = _build_validation_injection(
        lang, seat_result, phone_result, email_result, session_id
    )
    processed = text + validation_injection

    # Oturumdan doğrulanmış verileri enjekte et
    session = get_session(session_id)
    truth_injection = build_truth_injection(session)
    if truth_injection and truth_injection not in processed:
        processed += truth_injection

    return processed
