import io
import re
from elevenlabs.client import ElevenLabs
from config import settings

def get_eleven_client():
    """Anahtari her seferinde guncel ayarlardan alarak client olusturur."""
    if settings.ELEVENLABS_API_KEY and "your_" not in settings.ELEVENLABS_API_KEY.lower():
        return ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)
    return None


def _normalize_stt_text(raw_text: str) -> str:
    """
    Clean common ASR noise and keep the most booking-relevant fragment.
    """
    if not raw_text:
        return ""

    text = raw_text.strip()
    text = re.sub(r"\(([^)]*)\)", " ", text)  # remove parenthesized cues
    text = re.sub(r"\s+", " ", text).strip()

    # Kendi kendine tekrar eden kısa metinleri temizleme (ElevenLabs/STT halüsinasyonu)
    # 1. Karakter bazlı tam tekrar (Örn: "uygusazar.uygusazar.")
    if len(text) > 3 and len(text) % 2 == 0:
        half = len(text) // 2
        if text[:half] == text[half:]:
            text = text[:half]

    # 2. Kelime bazlı tekrar (Örn: "Duygu Sezer Duygu Sezer")
    words = text.split()
    if len(words) > 0 and len(words) % 2 == 0:
        half_w = len(words) // 2
        if words[:half_w] == words[half_w:]:
            text = " ".join(words[:half_w])


    # Split by sentence boundaries and score each part by booking relevance.
    parts = [p.strip(" .,!?:;") for p in re.split(r"[.!?]+", text) if p.strip(" .,!?:;")]
    if not parts:
        return text

    booking_keywords = {
        "ocak", "subat", "şubat", "mart", "nisan", "mayis", "mayıs", "haziran",
        "temmuz", "agustos", "ağustos", "eylul", "eylül", "ekim", "kasim", "kasım", "aralik", "aralık",
        "istanbul", "ankara", "izmir", "bursa", "antalya", "adana", "konya", "evet", "hayır", "hayir",
        "koltuk", "sefer", "bilet", "rezervasyon"
    }
    turkish_numbers = {
        "bir", "iki", "uc", "üç", "dort", "dört", "bes", "beş", "alti", "altı", "yedi", "sekiz",
        "dokuz", "on", "on bir", "onbir", "on iki", "oniki", "on uc", "onüç", "on üç"
    }

    def score(part: str) -> int:
        p = part.lower()
        s = 0
        if re.search(r"\b\d{1,2}\b", p):
            s += 2
        if any(m in p for m in booking_keywords):
            s += 3
        if any(n in p for n in turkish_numbers):
            s += 2
        if len(p.split()) <= 6:
            s += 1
        return s

    best = max(parts, key=score)
    best_score = score(best)

    # If we found a clearly relevant short fragment, prefer it.
    if best_score >= 3:
        return best.strip()

    return text


def _normalize_numeric_input(text: str) -> str:
    """
    Sesli girişten gelen karışık rakam+yazı ifadelerini tek akışta rakamlara çevirir.
    
    Örnekler:
      "37 50 6 yetmiş"            -> "37506070"  (yetmiş = 70 tek başına)
      "37 50 6 yetmiş altmış 1 27 4" -> "37506070611274" 
      "beş 37 yirmi yedi"         -> "53727"
      "sıfır beş üç yedi"         -> "0537"
      "altmış bir"                 -> "61"
      "dört yüz elli"             -> "450" (yüz desteği)
    """
    if not text:
        return ""
    
    t = text.lower().strip()
    # Türkçe karakter normalizasyonu
    t = t.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    t = t.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    # Noktalama ve özel karakterleri temizle (@ ve . hariç - email için)
    t = re.sub(r"[^0-9a-zA-Z@\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    
    # E-posta benzeri yapı varsa dokunma
    if "@" in t:
        return text.strip()
    
    unit_map = {
        "sifir": "0", "bir": "1", "iki": "2", "uc": "3", "dort": "4",
        "bes": "5", "alti": "6", "yedi": "7", "sekiz": "8", "dokuz": "9"
    }
    ten_map = {
        "on": 10, "yirmi": 20, "otuz": 30, "kirk": 40, "elli": 50,
        "altmis": 60, "atmis": 60, "almis": 60, "yetmis": 70, "yemis": 70, "seksen": 80, "seksan": 80, "doksan": 90
    }
    # Bitişik compound'lar (STT bazen boşluksuz yazar)
    compound_map = {
        "onbir": "11", "oniki": "12", "onuc": "13", "ondort": "14", "onbes": "15",
        "onalti": "16", "onyedi": "17", "onsekiz": "18", "ondokuz": "19",
        "yirmibir": "21", "yirmiiki": "22", "yirmiuc": "23", "yirmidort": "24",
        "yirmibes": "25", "yirmialti": "26", "yirmiyedi": "27", "yirmisekiz": "28",
        "yirmidokuz": "29", "otuzbir": "31", "otuziki": "32", "otuzuc": "33",
        "otuzdort": "34", "otuzbes": "35", "otuzalti": "36", "otuzyedi": "37",
        "otuzsekiz": "38", "otuzdokuz": "39",
        "kirkbir": "41", "kirkiki": "42", "kirkuc": "43", "kirkdort": "44",
        "kirkbes": "45", "kirkalti": "46", "kirkyedi": "47", "kirksekiz": "48",
        "kirkdokuz": "49", "ellibir": "51",
    }
    
    tokens = t.split()
    parts: list[str] = []
    i = 0
    
    while i < len(tokens):
        tok = tokens[i]
        
        # 1. Saf rakam
        if tok.isdigit():
            parts.append(tok)
            i += 1
            continue
        
        # 2. Bitişik compound ("onbir", "yirmialti" vb.)
        if tok in compound_map:
            parts.append(compound_map[tok])
            i += 1
            continue
        
        # 3. Onluk ("on", "yirmi", ..., "doksan")
        if tok in ten_map:
            ten_val = ten_map[tok]
            # Sonraki token birlik mi?
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt in unit_map and nxt != "sifir":
                # "yetmiş iki" -> 72
                parts.append(str(ten_val + int(unit_map[nxt])))
                i += 2
                continue
            elif nxt.isdigit() and len(nxt) == 1 and int(nxt) > 0:
                # "yetmiş 2" -> 72  (STT bazen sonraki rakamı sayı olarak yazar)
                parts.append(str(ten_val + int(nxt)))
                i += 2
                continue
            else:
                # "yetmiş" tek başına -> 70
                parts.append(str(ten_val))
                i += 1
                continue
        
        # 4. Birlik ("bir", "iki", ..., "dokuz", "sıfır")
        if tok in unit_map:
            parts.append(unit_map[tok])
            i += 1
            continue
        
        # 5. Tanınmayan kelime - sayısal ifade değilse atla
        i += 1
    
    # İkinci pas: STT parçalanma tamiri
    # "60 1" -> "61", "70 4" -> "74" gibi durumlarda birleştir
    merged: list[str] = []
    i = 0
    while i < len(parts):
        cur = parts[i]
        nxt = parts[i + 1] if i + 1 < len(parts) else None
        if (
            nxt is not None
            and cur.isdigit()
            and nxt.isdigit()
            and int(cur) in {10, 20, 30, 40, 50, 60, 70, 80, 90}
            and len(nxt) == 1
            and int(nxt) > 0
        ):
            merged.append(str(int(cur) + int(nxt)))
            i += 2
            continue
        merged.append(cur)
        i += 1
    
    result = "".join(merged)
    
    # Sonuçta hiç rakam yoksa orijinal metni dön
    if not result or not any(c.isdigit() for c in result):
        return text.strip()
    
    return result


def _convert_turkish_number_words(text: str) -> str:
    """
    Convert common Turkish number words (1-50) into digits.
    Examples: "beş" -> "5", "on dokuz" -> "19".
    """
    if not text:
        return ""

    t = text.lower()

    # Compound numbers first to avoid partial replacements.
    compound_map = {
        "on bir": "11", "onbir": "11",
        "on iki": "12", "oniki": "12",
        "on üç": "13", "onuc": "13", "on uc": "13", "onüç": "13",
        "on dört": "14", "ondort": "14", "on dort": "14",
        "on beş": "15", "onbes": "15", "on bes": "15",
        "on altı": "16", "onalti": "16", "on alti": "16",
        "on yedi": "17", "onyedi": "17",
        "on sekiz": "18", "onsekiz": "18",
        "on dokuz": "19", "ondokuz": "19",
        "yirmi bir": "21", "yirmibir": "21",
        "yirmi iki": "22", "yirmiiki": "22",
        "yirmi üç": "23", "yirmiuc": "23", "yirmi uc": "23", "yirmiüç": "23",
        "yirmi dört": "24", "yirmidort": "24", "yirmi dort": "24",
        "yirmi beş": "25", "yirmibes": "25", "yirmi bes": "25",
        "yirmi altı": "26", "yirmialti": "26", "yirmi alti": "26",
        "yirmi yedi": "27", "yirmiyedi": "27",
        "yirmi sekiz": "28", "yirmisekiz": "28",
        "yirmi dokuz": "29", "yirmidokuz": "29",
        "otuz bir": "31", "otuzbir": "31",
        "otuz iki": "32", "otuziki": "32",
        "otuz üç": "33", "otuzuc": "33", "otuz uc": "33", "otuzüç": "33",
        "otuz dört": "34", "otuzdort": "34", "otuz dort": "34",
        "otuz beş": "35", "otuzbes": "35", "otuz bes": "35",
        "otuz altı": "36", "otuzalti": "36", "otuz alti": "36",
        "otuz yedi": "37", "otuzyedi": "37",
        "otuz sekiz": "38", "otuzsekiz": "38",
        "otuz dokuz": "39", "otuzdokuz": "39",
        "kırk bir": "41", "kirk bir": "41", "kirkbir": "41", "kırkbir": "41",
        "kırk iki": "42", "kirk iki": "42", "kirkiki": "42", "kırkiki": "42",
        "kırk üç": "43", "kirk üç": "43", "kirk uc": "43", "kırkuc": "43",
        "kırk dört": "44", "kirk dört": "44", "kirk dort": "44", "kırkdort": "44",
        "kırk beş": "45", "kirk beş": "45", "kirk bes": "45", "kırkbes": "45",
        "kırk altı": "46", "kirk altı": "46", "kirk alti": "46", "kırkalti": "46",
        "kırk yedi": "47", "kirk yedi": "47", "kirkyedi": "47", "kırkyedi": "47",
        "kırk sekiz": "48", "kirk sekiz": "48", "kirksekiz": "48", "kırksekiz": "48",
        "kırk dokuz": "49", "kirk dokuz": "49", "kirkdokuz": "49", "kırkdokuz": "49",
        "elli bir": "51", "ellibir": "51",
    }

    single_map = {
        "bir": "1", "iki": "2", "üç": "3", "uc": "3", "dört": "4", "dort": "4",
        "beş": "5", "bes": "5", "altı": "6", "alti": "6", "yedi": "7", "sekiz": "8",
        "dokuz": "9", "on": "10", "yirmi": "20", "otuz": "30", "kırk": "40", "kirk": "40", "elli": "50"
    }

    for k, v in sorted(compound_map.items(), key=lambda x: len(x[0]), reverse=True):
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)
    for k, v in sorted(single_map.items(), key=lambda x: len(x[0]), reverse=True):
        t = re.sub(rf"\b{re.escape(k)}\b", v, t)

    return re.sub(r"\s+", " ", t).strip()


def _collapse_numeric_sequences(text: str) -> str:
    """
    If transcript is mostly numeric chunks (e.g. "37 50 60 12 74"),
    collapse them into a continuous number for ID/phone style inputs.
    """
    if not text:
        return ""

    normalized = text.strip()
    # Keep only digits and separators to test whether input is numeric-dominant.
    numeric_only_probe = re.sub(r"[\d\s\.,;:!\?\-\(\)/]+", "", normalized)
    if numeric_only_probe:
        return normalized

    chunks = re.findall(r"\d+", normalized)
    if len(chunks) < 3:
        return normalized

    # "60 1" -> "61" gibi STT parçalanmalarını birleştir
    merged_chunks = []
    i = 0
    while i < len(chunks):
        cur = chunks[i]
        nxt = chunks[i + 1] if i + 1 < len(chunks) else None
        if (
            nxt is not None
            and cur.isdigit()
            and nxt.isdigit()
            and int(cur) in {10, 20, 30, 40, 50, 60, 70, 80, 90}
            and len(nxt) == 1
            and int(nxt) > 0
        ):
            merged_chunks.append(str(int(cur) + int(nxt)))  # 60 + 1 -> 61
            i += 2
            continue
        merged_chunks.append(cur)
        i += 1

    chunks = merged_chunks
    joined = "".join(chunks)
    # Common voice-entered identifiers in this app:
    # TC: 11 digits, phone: 10-11 digits.
    if len(joined) in (10, 11):
        return joined
    return normalized


def _detect_email_context(text: str) -> bool:
    """
    Metnin e-posta adresi içerip içermediğini tespit eder.
    Sesli söylenen email kalıplarını tanır.
    """
    if not text:
        return False
    
    t = text.lower().strip()
    t = t.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    t = t.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    
    # Zaten @ varsa kesin email
    if "@" in t:
        return True
    
    # "at" veya "et" + email domain ipuçları
    at_words = any(w in t.split() for w in ["at", "et"])
    domain_hints = any(d in t for d in ["gmail", "mail", "hotmail", "yahoo", "outlook", "yandex", "icloud"])
    dot_hints = any(d in t.split() for d in ["nokta", "dot", "com", "net", "org"])
    
    # "at/et" + domain veya "at/et" + nokta/com  
    if at_words and (domain_hints or dot_hints):
        return True
    
    # domain + nokta/com (email yazılı ama @ olmadan)
    if domain_hints and dot_hints:
        return True
    
    return False

def _detect_numeric_context(text: str) -> bool:
    """
    Metnin sayısal veri (TC, telefon vb.) içerip içermediğini tespit eder.
    Sayı ağırlıklı metin = True, kelime ağırlıklı = False.
    """
    if not text:
        return False
    
    t = text.lower().strip()
    t_normalized = t.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
    t_normalized = t_normalized.replace("ü", "u").replace("ö", "o").replace("ç", "c")
    
    # Türkçe sayı kelimeleri (STT yanlış duyma varyantları dahil)
    number_words = {
        "sifir", "bir", "iki", "uc", "dort", "bes", "alti", "yedi", "sekiz", "dokuz",
        "on", "yirmi", "otuz", "kirk", "elli", "altmis", "atmis", "almis", "yetmis", "yemis", "seksen", "seksan", "doksan",
        "onbir", "oniki", "onuc", "ondort", "onbes", "onalti", "onyedi", "onsekiz", "ondokuz"
    }
    
    tokens = re.sub(r"[^a-z0-9\s]", " ", t_normalized).split()
    if not tokens:
        return False
        
    # Tarih, gün, ay, yıl belirten kelimeler içeriyorsa sayısal ağırlıklı BAĞLAM kabul etme
    exclude_words = {
        "ocak", "subat", "mart", "nisan", "mayis", "haziran", 
        "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik",
        "bugun", "yarin", "haftaya", "gun", "ay", "yil",
        "pazartesi", "sali", "carsamba", "persembe", "cuma", "cumartesi", "pazar",
        "bin", "yuz", "isim", "sehir", "bursa", "istanbul", "ankara", "gidis", "donus"
    }
    
    for tok in tokens:
        if tok in exclude_words:
            return False
    
    numeric_token_count = 0
    for tok in tokens:
        if tok.isdigit():
            numeric_token_count += 1
        elif tok in number_words:
            numeric_token_count += 1
    
    # Tokenların %60+'ı sayısal ise bu bir numara girişidir
    return numeric_token_count / len(tokens) >= 0.6


async def transcribe_audio(audio_bytes: bytes, filename: str, lang: str = settings.DEFAULT_LANG) -> dict:
    """Sadece ElevenLabs SDK (Scribe) kullanır."""
    if not audio_bytes or len(audio_bytes) == 0:
        raise Exception("Gönderilen ses verisi boş.")

    client = get_eleven_client()
    if not client:
        raise Exception("ElevenLabs API anahtarı ayarlanmamış veya geçersiz.")

    try:
        print(f"DEBUG: ElevenLabs SDK STT (Scribe) çağrılıyor... ({len(audio_bytes)} byte, {filename})")

        # ElevenLabs SDK, file parametresi olarak (filename, file_object, content_type) tuple'ı bekler
        audio_file = io.BytesIO(audio_bytes)

        # Dosya uzantısına göre content type belirle
        if filename.endswith(".webm"):
            content_type = "audio/webm"
        elif filename.endswith(".wav"):
            content_type = "audio/wav"
        elif filename.endswith(".mp3"):
            content_type = "audio/mpeg"
        elif filename.endswith(".ogg"):
            content_type = "audio/ogg"
        else:
            content_type = "audio/webm"  # Tarayıcı kaydı genellikle webm

        resp = client.speech_to_text.convert(
            file=(filename, audio_file, content_type),
            model_id="scribe_v1",
            language_code=lang,  # Frontend'den gelen dil (tr veya en)
        )

        raw_text = str(getattr(resp, "text", "") or getattr(resp, "transcript", "") or "")
        print(f"DEBUG: Ham transkripsiyon: '{raw_text}'")
        
        # Adım 1: ASR gürültüsünü temizle
        clean_text = _normalize_stt_text(raw_text)
        print(f"DEBUG: ASR temizleme sonrası: '{clean_text}'")
        
        # Adım 2: Bağlam tespiti ve uygun normalize
        if _detect_email_context(clean_text):
            # E-posta bağlamı tespit edildi
            from services.tools import _normalize_email_input
            clean_text = _normalize_email_input(clean_text)
            print(f"DEBUG: Email normalize: '{raw_text}' -> '{clean_text}'")
        elif _detect_numeric_context(clean_text):
            # Sayısal veri (TC, telefon vb.)
            numeric_result = _normalize_numeric_input(clean_text)
            print(f"DEBUG: Sayısal normalize: '{clean_text}' -> '{numeric_result}'")
            clean_text = numeric_result
        else:
            # Kelime bazlı dönüşüm (koltuk seçimi, tarih vb. için)
            clean_text = _convert_turkish_number_words(clean_text)
            clean_text = _collapse_numeric_sequences(clean_text)
        
        print(f"DEBUG: Final STT çıktısı: '{clean_text}'")

        return {
            "text": clean_text,
            "lang": getattr(resp, "language_code", settings.DEFAULT_LANG)
        }
    except Exception as e:
        print(f"ElevenLabs SDK STT Hatası: {str(e)}")
        raise Exception(f"STT Servis Hatası: {str(e)}")