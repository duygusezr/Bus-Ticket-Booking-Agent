"""
services/session_state.py
─────────────────────────
Onaylanan rezervasyon verilerini sunucu tarafında saklayan hafif session yönetimi.

Neden burada?
  chat.py'daki _inject_ground_truth() fonksiyonu, onaylı sefer/koltuk/tarih
  bilgilerini ham konuşma metninden regex ile çıkarıyordu. Bu yaklaşım LLM'in
  ifadesindeki küçük değişikliklere karşı kırılgandı. Artık veriler araç
  sonuçları döndüğünde buraya açıkça yazılıyor; LLM'e de buradan okunarak
  enjekte ediliyor.

Kullanım:
  session = get_session("default")
  session.sefer_id = 42
  session.seat = "15"
  truth = build_truth_injection(session)   # "[ABSOLUTE SYSTEM TRUTH: ...]"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class BookingSession:
    """Tek bir kullanıcı oturumunun rezervasyon durumu."""
    sefer_id: Optional[int] = None
    departure: Optional[str] = None
    destination: Optional[str] = None
    travel_date: Optional[str] = None
    seat: Optional[str] = None
    passenger_name: Optional[str] = None
    # Doğrulanmış değerler (araç sonucundan)
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
    tool_result: str,
) -> None:
    """
    LLM araç döngüsünden gelen her başarılı araç çağrısında çağrılır.
    Araç adına göre hangi alanın güncelleneceğini belirler.
    """
    session = get_session(session_id)

    if tool_name == "get_bus_trips":
        # Sefer sonucundan şehirleri ve tarihi kaydet
        if "departure_city" in tool_args:
            session.departure = tool_args["departure_city"]
        if "destination_city" in tool_args:
            session.destination = tool_args["destination_city"]
        if "travel_date" in tool_args and tool_args["travel_date"]:
            session.travel_date = tool_args["travel_date"]
        # Sefer ID'yi araç sonucundan çıkar (örn: "Sefer_ID: 42")
        import re
        m = re.search(r"Sefer_ID:\s*(\d+)", tool_result)
        if m:
            session.sefer_id = int(m.group(1))

    elif tool_name == "validate_seat_selection":
        # "Koltuk 15 uygun." → seat = "15"
        import re
        m = re.search(r"Koltuk\s+(\d+)\s+uygun", tool_result)
        if m:
            session.seat = m.group(1)

    elif tool_name == "validate_tc_number":
        if "başarıyla doğrulandı" in tool_result:
            session.tc_verified = True

    elif tool_name == "validate_phone_number":
        # "Telefon numarası doğrulandı: 0537 279 14 37"
        import re
        m = re.search(r"doğrulandı:\s*(.+)", tool_result)
        if m:
            session.validated_phone = m.group(1).strip()

    elif tool_name == "validate_email_address":
        # "E-posta doğrulandı: user@gmail.com"
        import re
        m = re.search(r"doğrulandı:\s*(\S+)", tool_result)
        if m:
            session.validated_email = m.group(1).strip()

    elif tool_name == "make_reservation":
        # Rezervasyon tamamlandıysa oturumu temizle
        if "PNR Kodu:" in tool_result:
            clear_session(session_id)


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
    if session.validated_phone:
        parts.append(f"STRICT_PHONE={session.validated_phone}")
    if session.validated_email:
        parts.append(f"STRICT_EMAIL={session.validated_email}")

    if not parts:
        return ""
    return f" [ABSOLUTE SYSTEM TRUTH (ASLA HALLUCINATE ETME): {' | '.join(parts)}]"
