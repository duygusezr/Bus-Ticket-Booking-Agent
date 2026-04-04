"""
services/session_state.py
─────────────────────────
Onaylanan rezervasyon verilerini sunucu tarafında saklayan hafif session yönetimi.

Araçlar artık ToolResult dataclass'ı döndürür; bu sayede session_state
araç çıktısını string üzerinden regex ile değil, doğrudan data alanından okur.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Any


# ─────────────────────────────────────────────
# Araç dönüş tipi
# ─────────────────────────────────────────────

@dataclass
class ToolResult:
    """
    Tüm LLM araçlarının döndürdüğü yapılandırılmış sonuç.

    message : LLM'e ve kullanıcıya gösterilecek insan okunabilir metin.
    success : İşlem başarılı mıydı?
    data    : session_state'in regex olmadan okuyacağı anahtar-değer verisi.
    """
    message: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Gemini araç döngüsü string bekler; message'ı döndür."""
        return self.message


# ─────────────────────────────────────────────
# Oturum modeli
# ─────────────────────────────────────────────

@dataclass
class BookingSession:
    """Tek bir kullanıcı oturumunun rezervasyon durumu."""
    sefer_id: Optional[int] = None
    departure: Optional[str] = None
    destination: Optional[str] = None
    travel_date: Optional[str] = None
    seat: Optional[str] = None
    passenger_name: Optional[str] = None
    validated_phone: Optional[str] = None
    validated_email: Optional[str] = None
    tc_verified: bool = False


# Oturum deposu — tek process için yeterli.
# Yatay ölçekleme gerektiğinde Redis ile değiştirilebilir.
_store: Dict[str, BookingSession] = {}


def get_session(session_id: str = "default") -> BookingSession:
    """Varsa mevcut, yoksa yeni oturum döndür."""
    if session_id not in _store:
        _store[session_id] = BookingSession()
    return _store[session_id]


def clear_session(session_id: str = "default") -> None:
    """Rezervasyon tamamlandıktan veya sıfırlandıktan sonra çağrılır."""
    _store.pop(session_id, None)


def update_session_from_tool_result(
    session_id: str,
    tool_name: str,
    tool_args: dict,
    tool_result: ToolResult,
) -> None:
    """
    LLM araç döngüsünden gelen her araç çağrısında çağrılır.
    Veriyi ToolResult.data'dan okur — regex ayrıştırma yoktur.
    """
    if not tool_result.success:
        return

    session = get_session(session_id)
    d = tool_result.data

    if tool_name == "get_bus_trips":
        session.departure = tool_args.get("departure_city") or session.departure
        session.destination = tool_args.get("destination_city") or session.destination
        if tool_args.get("travel_date"):
            session.travel_date = tool_args["travel_date"]
        if "sefer_id" in d:
            session.sefer_id = d["sefer_id"]

    elif tool_name == "validate_seat_selection":
        if "seat" in d:
            session.seat = str(d["seat"])

    elif tool_name == "validate_tc_number":
        session.tc_verified = True

    elif tool_name == "validate_phone_number":
        if "formatted" in d:
            session.validated_phone = d["formatted"]

    elif tool_name == "validate_email_address":
        if "email" in d:
            session.validated_email = d["email"]

    elif tool_name == "make_reservation":
        if "pnr" in d:
            clear_session(session_id)

    # make_reservation argümanlarından yolcu adını kaydet
    if tool_name == "make_reservation" and "yolcu_ad_soyad" in tool_args:
        # Oturum temizlenmeden önce adı okuyabiliriz ama oturum zaten silindi;
        # bu alan bilgi amaçlıdır, kritik değil.
        pass


def build_truth_injection(session: BookingSession) -> str:
    """
    Oturumdaki doğrulanmış verileri LLM'e enjekte edilecek
    [ABSOLUTE SYSTEM TRUTH: ...] bloğuna dönüştür.
    Boş oturum için boş string döner.
    """
    parts: list[str] = []
    if session.sefer_id is not None:
        parts.append(f"STRICT_ID={session.sefer_id}")
    if session.departure and session.destination:
        parts.append(f"STRICT_ROUTE={session.departure} -> {session.destination}")
    if session.travel_date:
        parts.append(f"STRICT_DATE={session.travel_date}")
    if session.seat:
        parts.append(f"STRICT_SEAT={session.seat}")
    if session.passenger_name:
        parts.append(f"STRICT_NAME={session.passenger_name}")
    if session.validated_phone:
        parts.append(f"STRICT_PHONE={session.validated_phone}")
    if session.validated_email:
        parts.append(f"STRICT_EMAIL={session.validated_email}")

    if not parts:
        return ""
    return f" [ABSOLUTE SYSTEM TRUTH (ASLA HALLUCINATE ETME): {' | '.join(parts)}]"
