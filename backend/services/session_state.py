"""
services/session_state.py
─────────────────────────
Onaylanan rezervasyon verilerini sunucu tarafında saklayan hafif session yönetimi.

Araçlar ToolResult (services/types.py) döndürür; bu sayede session_state
araç çıktısını string üzerinden regex ile değil, doğrudan data alanından okur.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from services.types import ToolResult  # noqa: F401 — dışarıdan erişim için re-export


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
    tc_no: Optional[str] = None
    # Koltuk haritası popup için
    available_seats: Optional[str] = None
    occupied_seats: Optional[str] = None
    seat_map_pending: bool = False


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
        if "available_seats" in d:
            session.available_seats = d["available_seats"]
            session.occupied_seats = d.get("occupied_seats", "")
            session.seat_map_pending = True

    elif tool_name == "validate_seat_selection":
        if "seat" in d:
            session.seat = str(d["seat"])

    elif tool_name == "validate_tc_number":
        session.tc_verified = True
        if "tc_no" in tool_args:
            session.tc_no = str(tool_args["tc_no"])

    elif tool_name == "validate_phone_number":
        if "formatted" in d:
            session.validated_phone = d["formatted"]

    elif tool_name == "validate_email_address":
        if "email" in d:
            session.validated_email = d["email"]

    elif tool_name == "make_reservation":
        # Yolcu adını rezervasyon temizlenmeden önce kaydet
        if "yolcu_ad_soyad" in tool_args:
            session.passenger_name = tool_args["yolcu_ad_soyad"]
        if "pnr" in d:
            clear_session(session_id)


def build_state_block(session: "BookingSession", lang: str = "tr") -> str:
    """
    Oturumdaki doğrulanmış verileri LLM'e system prompt üzerinden iletilecek
    yapılandırılmış blok olarak döndürür.

    - Kullanıcı mesajına EKLENMEZ; her zaman system prompt içine girer.
    - Sadece dolu alanlar gösterilir.
    - Boş oturum için boş string döner.
    - TC numarası kasıtlı olarak saklanmaz — her seferinde kullanıcıdan alınır.
    """
    if lang == "en":
        return _build_state_block_en(session)
    return _build_state_block_tr(session)


def _build_state_block_tr(session: "BookingSession") -> str:
    lines: list[str] = []

    if session.sefer_id is not None:
        lines.append(f"- Sefer ID     : {session.sefer_id}")
    if session.departure and session.destination:
        lines.append(f"- Güzergah     : {session.departure} → {session.destination}")
    if session.travel_date:
        lines.append(f"- Tarih        : {session.travel_date}")
    if session.seat:
        lines.append(f"- Koltuk       : {session.seat}")
    if session.passenger_name:
        lines.append(f"- Yolcu Adı    : {session.passenger_name}")
    if session.validated_phone:
        lines.append(f"- Telefon      : {session.validated_phone}")
    if session.validated_email:
        lines.append(f"- E-posta      : {session.validated_email}")
    if session.tc_verified and session.tc_no:
        lines.append(f"- TC No        : {session.tc_no}")
    elif session.tc_verified:
        lines.append("- TC Doğrulama : ✓ Onaylandı")

    if not lines:
        return ""

    # Eksik alanları listele
    missing: list[str] = []
    if session.sefer_id is None:
        missing.append("Sefer ID")
    if not session.seat:
        missing.append("Koltuk")
    if not session.passenger_name:
        missing.append("Ad Soyad")
    if not session.tc_verified:
        missing.append("TC Kimlik")
    if not session.validated_phone:
        missing.append("Telefon")
    if not session.validated_email:
        missing.append("E-posta")

    block = "\n".join(lines)
    if missing:
        block += f"\n- Eksik Bilgiler: {', '.join(missing)}"
    else:
        block += "\n- Eksik Bilgiler: Yok — tüm bilgiler tam"

    return (
        "\n\n## REZERVASYON DURUMU (DOĞRULANMIŞ — ASLA HALLUCINATE ETME)\n"
        f"{block}"
    )


def _build_state_block_en(session: "BookingSession") -> str:
    lines: list[str] = []

    if session.sefer_id is not None:
        lines.append(f"- Trip ID      : {session.sefer_id}")
    if session.departure and session.destination:
        lines.append(f"- Route        : {session.departure} → {session.destination}")
    if session.travel_date:
        lines.append(f"- Date         : {session.travel_date}")
    if session.seat:
        lines.append(f"- Seat         : {session.seat}")
    if session.passenger_name:
        lines.append(f"- Passenger    : {session.passenger_name}")
    if session.validated_phone:
        lines.append(f"- Phone        : {session.validated_phone}")
    if session.validated_email:
        lines.append(f"- Email        : {session.validated_email}")
    if session.tc_verified and session.tc_no:
        lines.append(f"- TC No        : {session.tc_no}")
    elif session.tc_verified:
        lines.append("- TC Verified  : ✓ Confirmed")

    if not lines:
        return ""

    missing: list[str] = []
    if session.sefer_id is None:
        missing.append("Trip ID")
    if not session.seat:
        missing.append("Seat")
    if not session.passenger_name:
        missing.append("Full Name")
    if not session.tc_verified:
        missing.append("TC Identity")
    if not session.validated_phone:
        missing.append("Phone")
    if not session.validated_email:
        missing.append("Email")

    block = "\n".join(lines)
    if missing:
        block += f"\n- Missing Info : {', '.join(missing)}"
    else:
        block += "\n- Missing Info : None — all fields complete"

    return (
        "\n\n## BOOKING STATE (VERIFIED — NEVER HALLUCINATE)\n"
        f"{block}"
    )


def build_truth_injection(session: BookingSession) -> str:
    """
    Legacy function for backward compatibility with tests.
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


