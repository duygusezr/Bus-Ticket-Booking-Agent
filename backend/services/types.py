"""
services/types.py
─────────────────
Proje genelinde paylaşılan veri tipleri ve sözleşmeler.

ToolResult buraya taşındı çünkü hem tools.py hem session_state.py hem de
llm_service.py tarafından kullanılıyor. tools.py'ın session_state.py'a
bağımlı olması ters bir bağımlılık yönüydü; ortak tipler ayrı bir modülde
olmalı.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class ToolResult:
    """
    Tüm LLM araçlarının döndürdüğü yapılandırılmış sonuç.

    message : LLM'e iletilecek insan okunabilir metin.
    success : İşlem başarılı mıydı?
    data    : session_state'in regex olmadan okuyacağı anahtar-değer verisi.
    """
    message: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Gemini araç döngüsü string bekler; message'ı döndür."""
        return self.message
