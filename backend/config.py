import os
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(_env_path, override=True)

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Prompt dosyasını diskten yükle. Dosya yoksa RuntimeError fırlat."""
    path = _PROMPTS_DIR / filename
    if not path.exists():
        raise RuntimeError(
            f"Prompt dosyası bulunamadı: {path}. "
            "backend/prompts/ klasörünün mevcut olduğundan emin olun."
        )
    return path.read_text(encoding="utf-8")


def _parse_int(val: str | None, default: int) -> int:
    try:
        return int(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _parse_list(val: str | None) -> list[str]:
    return [v.strip() for v in (val or "*").split(",") if v.strip()]


@dataclass
class Settings:
    # Sistem promptları dışarıdan yüklenir; kod içinde gömülü değil.
    SYSTEM_PROMPT: str = field(default_factory=lambda: _load_prompt("system_tr.txt"))
    SYSTEM_PROMPT_EN: str = field(default_factory=lambda: _load_prompt("system_en.txt"))

    DEFAULT_LANG: str = field(default_factory=lambda: os.getenv("DEFAULT_LANG", "tr"))
    PORT: int = field(default_factory=lambda: _parse_int(os.getenv("PORT"), 8001))
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    ELEVENLABS_API_KEY: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    ELEVENLABS_STT_MODEL: str = field(
        default_factory=lambda: os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")
    )

    # Gemini — STT fallback
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    GEMINI_STT_MODEL: str = field(
        default_factory=lambda: os.getenv("GEMINI_STT_MODEL", "gemini-2.5-flash")
    )

    # Varsayılan değer .env.example'da belgelenmiş; burada sadece fallback.
    OPENAI_CHAT_MODEL: str = field(
        default_factory=lambda: os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    )
    CORS_ORIGINS: list[str] = field(
        default_factory=lambda: _parse_list(os.getenv("CORS_ORIGINS", "*"))
    )

    def __post_init__(self) -> None:
        import warnings
        if not self.OPENAI_API_KEY:
            warnings.warn(
                "OPENAI_API_KEY ayarlanmamış. Tüm LLM çağrıları başarısız olacak.",
                stacklevel=2,
            )
        if not self.ELEVENLABS_API_KEY and not self.GEMINI_API_KEY:
            warnings.warn(
                "ELEVENLABS_API_KEY ve GEMINI_API_KEY ikisi de ayarlanmamış. "
                "STT (konuşma tanıma) çalışmayacak.",
                stacklevel=2,
            )
        elif not self.ELEVENLABS_API_KEY:
            warnings.warn(
                "ELEVENLABS_API_KEY ayarlanmamış. STT yalnızca Gemini fallback ile çalışacak.",
                stacklevel=2,
            )
        elif not self.GEMINI_API_KEY:
            warnings.warn(
                "GEMINI_API_KEY ayarlanmamış. STT Gemini fallback'i kullanamayacak.",
                stacklevel=2,
            )
        if self.CORS_ORIGINS == ["*"]:
            warnings.warn(
                "CORS_ORIGINS '*' olarak ayarlandı — tüm kaynaklara izin verildi. "
                "Üretimde CORS_ORIGINS ortam değişkeniyle belirli bir kaynak belirleyin.",
                stacklevel=2,
            )


settings = Settings()
