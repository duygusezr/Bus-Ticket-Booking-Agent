"""
Shared Turkish/English number word → digit conversion utilities.
Eliminates ~600 lines of duplicated parsing logic across tools.py, stt_service.py.
"""
import re

UNIT_MAP = {
    "sifir": 0, "bir": 1, "iki": 2, "uc": 3, "dort": 4,
    "bes": 5, "alti": 6, "yedi": 7, "sekiz": 8, "dokuz": 9,
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
}

TEN_MAP = {
    "on": 10, "yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50,
    "altmis": 60, "atmis": 60, "almis": 60, "yetmis": 70, "yemis": 70,
    "seksen": 80, "seksan": 80, "doksan": 90,
    "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

COMPOUND_MAP = {
    "onbir": 11, "oniki": 12, "onuc": 13, "ondort": 14, "onbes": 15,
    "onalti": 16, "onyedi": 17, "onsekiz": 18, "ondokuz": 19,
    "yirmibir": 21, "yirmiiki": 22, "yirmiuc": 23, "yirmidort": 24,
    "yirmibes": 25, "yirmialti": 26, "yirmiyedi": 27, "yirmisekiz": 28,
    "yirmidokuz": 29, "otuzbir": 31, "otuziki": 32, "otuzuc": 33,
    "otuzdort": 34, "otuzbes": 35, "otuzalti": 36, "otuzyedi": 37,
    "otuzsekiz": 38, "otuzdokuz": 39, "kirkbir": 41, "kirkiki": 42,
    "kirkuc": 43, "kirkdort": 44, "kirkbes": 45, "kirkalti": 46,
    "kirkyedi": 47, "kirksekiz": 48, "kirkdokuz": 49, "ellibir": 51,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}


def normalize_text(text: str) -> str:
    """Lowercase + Turkish char normalization + collapse whitespace."""
    t = (text or "").lower()
    for src, dst in [("ı","i"),("ş","s"),("ğ","g"),("ü","u"),("ö","o"),("ç","c"),("İ","i"),("Ş","s"),("Ğ","g"),("Ü","u"),("Ö","o"),("Ç","c")]:
        t = t.replace(src, dst)
    return re.sub(r"\s+", " ", t).strip()


def tokenize_numeric(text: str, keep_at: bool = False) -> list[str]:
    """Strip punctuation (optionally keep @) and split into tokens."""
    pattern = r"[^0-9a-zA-Z@\s]" if keep_at else r"[^0-9a-zA-Z\s]"
    return re.sub(r"\s+", " ", re.sub(pattern, " ", normalize_text(text))).strip().split()


def _merge_decade_unit(parts: list[str]) -> list[str]:
    """Merge STT split artifacts: ['60','1'] → ['61']"""
    merged: list[str] = []
    i = 0
    while i < len(parts):
        cur = parts[i]
        nxt = parts[i + 1] if i + 1 < len(parts) else None
        if (
            nxt is not None
            and cur.isdigit() and nxt.isdigit()
            and int(cur) in {10, 20, 30, 40, 50, 60, 70, 80, 90}
            and len(nxt) == 1 and int(nxt) > 0
        ):
            merged.append(str(int(cur) + int(nxt)))
            i += 2
        else:
            merged.append(cur)
            i += 1
    return merged


def extract_digit_stream(text: str) -> str:
    """
    Convert a mixed Turkish/English word+digit string into a pure digit string.
    Handles: units, tens, hundreds, compounds, STT split artifacts.
    Returns empty string if no digits found.
    """
    tokens = tokenize_numeric(text)
    parts: list[str] = []
    i = 0

    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else ""

        # Hundreds: "N yuz [tens] [unit]"
        if (tok.isdigit() or tok in UNIT_MAP) and nxt == "yuz":
            val = int(tok) if tok.isdigit() else UNIT_MAP[tok]
            hundreds = val * 100
            i += 2
            if i < len(tokens) and tokens[i] in TEN_MAP:
                hundreds += TEN_MAP[tokens[i]]
                i += 1
                if i < len(tokens) and (tokens[i] in UNIT_MAP or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                    hundreds += int(UNIT_MAP.get(tokens[i], tokens[i]))
                    i += 1
            elif i < len(tokens) and (tokens[i] in UNIT_MAP or (tokens[i].isdigit() and len(tokens[i]) == 1)):
                hundreds += int(UNIT_MAP.get(tokens[i], tokens[i]))
                i += 1
            parts.append(str(hundreds))
            continue

        if tok == "yuz":
            parts.append("100"); i += 1; continue

        if tok.isdigit():
            parts.append(tok); i += 1; continue

        if tok in COMPOUND_MAP:
            parts.append(str(COMPOUND_MAP[tok])); i += 1; continue

        if tok in TEN_MAP:
            if nxt in UNIT_MAP:
                parts.append(str(TEN_MAP[tok] + UNIT_MAP[nxt])); i += 2; continue
            if nxt.isdigit() and len(nxt) == 1 and int(nxt) > 0:
                parts.append(str(TEN_MAP[tok] + int(nxt))); i += 2; continue
            parts.append(str(TEN_MAP[tok])); i += 1; continue

        if tok in UNIT_MAP:
            parts.append(str(UNIT_MAP[tok])); i += 1; continue

        i += 1  # unknown token — skip

    parts = _merge_decade_unit(parts)
    return "".join(parts)


def normalize_phone_digits(text: str) -> str:
    """
    Extract digits from phone input (words or mixed), strip country code.
    Returns normalized digit string (10-11 digits expected).
    """
    digits = extract_digit_stream(text)
    if not digits:
        # fallback: strip non-digits
        digits = re.sub(r"[^0-9]", "", text)

    # Strip country code
    if len(digits) == 12 and digits.startswith("90") and digits[2] == "5":
        digits = "0" + digits[2:]
    elif len(digits) == 13 and digits.startswith("090"):
        digits = digits[1:]
    if len(digits) == 10 and digits.startswith("5"):
        digits = "0" + digits

    return digits
